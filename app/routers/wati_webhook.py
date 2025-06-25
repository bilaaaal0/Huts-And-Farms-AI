# app/routers/meta_webhook.py
from fastapi import APIRouter, Request
import os
import httpx
from dotenv import load_dotenv
# app/routers/meta_webhook.py
from fastapi import APIRouter, Request
from app.agent.booking_agent import BookingToolAgent
from app.database import SessionLocal
from app.chatbot.models import Session as SessionModel, Message
from datetime import datetime

from app.agent.booking_agent import BookingToolAgent  # ✅ Make sure this works

load_dotenv()


router = APIRouter()
agent = BookingToolAgent()

VERIFY_TOKEN = "my_custom_secret_token"
WHATSAPP_TOKEN = "EAAZANH8gcmGsBO3LaIpAc22ePIJWqOi0GT5j71NiUZAFgQZC0i27fPmAbsUPG2aLMuSMVb1517rbcq4C3TeveoumRPPsZCPZAiAm5xqUlziNZBDGXtw8odfNLczab2O5wU8n8Xs2ixWluFSjgEnkGrGZBqqxjf6HIGPa69NsXbpJOj5E581uNDy3HA4vsevniXRFwkMNSXWXMfTzs8oeLSC5iMP3H2aATbsZCC9bEE201gqSkgZDZD"
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")

print(f"Whatsapp token : {WHATSAPP_TOKEN}")


@router.get("/meta-webhook")
def verify_webhook(request: Request):
    """
    Verifies webhook with Meta (first time setup).
    """
    from fastapi.responses import PlainTextResponse
    params = request.query_params
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge"))
    return PlainTextResponse("Invalid token", status_code=403)





@router.post("/meta-webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("📩 Incoming:", data)

    try:
        # Extract WhatsApp phone number and message
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if not messages:
            return {"status": "ignored"}

        wa_id = messages[0]["from"]  # phone number
        text = messages[0]["text"]["body"]
        session_id = wa_id  # Use wa_id as session_id

        # --- Ensure session exists ---
        db = SessionLocal()
        session = db.query(SessionModel).filter_by(id=session_id).first()
        if not session:
            session = SessionModel(id=session_id)
            db.add(session)
            db.commit()

        # --- Save user message ---
        db.add(Message(session_id=session_id, sender="user", content=text, timestamp=datetime.utcnow()))
        db.commit()

        # --- Get response ---
        response = agent.get_response(incoming_text=text, session_id=session_id)

        # --- Save bot message ---
        db.add(Message(session_id=session_id, sender="bot", content=response, timestamp=datetime.utcnow()))
        db.commit()
        db.close()

        # --- Send reply (Optional if you add sending here) ---
        print(f"🤖 Agent Reply: {response}")
         # ✅ Send the response back to the user
        await send_whatsapp_message(wa_id, response)

    except Exception as e:
        print("❌ Error in webhook:", e)

    return {"status": "ok"}


async def send_whatsapp_message(recipient_number: str, message: str):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "text",
        "text": {"body": message}
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print("❌ Failed to send:", response.text)
