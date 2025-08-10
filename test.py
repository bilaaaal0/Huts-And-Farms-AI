import requests

def send_whatsapp_message(access_token, phone_number_id, to_number, message):
    """
    Send a WhatsApp text message using the WhatsApp Business Cloud API.

    :param access_token: Your permanent or temporary WhatsApp Cloud API token
    :param phone_number_id: The Phone Number ID from WhatsApp Manager
    :param to_number: Recipient phone number in international format without '+'
    :param message: Text message to send
    """
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message}
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        print("Message sent successfully:", response.json())
    else:
        print("Failed to send message:", response.status_code, response.text)


# Example usage:
ACCESS_TOKEN = "EAAZANH8gcmGsBPBR0wcBdw5iCavXKYWrjF9MZB5xg1xDRNvZCOKvGZA0h9pFZCNXLf1sIDH7Yg4U4TBpNORobqieCZAufKo6G8wEwIDVrMkAgHqSx87YbZAVUHwZAghhvNf5Ytkow1RQgqiFOpCCDLZC2xteliCgyXhPgJI3VZBTjIBJtda745PomihkKqXKWoY7qfkwZDZD"
PHONE_NUMBER_ID = "787517121101314"
TO_NUMBER = "923312844594"

send_whatsapp_message(
    access_token=ACCESS_TOKEN,
    phone_number_id=PHONE_NUMBER_ID,
    to_number=TO_NUMBER,
    message="Hello from WhatsApp Cloud API!"
)
