import google.generativeai as genai
import os
from dotenv import load_dotenv

# load .env file
load_dotenv()

# read API key
api_key = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=api_key)

for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print(model.name)