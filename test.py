import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
	print("⚠️ GEMINI_API_KEY not set; skipping Gemini test. Set GEMINI_API_KEY in your .env to run this test.")
else:
	genai.configure(api_key=api_key)
	# Use the latest supported model
	model = genai.GenerativeModel("gemini-2.5-flash")
	response = model.generate_content("Hello Gemini, just test.")
	print(response.text)
