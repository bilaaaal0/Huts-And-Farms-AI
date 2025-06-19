from langchain_core.tools import tool
import requests
import os
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("NOCODB_BASE_URL")
TOKEN = os.getenv("NOCODB_API_TOKEN") 

headers = {
    "accept": "application/json",
    "xc-token": TOKEN
}

# @tool("check_reservation_by_client")
# def check_reservation_by_client(client_name: str) -> str:
#     """
#     Check if any reservation exists for a specific client name.
#     """
#     table_id = "mb92g41bhfubow2"  # Booking-Reservation table ID
#     url = f"{BASE_URL}/api/v2/tables/{table_id}/records?where=(Nom%20Client,eq,{client_name})"

#     response = requests.get(url, headers=headers)
    
#     if response.status_code != 200:
#         return f"Failed to fetch data. Status code: {response.status_code}"

#     records = response.json().get("list", [])
#     if not records:
#         return f"No reservations found for {client_name}."
    
#     # Customize the info you want to return
#     return f"Found {len(records)} reservation(s) for {client_name}. Example: ID Réservation = {records[0].get('ID Réservation')}"



@tool
def check_reservation_by_email(email: str, question: str) -> str:
    """
    Checks reservations by filtering rows using the provided email.
    Responds only using data related to the client's email.
    """

    url = f"{BASE_URL}/api/v2/db/data/v1/your_project/Booking-Reservation"
    headers = {"xc-token": TOKEN}
    params = {"where": f"Email Client,eq,{email}"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return f"Failed to fetch reservations for {email}."

    data = response.json().get("list", [])
    if not data:
        return f"No reservations found for {email}."

    # Handle known question patterns
    if "upcoming" in question.lower():
        bookings = [r for r in data if r.get("Réservation Statut", "").lower() in ["client confirmed", "pending"]]
        if bookings:
            return f"Upcoming reservation ID: {bookings[0].get('ID Réservation')} on {bookings[0].get('jour de booking')}"
        else:
            return "No upcoming reservations found."
    
    elif "total amount" in question.lower():
        total = [r.get("Prix final total TTC") for r in data if r.get("Prix final total TTC")]
        return f"Total amounts: {', '.join(total)}" if total else "No price data available."

    else:
        return f"Found {len(data)} reservation(s) for {email}. Please specify what info you want."

