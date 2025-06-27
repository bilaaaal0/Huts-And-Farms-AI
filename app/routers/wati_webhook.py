from fastapi import APIRouter, Request
import os
import httpx
from dotenv import load_dotenv
from datetime import datetime
from app.agent.booking_agent import BookingToolAgent
from app.database import SessionLocal
from app.chatbot.models import Session as SessionModel, Message
from fastapi.responses import PlainTextResponse

load_dotenv()

router = APIRouter()
agent = BookingToolAgent()

VERIFY_TOKEN = "my_custom_secret_token"
WHATSAPP_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")

print(f"Whatsapp token : {WHATSAPP_TOKEN}")


@router.get("/meta-webhook")
def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge"))
    return PlainTextResponse("Invalid token", status_code=403)


@router.post("/meta-webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("📩 Incoming:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if not messages:
            return {"status": "ignored"}

        wa_id = messages[0]["from"]
        text = messages[0]["text"]["body"]
        session_id = wa_id

        db = SessionLocal()

        # --- Check for existing session ---
        session = db.query(SessionModel).filter_by(id=session_id).first()

        if not session:
            session = SessionModel(
                id=session_id,
                whatsapp_number=wa_id  # Save sender number
            )
            db.add(session)
            db.commit()

        # --- Save user message ---
        db.add(Message(
            session_id=session_id,
            sender="user",
            content=text,
            timestamp=datetime.utcnow()
        ))
        db.commit()

        # --- Get bot reply ---
        response = agent.get_response(incoming_text=text, session_id=session_id)

        # --- Save bot response ---
        db.add(Message(
            session_id=session_id,
            sender="bot",
            content=response,
            timestamp=datetime.utcnow()
        ))
        db.commit()
        db.close()

        print(f"🤖 Agent Reply: {response}")
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
