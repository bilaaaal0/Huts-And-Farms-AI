import os
import requests
from dotenv import load_dotenv

load_dotenv()
NOCO_API_TOKEN = os.getenv("NOCO_API_TOKEN")  # directly load the token
HEADERS = {
    "xc-token": NOCO_API_TOKEN
}
NOCO_BASE_URL = os.getenv("NOCO_BASE_URL") 
NOCO_EMAIL = os.getenv("NOCO_EMAIL")
NOCO_PASSWORD = os.getenv("NOCO_PASSWORD")

def get_token():
    if NOCO_API_TOKEN:
      return NOCO_API_TOKEN  # Use static token
   

