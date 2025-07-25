from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from sqlalchemy import Column, String, Text, Integer, Enum, DateTime, Numeric, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import uuid


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, index=True)  # Use a UUID string or similar
    whatsapp_number = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client_email = Column(String(100), nullable=True)  # Email of the client, if authenticated
    messages = relationship("Message", back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("sessions.id"))
    sender = Column(String(10))  # e.g. "user" or "bot"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="messages")






# ✅ Properties
class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (UniqueConstraint("username", name="unique_property_username"),)

    property_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    address = Column(String(255))
    city = Column(String(100))
    province = Column(String(100))
    country = Column(String(100))
    contact_person = Column(String(100))
    contact_number = Column(String(20))
    email = Column(String(100))
    max_occupancy = Column(Integer)
    username = Column(String(100), unique=True)
    password = Column(Text, nullable=False)
    type = Column(Enum("hut", "farm", name="property_type_enum"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# ✅ Users
class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="unique_user_email"),)

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, nullable=False, unique=True)
    phone_number = Column(String)
    password = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# ✅ Owners
class Owner(Base):
    __tablename__ = "owners"
    __table_args__ = (UniqueConstraint("username", name="unique_owner_username"),)

    owner_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, nullable=False)
    phone_number = Column(String)
    username = Column(String, unique=True, nullable=False)
    password = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# ✅ OwnerProperties
class OwnerProperty(Base):
    __tablename__ = "owner_properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    property_id = Column(UUID(as_uuid=True), nullable=False)

# ✅ Bookings
class Booking(Base):
    __tablename__ = "bookings"

    booking_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    property_id = Column(UUID(as_uuid=True), nullable=False)
    booking_date = Column(DateTime, nullable=False)
    shift_type = Column(Enum("Day", "Night", "Full Day", name="shift_type_enum"), nullable=False)
    total_cost = Column(Numeric(10, 2), nullable=False)
    booking_source = Column(Enum("Website", "WhatsApp Bot", "Third-Party", name="booking_source_enum"), nullable=False)
    status = Column(Enum("Pending", "Confirmed", "Cancelled", "Completed", name="booking_status_enum"), default="Pending")
    booked_at = Column(DateTime)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    user_phone_number = Column(String(255), nullable=True)

# ✅ PropertyPricing
class PropertyPricing(Base):
    __tablename__ = "property_pricing"

    pricing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), nullable=False)
    base_price_day_shift = Column(Numeric(10, 2))
    base_price_night_shift = Column(Numeric(10, 2))
    base_price_full_day = Column(Numeric(10, 2))
    season_start_date = Column(DateTime)
    season_end_date = Column(DateTime)
    special_offer_note = Column(Text)

# ✅ PropertyImage
class PropertyImage(Base):
    __tablename__ = "property_images"

    image_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), nullable=False)
    image_url = Column(Text)
    uploaded_at = Column(DateTime)

# ✅ PropertyVideo
class PropertyVideo(Base):
    __tablename__ = "property_videos"

    video_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), nullable=False)
    video_url = Column(Text)
    uploaded_at = Column(DateTime)

# ✅ PropertyAmenity
class PropertyAmenity(Base):
    __tablename__ = "property_amenities"

    amenity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), nullable=False)
    type = Column(String)
    value = Column(String)
