import requests

NOCO_BASE_URL = "https://database.dabablane.com"
NOCO_API_TOKEN = "PvRd94S5nqUOtplcdu4ZDq-4O45TGuls72CAekYT"
HEADERS = {"xc-token": NOCO_API_TOKEN}

# From your Swagger image
TABLES = {
    "Booking-Reservation": "mb92g41bhfubow2",
    "Order-Command": "mwl1c7if8k4wfzdt"
}

def fetch_data_and_columns(table_id, table_name, limit=3):
    url = f"{NOCO_BASE_URL}/api/v2/tables/{table_id}/records?limit={limit}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()

    records = data.get("list", [])
    print(f"\n===== {table_name} ({table_id}) =====")
    if not records:
        print("No data found.")
        return

    # Infer columns from first record
    first = records[0]
    print("Columns:")
    for key in first.keys():
        print(f" - {key}")

    print("\nSample Data:")
    for record in records:
        print(record)

def run_test():
    for table_name, table_id in TABLES.items():
        fetch_data_and_columns(table_id, table_name)


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
    url = f"{NOCO_BASE_URL}/v1/auth/login"
    response = requests.post(url, json={"email": NOCO_EMAIL, "password": NOCO_PASSWORD})
    response.raise_for_status()

    token = response.json()["token"]
    print(f"🔑 Token fetched from login: {token}")
    return token




if __name__ == "__main__":
    get_token()
