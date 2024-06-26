import json
from datetime import timedelta, datetime

from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from authentication import validate_request_and_user, create_access_token, encrypt_email, verify_password, \
    generate_verification_code, hash_password
from database import get_user_from_database, create_database_and_tables, save_verification_code, \
    get_verification_code, create_user_in_database, verify_user_in_database, update_user_details, save_workout_log, \
    get_formatted_workout_data
from middleware.fast_api_middleware import SessionTimeoutMiddleware
from openai_utils import get_json_from_notes, get_chatgpt_response, generate_motivational_analysis
from models import UserWorkoutNotesInput, UserCreate, EmailVerificationInput, UserDetailsUpdate
from utils.email_utils import send_verification_email
from utils.langchain_utils import add_message_to_memory, generate_response, is_session_expired, reset_session, \
    memory as langchain_buffer_memory, \
    summarize_conversation, get_initial_context

app = FastAPI()

app.add_middleware(SessionTimeoutMiddleware, timeout=30)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
bearer_scheme = HTTPBearer()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

create_database_and_tables()

# Dictionary to store session-specific data
session_data = {}


@app.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5 per minute")
async def register_user(request: Request, user: UserCreate):
    existing_user = get_user_from_database(user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    code = generate_verification_code()
    hashed_password = hash_password(user.password)
    create_user_in_database(user.email, hashed_password)
    save_verification_code(user.email, code)
    send_verification_email(user.email, code)
    return {"msg": "Verification code sent to email"}


@app.post("/verify", status_code=status.HTTP_200_OK)
@limiter.limit("5 per minute")
async def verify_user(request: Request, input: EmailVerificationInput):
    result = get_verification_code(input.email)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    stored_code, expiration = result

    # Check if the provided code matches the stored code and if the code is still valid
    if stored_code != input.code or datetime.now() > expiration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    verify_user_in_database(input.email)
    encrypted_email = encrypt_email(input.email)
    access_token = create_access_token(
        data={"sub": encrypted_email}, expires_delta=None  # long-lived token
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/token")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Find a user in the db using provided email
    user = get_user_from_database(form_data.username)

    # If the password is correct,
    if user and verify_password(form_data.password, user["hashed_password"]):
        # Only when the user has verified their email
        if not user["verified"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # return an encrypted token to the client for req authentication
        encrypted_email = encrypt_email(user["email"])
        access_token = create_access_token(
            data={"sub": encrypted_email}, expires_delta=None  # long-lived token
        )
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.post("/update-personal-details", status_code=status.HTTP_200_OK)
async def update_personal_details(request: Request, details: UserDetailsUpdate,
                                  user: dict = Depends(validate_request_and_user)):
    update_user_details(user["email"], details.height, details.weight, details.age, details.gender, details.goals)
    return {"msg": "Personal details updated successfully"}


@app.post("/save-workout")
async def save_workout(request: Request, user_workout_input: UserWorkoutNotesInput,
                       user: dict = Depends(validate_request_and_user)):
    if not user_workout_input.notes:
        raise HTTPException(status_code=400, detail="No notes provided")
    try:
        json_output = get_json_from_notes(user_workout_input.notes)

        # Parse JSON output to Python dictionary
        workout_data = json.loads(json_output)

        # Get the user's ID
        user_data = get_user_from_database(user["email"])
        user_id = user_data["user_id"]

        # Save workout logs in the database
        save_workout_log(user_id, workout_data)

        # Get workout history
        workout_history = get_formatted_workout_data(user_id)

        # Generate motivational analysis
        prompt_context = get_initial_context(user_data, workout_history)

        analysis_output = generate_motivational_analysis(prompt_context, workout_data)

        return {
            "data": workout_data,
            "analysis": analysis_output,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", status_code=status.HTTP_200_OK)
async def chat_with_gpt(request: Request, user: dict = Depends(validate_request_and_user)):
    session_id = user["email"]

    # Initialise the session if there isn't one already
    if session_id not in session_data:
        session_data[session_id] = {
            "initial_context_set": False
        }

    # Handle expired sessions
    if is_session_expired():
        reset_session()
        session_data.pop(session_id, None)  # Clear session data
        return {"message": "Session expired. Please start a new session."}

    # Only add initial prompt context into the chatGPT request at the start of the session, not with every request
    include_initial_context = not session_data[session_id]["initial_context_set"]

    if include_initial_context:
        user_data = get_user_from_database(user["email"])
        user_id = user_data["user_id"]
        workout_history = get_formatted_workout_data(user_id)
        initial_context = get_initial_context(user_data, workout_history)
        session_data[session_id]["initial_context_set"] = True
    else:
        initial_context = ""  # Empty since it's already been included

    # Summarize conversation if needed
    if len(langchain_buffer_memory.buffer) > 9000:
        summarize_conversation()

    data = await request.json()
    user_message = data["message"]

    add_message_to_memory("user", user_message)

    prompt = f"User: {user_message}\n"

    chat_response = await generate_response(prompt, include_initial_context=include_initial_context,
                                            initial_context=initial_context)
    add_message_to_memory("assistant", chat_response)

    # Set a reasonable session expiry time (e.g., 1 day from now)
    new_session_expiry_time = (datetime.utcnow() + timedelta(days=1)).isoformat()

    return {
        "message": chat_response,
        "session_expiry_time": new_session_expiry_time
    }


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
