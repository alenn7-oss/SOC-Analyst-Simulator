import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="You are a panicked, non-technical employee whose work computer "
             "might have been hacked. In one short sentence, ask your IT team what's going on."
)

print(response.text)
