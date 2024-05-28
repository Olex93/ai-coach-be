import requests
from config import settings

OPENAI_API_KEY = settings.OPENAI_API_KEY


def get_json_from_notes(notes: str):
    prompt = f"Transform the following workout notes into JSON format with the headers: Workout ID, Date, Time, Exercise, Set ID, Reps, Is Dropset, Duration, Calories.\n\nNotes:\n{notes}"
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are an assistant that transforms workout notes into JSON format."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    response_data = response.json()
    json_output = response_data['choices'][0]['message']['content']
    return json_output


def get_chatgpt_response(messages: list):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": messages,
        "temperature": 0.5
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    response_data = response.json()
    return response_data['choices'][0]['message']['content']
