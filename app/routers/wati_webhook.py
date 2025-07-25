from fastapi import APIRouter, Request
import os
import httpx
from dotenv import load_dotenv
from datetime import datetime
from app.agent.booking_agent import BookingToolAgent
from app.database import SessionLocal
from app.chatbot.models import Session as SessionModel, Message
from fastapi.responses import PlainTextResponse
from app.format_message import formatting

import re
from typing import List, Optional, Dict

load_dotenv()

router = APIRouter()
agent = BookingToolAgent()

VERIFY_TOKEN = "my_custom_secret_token"
WHATSAPP_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")




def extract_media_urls(text: str) -> Optional[Dict[str, List[str]]]:
    """
    Extracts all media URLs from a given text block.
    Returns a dictionary with 'images' and 'videos' keys.
    """
    pattern = r"https://[^\s]+"
    urls = re.findall(pattern, text)

    if not urls:
        return None

    media = {
        "images": [],
        "videos": []
    }

    for url in urls:
        if "/image/" in url:
            media["images"].append(url)
        elif "/video/" in url:
            media["videos"].append(url)

    return media if media["images"] or media["videos"] else None


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

    db = SessionLocal()
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

        # --- Check for existing session ---
        session = db.query(SessionModel).filter_by(id=session_id).first()

        if not session:
            session = SessionModel(
                id=session_id,
                whatsapp_number=wa_id
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
        
        # formatted response
        response = formatting(response)
        print(response)
        print(type(response))

        urls = extract_media_urls(response)

        # --- Save bot response ---
        db.add(Message(
            session_id=session_id,
            sender="bot",
            content=response,
            timestamp=datetime.utcnow()
        ))
        db.commit()

        print(f"🤖 Agent Reply: {response}")
        if urls:
            print(f"📸 Media URLs: {urls}")
            # Send media with the text message
            media_message = "Here are the media you requested."
            await send_whatsapp_message(wa_id, media_message, urls)
        else:
            # Send only text message if no media
            await send_whatsapp_message(wa_id, response)

    except Exception as e:
        print("❌ Error in webhook:", e)

    finally:
        db.close() 

    return {"status": "ok"}


async def send_whatsapp_message(recipient_number: str, message: str, media_urls: Dict[str, List[str]] = None):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    # If media_urls are provided, send media first, then text
    if media_urls:
        # Send each media file
        for media_type, urls in media_urls.items():
            for media_url in urls:
                print(f"Sending {media_type[:-1]} to {recipient_number}: {media_url}")
                
                # Convert 'images' to 'image' and 'videos' to 'video' for WhatsApp API
                whatsapp_media_type = media_type[:-1]  # Remove 's' from 'images'/'videos'
                
                media_payload = {
                    "messaging_product": "whatsapp",
                    "to": recipient_number,
                    "type": whatsapp_media_type,
                    whatsapp_media_type: {
                        "link": media_url
                    }
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=media_payload, headers=headers)
                    if response.status_code != 200:
                        print(f"❌ Failed to send {whatsapp_media_type}: {response.text}")
                    else:
                        print(f"✅ {whatsapp_media_type.title()} sent")

        # Send text message after media if there's text content
        if message.strip():
            text_payload = {
                "messaging_product": "whatsapp",
                "to": recipient_number,
                "type": "text",
                "text": {"body": message}
            }
            
            async with httpx.AsyncClient() as client:
                text_response = await client.post(url, json=text_payload, headers=headers)
                if text_response.status_code != 200:
                    print(f"❌ Failed to send text: {text_response.text}")
                else:
                    print("✅ Text message sent")
    else:
        # Send only text message
        text_payload = {
            "messaging_product": "whatsapp",
            "to": recipient_number,
            "type": "text",
            "text": {"body": message}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=text_payload, headers=headers)
            if response.status_code != 200:
                print(f"❌ Failed to send text: {response.text}")
            else:
                print("✅ Text message sent")
