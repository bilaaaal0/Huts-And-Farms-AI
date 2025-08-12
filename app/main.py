from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from app.routers import wati_webhook
from app.routers import agent 
from app.database import engine
from app.chatbot import models
import httpx
import json
import base64
import logging
import os
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime, timedelta
models.Base.metadata.create_all(bind=engine)

app = FastAPI()



app.include_router(agent.router)  
app.include_router(wati_webhook.router)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
registration_store={}

load_dotenv()

VERIFY_TOKEN = "my_custom_secret_token"
WHATSAPP_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")

def decode_certificate(cert_base64: str) -> dict:
    """
    Decode the base64 certificate to extract vname (display name)
    """
    try:
        decoded_bytes = base64.b64decode(cert_base64)
        # This is a simplified extraction - actual implementation depends on cert format
        # For demo purposes, we'll return a mock display name
        return {"vname": "HutsAndFarms-AI"}
    except Exception as e:
        logger.error(f"Failed to decode certificate: {e}")
        return {"vname": "Unknown"}


async def request_code_from_meta(cc: str, phone_number: str, method: str, cert: str, pin: Optional[str] = None) -> dict:
    """
    Make POST call to Meta's WhatsApp Business API to request registration code
    Meta will send the code directly to the user via SMS/voice
    """
    url = "https://graph.facebook.com/v19.0/account"  # Meta's registration endpoint
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "cc": cc,
        "phone_number": phone_number,
        "method": method,
        "cert": cert
    }
    
    # Add PIN if provided (for 2FA)
    if pin:
        payload["pin"] = pin
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Registration code request sent to Meta for {cc}{phone_number}")
            return result
    except httpx.HTTPError as e:
        logger.error(f"Failed to request code from Meta: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to request verification code: {str(e)}"
        )


async def verify_code_with_meta(code: str) -> bool:
    """
    Make POST call to Meta's WhatsApp Business API to verify registration code
    """
    url = "https://graph.facebook.com/v19.0/account/verify"  # Meta's verification endpoint
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "code": code
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"Code verification successful with Meta")
            return True
    except httpx.HTTPError as e:
        logger.error(f"Failed to verify code with Meta: {e}")
        return False


# def is_code_expired(timestamp: datetime) -> bool:
#     """Check if verification code has expired"""
#     return datetime.now() > timestamp + timedelta(minutes=CODE_EXPIRY_MINUTES)


@app.post("/v1/account")
async def request_registration_code(request: Request):
    """
    Request registration code endpoint
    Returns:
    - 201 Created: Account already exists (already registered)
    - 202 Accepted: Account doesn't exist, registration code sent
    """
    try:
        data = await request.json()
        
        # Validate required fields
        cc = data.get("cc")
        phone_number = data.get("phone_number")
        method = data.get("method", "sms")  # sms or voice
        cert = data.get("cert")
        pin = data.get("pin")  # Required if 2FA is enabled
        
        if not all([cc, phone_number, cert]):
            raise HTTPException(
                status_code=400, 
                detail="Missing required fields: cc, phone_number, cert"
            )
        
        if method not in ["sms", "voice"]:
            raise HTTPException(
                status_code=400,
                detail="Method must be 'sms' or 'voice'"
            )
        
        # Validate phone number format
        if not phone_number.isdigit():
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number format"
            )
        
        # Validate country code format
        if not cc.isdigit() or len(cc) < 1 or len(cc) > 4:
            raise HTTPException(
                status_code=400,
                detail="Invalid country code format"
            )
        
        full_phone = f"{cc}{phone_number}"
        
        # Check if account already exists and is verified
        if full_phone in registration_store and registration_store[full_phone].get("verified"):
            logger.info(f"Account {full_phone} already exists and is verified")
            return JSONResponse(
                status_code=201,
                content={"message": "Account already exists"}
            )
        
        # Decode certificate to get display name
        cert_info = decode_certificate(cert)
        vname = cert_info.get("vname", "Unknown")
        
        # Store registration attempt
        registration_store[full_phone] = {
            "cc": cc,
            "phone_number": phone_number,
            "method": method,
            "cert": cert,
            "pin": pin,
            "vname": vname,
            "verified": False,
            "code_sent": False,
            "created_at": datetime.now()
        }
        
        # Request verification code from Meta
        # Meta will send the code directly to the user
        try:
            meta_response = await request_code_from_meta(cc, phone_number, method, cert, pin)
            
            # Mark as code sent
            registration_store[full_phone]["code_sent"] = True
            
            logger.info(f"Verification code request sent to Meta for {full_phone}")
            
            # Return response according to API specification
            response_data = {
                "account": [{
                    "vname": vname
                }]
            }
            
        except HTTPException:
            # Clean up if Meta request failed
            registration_store.pop(full_phone, None)
            raise
        
        return JSONResponse(
            status_code=202,
            content=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.post("/v1/account/verify")
async def verify_registration_code(request: Request):
    """
    Verify registration code endpoint
    Returns:
    - 201 Created: Registration completed successfully
    - 400 Bad Request: Invalid or expired code
    """
    try:
        data = await request.json()
        
        # Validate required fields
        code = data.get("code")
        
        if not code:
            raise HTTPException(
                status_code=400,
                detail="Missing required field: code"
            )
        
        # Validate code format
        if not (code.isdigit() and len(code) == 6):
            raise HTTPException(
                status_code=400,
                detail="Invalid code format. Code must be 6 digits."
            )
        
        # Find matching registration attempt
        phone_found = None
        for phone, reg_data in registration_store.items():
            if reg_data.get("code_sent") and not reg_data.get("verified"):
                phone_found = phone
                break
        
        if not phone_found:
            raise HTTPException(
                status_code=400,
                detail="No pending registration found"
            )
        
        # Verify code with Meta's API
        verification_success = await verify_code_with_meta(code)
        
        if not verification_success:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired verification code"
            )
        
        # Mark as verified
        registration_store[phone_found]["verified"] = True
        registration_store[phone_found]["verified_at"] = datetime.now()
        
        logger.info(f"Successfully verified account for {phone_found}")
        
        # Return 201 Created with no payload as per API specification
        return JSONResponse(
            status_code=201,
            content={}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@app.get("/v1/account/status/{phone_number}")
async def get_account_status(phone_number: str):
    """
    Helper endpoint to check account status (not part of official API)
    """
    if phone_number in registration_store:
        reg_data = registration_store[phone_number]
        
        return {
            "phone_number": phone_number,
            "vname": reg_data.get("vname"),
            "verified": reg_data.get("verified", False),
            "code_sent": reg_data.get("code_sent", False),
            "created_at": reg_data.get("created_at").isoformat() if reg_data.get("created_at") else None
        }
    else:
        raise HTTPException(status_code=404, detail="Phone number not found")


@app.delete("/v1/account/{phone_number}")
async def cleanup_registration(phone_number: str):
    """
    Helper endpoint to clean up registration data
    """
    if phone_number in registration_store:
        registration_store.pop(phone_number)
        return {"message": f"Cleaned up registration data for {phone_number}"}
    else:
        raise HTTPException(status_code=404, detail="Phone number not found")