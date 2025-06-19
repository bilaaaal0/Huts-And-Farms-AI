from fastapi import APIRouter
from pydantic import BaseModel
from app.agent.booking_agent import BookingToolAgent  # Assuming you saved the agent class here

router = APIRouter()
agent = BookingToolAgent()

class MessageInput(BaseModel):
    message: str

@router.post("/chat")
def chat_with_agent(payload: MessageInput):
    response = agent.get_response(payload.message)
    return {"response": response}
