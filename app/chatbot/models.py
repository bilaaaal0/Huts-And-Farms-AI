from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base  # adjust import based on your structure

class Client(Base):
    __tablename__ = "clients"

    email = Column(String, primary_key=True, index=True, unique=True)
    name = Column(String, nullable=True)
    role = Column(String, default="CLIENT")
    auth_token = Column(String, nullable=True)
    authenticated_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("Session", back_populates="client")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, index=True)  # UUID or any unique string
    client_email = Column(String, ForeignKey("clients.email"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="sessions")
    messages = relationship("Message", back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    sender = Column(String)  # "user" or "bot"
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="messages")
