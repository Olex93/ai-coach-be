from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from datetime import datetime, timedelta

# Initialize LangChain memory with a size suitable for a 1-day session
memory = ConversationBufferMemory(max_memory_size=10000)

# Track the session start time
session_start_time = datetime.utcnow()

# Initialize ChatGPT model
chat_model = ChatOpenAI(model_name="gpt-4", openai_api_key="YOUR_OPENAI_API_KEY")


def is_session_expired():
    global session_start_time
    # Check if the session has lasted more than 1 day
    return datetime.utcnow() - session_start_time > timedelta(days=1)


def reset_session():
    global session_start_time, memory
    session_start_time = datetime.utcnow()
    memory = ConversationBufferMemory(max_memory_size=10000)  # Reinitialize memory


def add_message_to_memory(role, content):
    memory.add(role=role, content=content)


async def generate_response(prompt, include_initial_context=False, initial_context=""):
    if include_initial_context:
        full_prompt = f"{initial_context}\n\n{prompt}"
    else:
        full_prompt = prompt

    response = await chat_model.agenerate([full_prompt])
    return response["choices"][0]["message"]["content"]


def summarize_conversation():
    # Example summarization logic (customize as needed)
    summary = memory.summarize()
    return summary


def get_initial_context(user_data, workout_history):
    user_personal_data = (
        f"User's personal data:\n"
        f"Age: {user_data['age']}\n"
        f"Weight: {user_data['weight']} kg\n"
        f"Height: {user_data['height']} cm\n"
        f"Gender: {user_data['gender']}\n"
        f"Goals: {user_data['goals']}\n"
    )

    initial_context_prompt = (
        "You are a fitness coach and expert data analyst.\n"
        f"{user_personal_data}\n\n"
        f"{workout_history}\n\n"
    )

    return initial_context_prompt
