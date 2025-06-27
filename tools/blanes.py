from langchain.tools import tool
import httpx

BASEURL = "https://dbapi.escalarmedia.com/api/front/v1"

@tool("list_blanes")
def blanes_list() -> str:
    """
    Lists all active Blanes using the provided token.
    Returns a readable list with name, price, and ID.
    """
    url = f"{BASEURL}/blanes"

    headers = {
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

def get_total_price(blane_id: int):
    url = f"{BASEURL}/blanes"

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        blanes = response.json()

        # Find the blane with matching ID
        blane = next((b for b in blanes if b["id"] == blane_id), None)

        if not blane:
            return None

        return blane['price_current']

    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"❌ Error fetching blane: {str(e)}"

def set_client_id(session_id: str, client_id: int) -> str:
    """
    Associates client_id with a session.
    """
    with SessionLocal() as db:
        # Fetch the session
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            return f"Session {session_id} not found."

        # Set client_email and commit
        session.client_id = client_id
        db.commit()

    return f"Set {client_id} for session {session_id}"

def get_client_id(client_email: str) -> str:
    """
    gets client_id associated with client_email
    """
    client_id = None
    with SessionLocal() as db:
        # Fetch the session
        session = db.query(Session).filter(Session.client_email == client_email).first()
        if not session:
            return f"Email {client_email} not found."

        # Set client_email and commit
        client_id = session.client_id

    return client_id


@tool("create_reservation")
def create_reservation(session_id: str, blane_id: int, name: str, email:str, phone: str, city: str, date: str, end_date: str, time: str, comments: str = "", quantity: int, number_persons: int, payment_method: str ) -> str:
    """
    Create a new reservation for a blane.
    Requires blane_id, user's name, email, phone, city of booking, date of booking, end_date, time, comments (if any), quantity of blanes to be booked, number of persons, payment_method
    """
    status: str = "confirmed"
    url = f"{BASEURL}/reservations"
    headers = {
        "Content-Type": "application/json"
    }
    total_price = get_total_price(blane_id)
    if isinstance(total_price, (int, float)) and total_price > 0:
        pass
    else:
        return "Blane not found"
    payload = {
        "blane_id": blane_id,
        "name": name,
        "email": email,
        "phone": phone,
        "city": city,
        "date": date,
        "end_date": end_date,
        "time": time,
        "comments": comments,
        "quantity": quantity,
        "number_persons": number_persons,
        "status": status
        "total_price": total_price,
        "payment_method": payment_method,
        "partiel_price": total_price/2
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        data = response.json()["data"]
        set_client_id(session_id, data['customer']['id'])
        return f"🎉 Reservation confirmed!\nRef: {data}"
        # return f"🎉 Reservation confirmed!\nRef: {data['NUM_RES']}\nDate: {data['date']}\nTime: {data['time']}"
    else:
        return f"❌ Failed to create reservation: {response.text}"


@tool("list_reservations")
def list_reservations(email: str) -> str:
    """
    Get the list of the authenticated user's reservations.
    Requires user's email.
    """
    client_id = get_client_id(email)
    url = f"{BASEURL}/reservations"
    headers = {
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
 