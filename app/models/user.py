from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="unique_user_email"),)

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=True)
    cnic = Column(String(13), nullable=True, unique=True)
    email = Column(String, nullable=True, unique=True)
    phone_number = Column(String, nullable=False, unique=True)
    password = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String(64), primary_key=True, index=True)  # Use a UUID string or similar
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)  # Foreign key to users
    created_at = Column(DateTime, default=datetime.utcnow)
    booking_id = Column(Text, nullable=True)  # Booking ID if this session is related to a booking
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.property_id"), nullable=True)
    property_type = Column(String, nullable=True)  # Will be constrained by enum
    booking_date = Column(DateTime, nullable=True)  # Date of the booking
    shift_type = Column(String, nullable=True)  # Will be constrained by enum
    min_price = Column(Integer, nullable=True)  # Minimum price for the booking
    max_price = Column(Integer, nullable=True)  # Maximum
    max_occupancy = Column(Integer, nullable=True)  # Maximum occupancy for the booking
    source = Column(String, nullable=True)  # Session source: Website or Chatbot
    
    # Booking contact details (temporary, for current booking only)
    booking_name = Column(Text, nullable=True)  # Name for this specific booking
    booking_cnic = Column(Text, nullable=True)  # CNIC for this specific booking
    
    # Memory management fields
    conversation_summary = Column(Text, nullable=True)  # Compressed conversation summary
    summary_updated_at = Column(DateTime, nullable=True)  # When summary was last updated
    summary_generation_count = Column(Integer, default=0)  # How many times summary has been generated
    needs_summarization = Column(Boolean, default=False)  # Flag set by tools when state changes
    
    user = relationship("User", backref="sessions")  # Relationship to User model
    property = relationship("Property", backref="sessions")
