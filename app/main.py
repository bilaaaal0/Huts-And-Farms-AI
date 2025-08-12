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
models.Base.metadata.create_all(bind=engine)

app = FastAPI()



app.include_router(agent.router)  
app.include_router(wati_webhook.router)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
registration_store={}

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
        
        full_phone = f"{cc}{phone_number}"
        
        # Check if account already exists (mock check)
        # In real implementation, check against WhatsApp Business API
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
            "code_sent": True
        }
        
        # In real implementation, this would call WhatsApp Business API
        # to send SMS/voice verification code
        logger.info(f"Sending {method} code to {full_phone}")
        
        # Simulate code sending (in real implementation, integrate with SMS/Voice API)
        mock_response = {
            "vname": vname,
            "message": f"Registration code sent via {method} to +{full_phone}",
            "display_name": vname
        }
        
        return JSONResponse(
            status_code=202,
            content=mock_response
        )
        
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
        
        # Find the registration attempt by code (simplified logic)
        # In real implementation, you'd match code with phone number
        phone_found = None
        for phone, reg_data in registration_store.items():
            if reg_data.get("code_sent") and not reg_data.get("verified"):
                phone_found = phone
                break
        
        if not phone_found:
            raise HTTPException(
                status_code=400,
                detail="No pending registration found or code already used"
            )
        
        # Verify the code (in real implementation, validate against sent code)
        # For demo purposes, accept any 6-digit code
        if not (code.isdigit() and len(code) == 6):
            raise HTTPException(
                status_code=400,
                detail="Invalid code format. Code must be 6 digits."
            )
        
        # Mark as verified
        registration_store[phone_found]["verified"] = True
        registration_store[phone_found]["verification_code"] = code
        
        logger.info(f"Successfully verified account for {phone_found}")
        
        # Return 201 Created with no payload as per documentation
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
            "code_sent": reg_data.get("code_sent", False)
        }
    else:
        raise HTTPException(status_code=404, detail="Phone number not found")