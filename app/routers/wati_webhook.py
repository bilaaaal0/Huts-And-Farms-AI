from fastapi import APIRouter, Request
import os
import httpx
from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.agent.booking_agent import BookingToolAgent
from app.database import SessionLocal
from app.chatbot.models import Session as SessionModel, Message, User
from fastapi.responses import PlainTextResponse
from app.format_message import formatting
from sqlalchemy import and_
import uuid
import re
from typing import List, Optional, Dict
from app.agent.admin_agent import AdminAgent
import cloudinary
import cloudinary.uploader
from cloudinary.uploader import upload as cloudinary_upload
import requests

load_dotenv()

from .utility import is_hourly_messages_limit_exceeded, is_hourly_token_limit_exceeded


router = APIRouter()
agent = BookingToolAgent()
admin_agent = AdminAgent()
VERIFY_TOKEN = "my_custom_secret_token"
WHATSAPP_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")

def get_or_create_user(wa_id: str, db) -> str:
    user = db.query(User).filter_by(phone_number=wa_id).first()
    if user:
        return user.user_id
    user_id = str(uuid.uuid4())
    new_user = User(user_id=user_id, phone_number=wa_id,created_at=datetime.utcnow())
    db.add(new_user)
    db.commit()
    return user_id
def get_or_create_session(user_id: str, db) -> str:
    session = db.query(SessionModel).filter_by(user_id=user_id).first()
    if session:
        return session.id

    session_id = str(uuid.uuid4())
    new_session = SessionModel(id=session_id, user_id=user_id)
    db.add(new_session)
    db.commit()
    return session_id

def remove_cloudinary_links(text: str) -> str:
    # Pattern to match cloudinary image and video links
    pattern = r"https?://res\.cloudinary\.com/[^\s]+(?:\.jpg|\.jpeg|\.png|\.mp4)"
    
    # Remove matched links
    cleaned_text = re.sub(pattern, '', text)
    
    # Optional: remove empty lines or extra spaces left behind
    cleaned_text = '\n'.join([line.strip() for line in cleaned_text.splitlines() if line.strip()])
    
    return cleaned_text

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


cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)
# @router.post("/meta-webhook")
# async def receive_message(request: Request):
#     data = await request.json()
#     print("📩 Incoming:", data)

#     db = SessionLocal()
#     try:
#         entry = data["entry"][0]
#         changes = entry["changes"][0]
#         value = changes["value"]
#         messages = value.get("messages")

#         if not messages:
#             return {"status": "ignored"}

#         wa_id = messages[0]["from"]
        

#         # Check for duplicate using WhatsApp message ID
#         whatsapp_msg_id = messages[0].get("id", "")
#         if whatsapp_msg_id:
#             existing = db.query(Message).filter(
#                 Message.whatsapp_message_id == whatsapp_msg_id
#             ).first()
#             if existing:
#                 print(f"🔄 Message already processed: {whatsapp_msg_id}")
#                 return {"status": "already_processed"}


#         user_id = get_or_create_user(wa_id, db)
#         print(f"User ID for {wa_id}: {user_id}")
#         session_id = get_or_create_session(user_id, db)

#         if messages[0].get("type") == "image":
#             print("📸 Received image message")
#             payment_details = agent.get_response(incoming_text="Image received run process_payment_screenshot", session_id=session_id, whatsapp_msg_id=whatsapp_msg_id)
#             # Save image metadata to database
            
#             if payment_details is not False:
#                 media_id = messages[0]["image"]["id"]
#                 media_url_response = requests.get(
#                     f"https://graph.facebook.com/v19.0/{media_id}",
#                     headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
#                 )
#                 media_url = media_url_response.json().get("url")

#                 # 2. Download the actual image binary
#                 image_response = requests.get(
#                     media_url,
#                     headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
#                 )
                
#                 # 3. Upload to Cloudinary
#                 result = cloudinary_upload(image_response.content)
#                 image_url = result["secure_url"] 

#                 # Send notification to admin
#                 cloudinary_dict = {
#                     "images": [image_url],
#                 }
#                 # Save bot message
#                 content = "Payment SS URL : " + image_url
#                 embedding_user = agent.get_embedding(content)
#                 db.add(Message(
#                     user_id=user_id,
#                     sender="user",
#                     content=content,
#                     whatsapp_message_id=whatsapp_msg_id,
#                     query_embedding=embedding_user,
#                     timestamp=datetime.utcnow()
#                 ))
#                 db.commit()
#                 print(payment_details)
#                 await send_whatsapp_message("923155699929", payment_details, cloudinary_dict)
#                 print(f"Details send to admin")

#                 return {"status": "uploaded", "cloudinary_url": image_url}
#             else:
#                 return {"status": "error", "message": "Please send only payment screenshots not any other image"}

#         elif messages[0].get("type") == "text":
            
            
#             text = messages[0]["text"]["body"]

            

#             if wa_id == "923155699929":
#                 print("Received message from admin")
                
#                 admin_bot_answer = admin_agent.get_response(text, session_id)
#                 session = db.query(SessionModel).filter_by(id=session_id).first()
#                 customer_phone = session.user.phone_number
#                 await send_whatsapp_message(customer_phone, admin_bot_answer)
#                 return {"status": "ok"}

            
#             # Get bot reply
#             response = agent.get_response(incoming_text=text, session_id=session_id,whatsapp_message_id=whatsapp_msg_id)

#             # Extract response content
#             if isinstance(response, dict):
#                 if 'output' in response and isinstance(response['output'], dict):
#                     message_content = response['output'].get('message', '')
#                     error_content = response['output'].get('error', '')
#                     response_text = message_content or error_content or str(response)
#                 else:
#                     response_text = response.get('message', '') or response.get('error', '') or str(response)
#             else:
#                 response_text = str(response)

#             # Format response
#             formatted_response = formatting(response_text)
#             urls = extract_media_urls(formatted_response)

#             # Prepare final message content
#             if urls:
#                 cleaned_response = remove_cloudinary_links(formatted_response)
#                 final_message_content = cleaned_response
#                 display_message = cleaned_response + "\n\n*Media files sent separately.*"
#             else:
#                 final_message_content = formatted_response
#                 display_message = formatted_response

#             # Save bot message
#             embedding_bot = agent.get_embedding(final_message_content)
#             bot_whatsapp_id = response.json()["messages"][0]["id"]
#             db.add(Message(
#                 user_id=user_id,
#                 sender="bot",
#                 content=final_message_content,
#                 whatsapp_message_id=bot_whatsapp_id,
#                 query_embedding=embedding_bot,
#                 timestamp=datetime.utcnow()
#             ))
#             db.commit()

#             # Send WhatsApp message
#             await send_whatsapp_message(wa_id, display_message, urls)

#     except Exception as e:
#         print("❌ Error in webhook:", e)
#         import traceback
#         print("❌ Full traceback:", traceback.format_exc())
#     finally:
#         db.close() 

#     return {"status": "ok"}


# async def send_whatsapp_message(recipient_number: str, message: str, media_urls: Dict[str, List[str]] = None):
#     url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
#     headers = {
#         "Authorization": f"Bearer {WHATSAPP_TOKEN}",
#         "Content-Type": "application/json"
#     }

#     # If media_urls are provided, send media first, then text
#     if media_urls:
#         # Send each media file
#         for media_type, urls in media_urls.items():
#             for media_url in urls:
#                 print(f"Sending {media_type[:-1]} to {recipient_number}: {media_url}")
                
#                 # Convert 'images' to 'image' and 'videos' to 'video' for WhatsApp API
#                 whatsapp_media_type = media_type[:-1]  # Remove 's' from 'images'/'videos'
                
#                 media_payload = {
#                     "messaging_product": "whatsapp",
#                     "to": recipient_number,
#                     "type": whatsapp_media_type,
#                     whatsapp_media_type: {
#                         "link": media_url
#                     }
#                 }
                
#                 async with httpx.AsyncClient() as client:
#                     response = await client.post(url, json=media_payload, headers=headers)
#                     if response.status_code != 200:
#                         print(f"❌ Failed to send {whatsapp_media_type}: {response.text}")
#                     else:
#                         print(f"✅ {whatsapp_media_type.title()} sent")

#         # Send text message after media if there's text content
#         if message.strip():
#             text_payload = {
#                 "messaging_product": "whatsapp",
#                 "to": recipient_number,
#                 "type": "text",
#                 "text": {"body": message}
#             }
            
#             async with httpx.AsyncClient() as client:
#                 text_response = await client.post(url, json=text_payload, headers=headers)
#                 if text_response.status_code != 200:
#                     print(f"❌ Failed to send text: {text_response.text}")
#                 else:
#                     print("✅ Text message sent")
#     else:
#         # Send only text message
#         text_payload = {
#             "messaging_product": "whatsapp",
#             "to": recipient_number,
#             "type": "text",
#             "text": {"body": message}
#         }
        
#         async with httpx.AsyncClient() as client:
#             response = await client.post(url, json=text_payload, headers=headers)
#             if response.status_code != 200:
#                 print(f"❌ Failed to send text: {response.text}")
#             else:
#                 print("✅ Text message sent")

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
        
        # Get USER's WhatsApp message ID
        user_whatsapp_msg_id = messages[0].get("id", "")
        if user_whatsapp_msg_id:
            existing = db.query(Message).filter(
                Message.whatsapp_message_id == user_whatsapp_msg_id
            ).first()
            if existing:
                print(f"🔄 Message already processed: {user_whatsapp_msg_id}")
                return {"status": "already_processed"}

        user_id = get_or_create_user(wa_id, db)
        print(f"User ID for {wa_id}: {user_id}")
        session_id = get_or_create_session(user_id, db)

        if messages[0].get("type") == "image":
            print("📸 Received image message")
            payment_details = agent.get_response(
                incoming_text="Image received run process_payment_screenshot", 
                session_id=session_id, 
                whatsapp_message_id=user_whatsapp_msg_id
            )
            
            if payment_details is not False:
                media_id = messages[0]["image"]["id"]
                media_url_response = requests.get(
                    f"https://graph.facebook.com/v23.0/{media_id}",
                    headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                )
                media_url = media_url_response.json().get("url")

                # Download the actual image binary
                image_response = requests.get(
                    media_url,
                    headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                )
                
                # Upload to Cloudinary
                result = cloudinary_upload(image_response.content)
                image_url = result["secure_url"] 

                # Save USER message (image metadata) with USER's WhatsApp ID
                content = "Payment SS URL : " + image_url
                embedding_user = agent.get_embedding(content)
                db.add(Message(
                    user_id=user_id,
                    sender="user",
                    content=content,
                    whatsapp_message_id=user_whatsapp_msg_id,  # USER's WhatsApp ID
                    query_embedding=embedding_user,
                    timestamp=datetime.utcnow()
                ))
                db.commit()
                
                # Send notification to admin (this will be handled by the tool)
                cloudinary_dict = {
                    "images": [image_url],
                }
                
                # Send admin notification and get WhatsApp response
                admin_response = await send_whatsapp_message("923155699929", payment_details, cloudinary_dict)
                
                # Save BOT message with ADMIN's WhatsApp message ID (if needed)
                if admin_response and hasattr(admin_response, 'json'):
                    admin_whatsapp_id = admin_response.json().get("messages", [{}])[0].get("id", "")
                    if admin_whatsapp_id:
                        # Note: This saves to the user's conversation, you might want to create separate admin conversation
                        embedding_bot = agent.get_embedding(payment_details)
                        db.add(Message(
                            user_id=user_id,
                            sender="bot",
                            content=payment_details,
                            whatsapp_message_id=admin_whatsapp_id,
                            query_embedding=embedding_bot,
                            timestamp=datetime.utcnow()
                        ))
                        db.commit()
                
                print(f"Details sent to admin")
                return {"status": "uploaded", "cloudinary_url": image_url}
            else:
                return {"status": "error", "message": "Please send only payment screenshots not any other image"}

        elif messages[0].get("type") == "text":
            text = messages[0]["text"]["body"]

            if wa_id == "923155699929":
                print("Received message from admin")
                
                admin_bot_answer = admin_agent.get_response(text, session_id)
                session = db.query(SessionModel).filter_by(id=session_id).first()
                customer_phone = session.user.phone_number
                customer_user_id = session.user.user_id
                
                # Send message to customer and get WhatsApp response
                whatsapp_response = await send_whatsapp_message(customer_phone, admin_bot_answer)
                
                # Save admin's bot message with proper WhatsApp ID
                if whatsapp_response and hasattr(whatsapp_response, 'json'):
                    bot_whatsapp_id = whatsapp_response.json().get("messages", [{}])[0].get("id", "")
                    if bot_whatsapp_id:
                        # embedding_bot = admin_agent.get_embedding(admin_bot_answer)
                        db.add(Message(
                            user_id=customer_user_id,
                            sender="bot",
                            content=admin_bot_answer,
                            whatsapp_message_id=bot_whatsapp_id,
                            # query_embedding=embedding_bot,
                            timestamp=datetime.utcnow()
                        ))
                        db.commit()
                
                return {"status": "ok"}

            # Get bot reply (this returns a STRING, not HTTP response)
            agent_response = agent.get_response(
                incoming_text=text, 
                session_id=session_id, 
                whatsapp_message_id=user_whatsapp_msg_id
            )

            # Extract response content from agent's string response
            if isinstance(agent_response, dict):
                if 'output' in agent_response and isinstance(agent_response['output'], dict):
                    message_content = agent_response['output'].get('message', '')
                    error_content = agent_response['output'].get('error', '')
                    response_text = message_content or error_content or str(agent_response)
                else:
                    response_text = agent_response.get('message', '') or agent_response.get('error', '') or str(agent_response)
            else:
                response_text = str(agent_response)

            # Format response
            formatted_response = formatting(response_text)
            urls = extract_media_urls(formatted_response)

            # Prepare final message content
            if urls:
                cleaned_response = remove_cloudinary_links(formatted_response)
                final_message_content = cleaned_response
                display_message = cleaned_response + "\n\n*Media files sent separately.*"
            else:
                final_message_content = formatted_response
                display_message = formatted_response

            # Send WhatsApp message FIRST to get the WhatsApp message ID
            whatsapp_response = await send_whatsapp_message(wa_id, display_message, urls)
            
            # Extract bot's WhatsApp message ID from the WhatsApp API response
            bot_whatsapp_id = None
            if whatsapp_response and hasattr(whatsapp_response, 'json'):
                response_json = whatsapp_response.json()
                bot_whatsapp_id = response_json.get("messages", [{}])[0].get("id", "")
            
            # Save bot message with proper WhatsApp ID
            # embedding_bot = agent.get_embedding(final_message_content)
            db.add(Message(
                user_id=user_id,
                sender="bot",
                content=final_message_content,
                whatsapp_message_id=bot_whatsapp_id,  # BOT's WhatsApp ID from API response
                # query_embedding=embedding_bot,
                timestamp=datetime.utcnow()
            ))
            db.commit()

    except Exception as e:
        print("❌ Error in webhook:", e)
        import traceback
        print("❌ Full traceback:", traceback.format_exc())
    finally:
        db.close() 

    return {"status": "ok"}


# You'll also need to modify your send_whatsapp_message function to return the response
async def send_whatsapp_message(recipient_number: str, message: str, media_urls: Dict[str, List[str]] = None):
    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"
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
                
                return text_response  # Return the response object
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
            
            return response  # Return the response object