from fastapi import FastAPI, Request

from app.routers import wati_webhook
from app.routers import agent 
from app.database import engine
from app.chatbot import models


models.Base.metadata.create_all(bind=engine)

app = FastAPI()



app.include_router(agent.router)  
app.include_router(wati_webhook.router)

@app.post("/v1/account")
async def register_phone_number(request: Request):
    data = await request.json()
    
    cc = data.get("cc")
    phone_number = data.get("phone_number")
    method = data.get("method", "sms")
    cert = data.get("cert")
    pin = data.get("pin")
    
    # Add your WhatsApp registration logic here
    
    return {
        "success": True,
        "message": f"Registration request for +{cc}{phone_number}",
        "method": method
    }