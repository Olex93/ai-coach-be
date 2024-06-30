import os
from dotenv import load_dotenv

load_dotenv()

print(os.getenv("OPENAI_API_KEY"))
print(os.getenv("JWT_SECRET_KEY"))
print(os.getenv("FERNET_ENCRYPTION_KEY"))
print(os.getenv("EMAIL_HOST"))
print(os.getenv("EMAIL_PORT"))
print(os.getenv("EMAIL_USERNAME"))
print(os.getenv("EMAIL_PASSWORD"))
print(os.getenv("EMAIL_FROM"))