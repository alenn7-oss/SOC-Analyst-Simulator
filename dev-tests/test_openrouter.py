import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": "openrouter/free",
        "messages": [
            {
                "role": "user",
                "content": "You are a panicked, non-technical employee whose work "
                           "computer might have been hacked. In one short sentence, "
                           "ask your IT team what's going on."
            }
        ]
    },
    timeout=20
)

print(response.status_code)
print(response.json())
