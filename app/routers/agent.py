from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.agent.booking_agent import BookingToolAgent
from app.database import SessionLocal
from sqlalchemy.orm import Session
from app.chatbot.models import Session as SessionModel, Message
from app.database import get_db
import uuid
from datetime import datetime


from .utility import  is_hourly_messages_limit_exceeded,is_hourly_token_limit_exceeded
router = APIRouter()
agent = BookingToolAgent()

# Request model for chat
class ChatInput(BaseModel):
    session_id: str
    message: str

@router.post("/chat")
def chat_with_agent(request: ChatInput, db: Session = Depends(get_db)):
    session_id = request.session_id
    user_message = request.message

    # Log user message
    
   
    if is_hourly_token_limit_exceeded(session_id,user_message):
            print(f"🚫 Rate limit exceeded for session: {session_id}")
            return {"response": "max_tokens_reached"}
    
    user_msg = Message(
        session_id=session_id,
        sender="user",
        content=user_message,
        timestamp=datetime.utcnow()
    )
    db.add(user_msg)
    db.commit()

    # Get agent response
    
    response_text = agent.get_response(user_message,session_id)

    response_text = response_text.replace("**", "*")

    # Log bot response
    bot_msg = Message(
        session_id=session_id,
        sender="bot",
        content=response_text,
        timestamp=datetime.utcnow()
    )
    db.add(bot_msg)
    db.commit()

    return {"response": response_text}





# POST /session/create
@router.post("/session/create")
def create_session():
    session_id = str(uuid.uuid4())
    with SessionLocal() as db:
        new_session = SessionModel(id=session_id)
        db.add(new_session)
        db.commit()
    return {"session_id": session_id}

@router.get("/chat/history/{session_id}")
def get_chat_history(session_id: str):
    db = SessionLocal()
    history = db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp).all()
    db.close()
    return [{"sender": msg.sender, "message": msg.content, "timestamp": msg.timestamp} for msg in history]