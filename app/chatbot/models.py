from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from sqlalchemy import Column, String, Text, Integer, Enum, DateTime, Numeric, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import uuid
from pgvector.sqlalchemy import Vector



class Session(Base):
    __tablename__ = "sessions"
    id = Column(String(64), primary_key=True, index=True)  # Use a UUID string or similar
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)  # Foreign key to users
    created_at = Column(DateTime, default=datetime.utcnow)
    booking_id = Column(String(64), nullable=True)  # Booking ID if this session is related to a booking
    property_id = Column(String(64), nullable=True)
    property_type = Column(Enum("hut", "farm", name="property_type_enum"), nullable=True)
    booking_date = Column(DateTime, nullable=True)  # Date of the booking
    shift_type = Column(Enum("Day", "Night", "Full Day", "Full Night", name="shift_type_enum"), nullable=True)  # Type of booking shift
    min_price = Column(Numeric(10, 2), nullable=True)  # Minimum price for the booking
    max_price = Column(Numeric(10, 2), nullable=True)  # Maximum
    max_occupancy = Column(Integer, nullable=True)  # Maximum occupancy for the booking
    user = relationship("User", backref="sessions")  # Relationship to User model


class Message(Base):
    __tablename__ = "messages"

    
    id = Column(Integer, primary_key=True, index=True)
    # session_id = Column(String(64), ForeignKey("sessions.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    sender = Column(String(10))  # "user" or "bot"
    content = Column(Text)

    timestamp = Column(DateTime, default=datetime.utcnow)
    whatsapp_message_id = Column(String(100), nullable=True)

    query_embedding = Column(Vector(3072), nullable=True)  # use correct dimension
    user = relationship("User", backref= "messages")






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
    advance_percentage = Column(Numeric(5, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# ✅ Users
class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="unique_user_email"),)

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable= True)
    cnic = Column(String(13),nullable=True, unique=True)
    email = Column(String, nullable=True, unique=True)
    phone_number = Column(String,nullable=False, unique=True)
    password = Column(Text, nullable=True)
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
    owner_id = Column(UUID(as_uuid=True), ForeignKey("owners.owner_id"), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.property_id"), nullable=False)
    owner = relationship("Owner", backref="properties")
    property = relationship("Property", backref="owners")

# ✅ Bookings
class Booking(Base):
    __tablename__ = "bookings"

    booking_id = Column(Text, primary_key=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)  # Foreign key to users
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.property_id"), nullable=False)
    booking_date = Column(DateTime, nullable=False)
    shift_type = Column(Enum("Day", "Night", "Full Day","Full Night" , name="shift_type_enum"), nullable=False)
    total_cost = Column(Numeric(10, 2), nullable=False)
    booking_source = Column(Enum("Website", "WhatsApp Bot", "Third-Party", name="booking_source_enum"), nullable=False)
    status = Column(Enum("Pending", "Confirmed", "Cancelled", "Completed", name="booking_status_enum"), default="Pending")
    booked_at = Column(DateTime)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    user = relationship("User", backref="bookings")
    property = relationship("Property", backref="Booking")


# class Payment(Base):
#     __tablename__ = "payments"

#     payment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     booking_id = Column(UUID(as_uuid=True), nullable=False)
#     amount = Column(Numeric(10, 2), nullable=False)
#     status = Column(Enum("Pending", "Completed", "Failed", name="payment_status_enum"), default="Pending")
#     transaction_id = Column(String(100), nullable=True)  # Transaction ID from payment gateway
#     sender_phone_number = Column(String(20), nullable=True)  # Phone number of the sender
#     sender_name = Column(String(100), nullable=True)  # Name of the sender
#     created_at = Column(DateTime, default=datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.utcnow)

# ✅ PropertyPricing
# class PropertyPricing(Base):
#     __tablename__ = "property_pricing"

#     pricing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     property_id = Column(UUID(as_uuid=True), ForeignKey("properties.property_id"), nullable=False)
#     base_price_day_shift = Column(Numeric(10, 2))
#     base_price_night_shift = Column(Numeric(10, 2))
#     base_price_full_day = Column(Numeric(10, 2))
#     season_start_date = Column(DateTime)
#     season_end_date = Column(DateTime)
#     special_offer_note = Column(Text)
#     property = relationship("Property", backref="pricing")

class PropertyPricing(Base):
    __tablename__ = "property_pricing"

    pricing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.property_id"), nullable=False)
    season_start_date = Column(DateTime, nullable=True)
    season_end_date = Column(DateTime, nullable=True)
    special_offer_note = Column(Text, nullable=True)

    property = relationship("Property", backref="pricing")


class PropertyShiftPricing(Base):
    __tablename__ = "property_shift_pricing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pricing_id = Column(UUID(as_uuid=True), ForeignKey("property_pricing.pricing_id"), nullable=False)
    day_of_week = Column(Enum("saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday" , name="week_enum"), nullable=False)  # 0=Monday, 6=Sunday
    shift_type = Column(Enum("Day", "Night", "Full Day","Full Night" , name="shift_type_enum"), nullable=False)  # 'day', 'night', 'full_day', 'full_night'
    price = Column(Numeric(10, 2), nullable=False)

    pricing = relationship("PropertyPricing", backref="shift_prices")


# ✅ PropertyImage
class PropertyImage(Base):
    __tablename__ = "property_images"

    image_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.property_id"), nullable=False)
    image_url = Column(Text)
    uploaded_at = Column(DateTime)
    property = relationship("Property", backref="images")

# ✅ PropertyVideo
class PropertyVideo(Base):
    __tablename__ = "property_videos"

    video_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.property_id"), nullable=False)
    video_url = Column(Text)
    uploaded_at = Column(DateTime)
    property = relationship("Property", backref="videos")

# ✅ PropertyAmenity
class PropertyAmenity(Base):
    __tablename__ = "property_amenities"

    amenity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.property_id"), nullable=False)
    type = Column(String)
    value = Column(String)
    property = relationship("Property", backref="amenities")
