from fastapi import FastAPI

from app.routers import bookings
from app.routers import agent  # 👈 new import
#from app.chatbot.models import client, session, message
app = FastAPI()


#app.include_router(bookings.router)
app.include_router(agent.router)  # 👈 include agent router
