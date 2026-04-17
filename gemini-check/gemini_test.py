from dotenv import load_dotenv

load_dotenv()  # Reads variables from .env file in the same directory or higher

# Access variables as if they came from the actual environment
import os
api_key = os.getenv('GEMINI_API_KEY')

from google import genai

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3.1-flash-lite-preview",
    contents="Explain how AI works in a few words"
)
print(response.text)


chat = client.chats.create(model="gemini-3.1-flash-lite-preview")

response = chat.send_message("Explain to me why the sky is blue")
print(response.text)

for message in chat.get_history():
    print(f'role - {message.role}',end=": ")
    print(message.parts[0].text)