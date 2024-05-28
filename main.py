import json

from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from authentication import validate_request_and_user, create_access_token, encrypt_email, verify_password, \
    generate_verification_code, hash_password
from database import get_user_from_database, create_database_and_tables, save_verification_code, \
    get_verification_code, create_user_in_database, verify_user_in_database, update_user_details, save_workout_log, \
    get_formatted_workout_data
from openai import get_json_from_notes, get_chatgpt_response
from models import UserWorkoutNotesInput, UserCreate, EmailVerificationInput, UserDetailsUpdate
from utils.email_utils import send_verification_email

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
bearer_scheme = HTTPBearer()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

create_database_and_tables()


@app.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5 per minute")
async def register_user(user: UserCreate):
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
async def verify_user(input: EmailVerificationInput):
    stored_code = get_verification_code(input.email)
    if stored_code != input.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    verify_user_in_database(input.email)
    encrypted_email = encrypt_email(input.email)
    access_token = create_access_token(
        data={"sub": encrypted_email}, expires_delta=None  # long-lived token
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
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
async def update_personal_details(details: UserDetailsUpdate, user: dict = Depends(validate_request_and_user)):
    update_user_details(user["email"], details.height, details.weight, details.age, details.gender, details.goals)
    return {"msg": "Personal details updated successfully"}


@app.post("/save-workout")
async def save_workout(user_workout_input: UserWorkoutNotesInput, user: dict = Depends(validate_request_and_user)):
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

        return {"data": workout_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", status_code=status.HTTP_200_OK)
async def chat_with_gpt(request: Request, user: dict = Depends(validate_request_and_user)):
    data = await request.json()
    user_message = data["message"]
    conversation_history = data.get("conversation_history", [])

    user = get_user_from_database(user["email"])
    user_id = user["user_id"]
    # Get user's personal data
    user_personal_data = (
        f"User's personal data:\n"
        f"Age: {user['age']}\n"
        f"Weight: {user['weight']} kg\n"
        f"Height: {user['height']} cm\n"
        f"Gender: {user['gender']}\n"
        f"Goals: {user['goals']}\n"
    )

    # Get formatted workout data
    workout_history = get_formatted_workout_data(user_id)

    # Construct the conversation prompt with workout data and conversation history
    messages = [
        {"role": "system", "content": "You are a fitness coach and expert data analyst."},
        {"role": "assistant", "content": user_personal_data},
        {"role": "assistant", "content": workout_history},
    ]

    for message in conversation_history:
        messages.append({"role": message["role"], "content": message["content"]})

    messages.append({"role": "user", "content": user_message})

    # Send the prompt to ChatGPT
    chat_response = get_chatgpt_response(messages)

    # Append the new messages to the conversation history
    conversation_history.append({"role": "user", "content": user_message})
    conversation_history.append({"role": "assistant", "content": chat_response})

    return {"message": chat_response, "conversation_history": conversation_history}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
