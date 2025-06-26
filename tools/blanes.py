from langchain.tools import tool
import httpx

BASEURL = "dbapi.escalarmedia.com/api"

@tool("list_blanes")
def blanes_list() -> str:
    """
    Lists all active Blanes using the provided token.
    Returns a readable list with name, price, and ID.
    """
    url = f"https://{BASEURL}/front/v1/blanes"  # Replace with real base URL

    headers = {
       # "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    params = {
        "status": "active",
        "sort_by": "created_at",
        "sort_order": "desc",
        "pagination_size": 10  # or any size you want
    }

    try:
        response = httpx.get(url, headers=headers, params=params)
        response.raise_for_status()
        blanes = response.json().get("data", [])

        if not blanes:
            return "No blanes found."

        output = []
        for i, blane in enumerate(blanes, start=1):
            output.append(f"{i}. {blane['name']} — Rs. {blane['price_current']} (ID: {blane['id']})")

        return "\n".join(output)

    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"❌ Error fetching blanes: {str(e)}"


from langchain.tools import tool
import requests

@tool("create_reservation")
def create_reservation(token: str, blane_id: int, date: str, time: str, status: str = "confirmed") -> str:
    """
    Create a new reservation for a blane.
    Requires user's access token, blane ID, date, and time.
    """
    url = f"https://{BASEURL}/front/v1/reservations"
    headers = {
        #"Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "blane_id": blane_id,
        "date": date,
        "time": time,
        "status": status
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        data = response.json()["data"]
        return f"🎉 Reservation confirmed!\nRef: {data['NUM_RES']}\nDate: {data['date']}\nTime: {data['time']}"
    else:
        return f"❌ Failed to create reservation: {response.text}"


@tool("list_reservations")
def list_reservations(email: str) -> str:
    """
    Get the list of the authenticated user's reservations.
    Requires user's email.
    """
    url = f"https://{BASEURL}/front/v1/reservations"
    headers = {
        #"Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "include": "blane",
        "sort_by": "date",
        "sort_order": "asc"
    }
    payload = {
        "email": email
    }

    response = requests.get(url, json=payload, headers=headers, params=params)

    if response.status_code != 200:
        return f"❌ Failed to fetch reservations: {response.text}"

    data = response.json()["data"]
    if not data:
        return "📭 You have no reservations at the moment."

    message = "📋 Your Reservations:\n"
    for res in data:
        message += f"- Ref: {res['NUM_RES']} | Blane ID: {res['blane_id']} | {res['date']} at {res['time']} ({res['status']})\n"

    return message.strip()
 