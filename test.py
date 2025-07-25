import google.generativeai as genai
import os

# Set your API key
genai.configure(api_key="AIzaSyByWBo2X2EIw2GzcXgxhw_0_6j0PELvFOc")

try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Hello!")
    print("✅ API Key is valid.")
    print("Response:", response.text)
except Exception as e:
    print("❌ API Key may be invalid or has issues.")
    print(e)
