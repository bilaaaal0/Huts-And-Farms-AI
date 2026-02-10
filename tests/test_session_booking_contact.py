"""
Test session-based booking contact details.

This test verifies that:
1. Booking details are saved to session (not user profile)
2. User profile remains unchanged
3. Session fields are cleared after booking
4. Multiple bookings can have different contact details
"""

import pytest
from datetime import datetime, timedelta
from app.models.user import User, Session
from app.models.property import Property
from app.models.booking import Booking
from app.services.booking_service import BookingService
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.property_repository import PropertyRepository


def test_session_booking_contact_flow(db_session):
    """Test complete flow of session-based booking contact details."""
    
    # Setup: Create user with profile
    user_repo = UserRepository()
    user = user_repo.create(db_session, {
        "name": "Bilal Ahmed",
        "cnic": "4210112345678",
        "phone_number": "+923001234567"
    })
    
    # Setup: Create property
    property_repo = PropertyRepository()
    property_data = {
        "name": "Test Farmhouse",
        "address": "Test Location",
        "type": "Farmhouse",
        "max_occupancy": 20,
        "advance_percentage": 50
    }
    property_obj = property_repo.create(db_session, property_data)
    
    # Setup: Create session
    session_repo = SessionRepository()
    session = session_repo.create(db_session, {
        "id": "test-session-123",
        "user_id": user.user_id,
        "property_id": property_obj.property_id,
        "source": "Bot"
    })
    
    # Verify initial state
    assert user.name == "Bilal Ahmed"
    assert user.cnic == "4210112345678"
    assert session.booking_name is None
    assert session.booking_cnic is None
    
    # Simulate: User edits details to book for someone else
    session.booking_name = "Ahmed Ali"
    session.booking_cnic = "9876543210123"
    db_session.commit()
    
    # Verify session has new details
    db_session.refresh(session)
    assert session.booking_name == "Ahmed Ali"
    assert session.booking_cnic == "9876543210123"
    
    # Verify user profile unchanged
    db_session.refresh(user)
    assert user.name == "Bilal Ahmed"
    assert user.cnic == "4210112345678"
    
    # Create booking with session details
    booking_service = BookingService()
    booking_date = datetime.now() + timedelta(days=7)
    
    result = booking_service.create_booking(
        db=db_session,
        user_id=str(user.user_id),
        property_id=str(property_obj.property_id),
        booking_date=booking_date,
        shift_type="Day",
        user_name="Ahmed Ali",  # From session
        cnic="9876543210123",  # From session
        booking_source="Bot",
        session_id=session.id
    )
    
    # Verify booking created successfully
    assert result["success"] is True
    assert "Ahmed Ali" in result["booking_id"]
    
    # Verify session fields cleared
    db_session.refresh(session)
    assert session.booking_name is None
    assert session.booking_cnic is None
    
    # Verify user profile still unchanged
    db_session.refresh(user)
    assert user.name == "Bilal Ahmed"
    assert user.cnic == "4210112345678"
    
    # Verify booking has correct contact details
    booking = db_session.query(Booking).filter_by(booking_id=result["booking_id"]).first()
    assert booking is not None
    assert "Ahmed Ali" in booking.contact_details
    assert "98765-4321012-3" in booking.contact_details  # Formatted CNIC


def test_booking_without_session_details(db_session):
    """Test booking uses user profile when session details not set."""
    
    # Setup: Create user with profile
    user_repo = UserRepository()
    user = user_repo.create(db_session, {
        "name": "Bilal Ahmed",
        "cnic": "4210112345678",
        "phone_number": "+923001234567"
    })
    
    # Setup: Create property
    property_repo = PropertyRepository()
    property_data = {
        "name": "Test Farmhouse",
        "address": "Test Location",
        "type": "Farmhouse",
        "max_occupancy": 20,
        "advance_percentage": 50
    }
    property_obj = property_repo.create(db_session, property_data)
    
    # Setup: Create session WITHOUT booking details
    session_repo = SessionRepository()
    session = session_repo.create(db_session, {
        "id": "test-session-456",
        "user_id": user.user_id,
        "property_id": property_obj.property_id,
        "source": "Bot"
    })
    
    # Verify session has no booking details
    assert session.booking_name is None
    assert session.booking_cnic is None
    
    # Create booking (should use user profile)
    booking_service = BookingService()
    booking_date = datetime.now() + timedelta(days=7)
    
    result = booking_service.create_booking(
        db=db_session,
        user_id=str(user.user_id),
        property_id=str(property_obj.property_id),
        booking_date=booking_date,
        shift_type="Day",
        booking_source="Bot",
        session_id=session.id
    )
    
    # Verify booking created with user profile details
    assert result["success"] is True
    assert "Bilal Ahmed" in result["booking_id"]
    
    # Verify booking has user profile contact details
    booking = db_session.query(Booking).filter_by(booking_id=result["booking_id"]).first()
    assert booking is not None
    assert "Bilal Ahmed" in booking.contact_details
    assert "42101-1234567-8" in booking.contact_details


def test_multiple_bookings_different_details(db_session):
    """Test user can make multiple bookings with different contact details."""
    
    # Setup: Create user
    user_repo = UserRepository()
    user = user_repo.create(db_session, {
        "name": "Bilal Ahmed",
        "cnic": "4210112345678",
        "phone_number": "+923001234567"
    })
    
    # Setup: Create property
    property_repo = PropertyRepository()
    property_data = {
        "name": "Test Farmhouse",
        "address": "Test Location",
        "type": "Farmhouse",
        "max_occupancy": 20,
        "advance_percentage": 50
    }
    property_obj = property_repo.create(db_session, property_data)
    
    booking_service = BookingService()
    
    # Booking 1: For self (using user profile)
    session1 = SessionRepository().create(db_session, {
        "id": "session-1",
        "user_id": user.user_id,
        "property_id": property_obj.property_id,
        "source": "Bot"
    })
    
    result1 = booking_service.create_booking(
        db=db_session,
        user_id=str(user.user_id),
        property_id=str(property_obj.property_id),
        booking_date=datetime.now() + timedelta(days=7),
        shift_type="Day",
        booking_source="Bot",
        session_id=session1.id
    )
    
    assert result1["success"] is True
    booking1 = db_session.query(Booking).filter_by(booking_id=result1["booking_id"]).first()
    assert "Bilal Ahmed" in booking1.contact_details
    
    # Booking 2: For friend (using session details)
    session2 = SessionRepository().create(db_session, {
        "id": "session-2",
        "user_id": user.user_id,
        "property_id": property_obj.property_id,
        "source": "Bot",
        "booking_name": "Ahmed Ali",
        "booking_cnic": "9876543210123"
    })
    
    result2 = booking_service.create_booking(
        db=db_session,
        user_id=str(user.user_id),
        property_id=str(property_obj.property_id),
        booking_date=datetime.now() + timedelta(days=14),
        shift_type="Night",
        user_name="Ahmed Ali",
        cnic="9876543210123",
        booking_source="Bot",
        session_id=session2.id
    )
    
    assert result2["success"] is True
    booking2 = db_session.query(Booking).filter_by(booking_id=result2["booking_id"]).first()
    assert "Ahmed Ali" in booking2.contact_details
    
    # Verify user profile unchanged
    db_session.refresh(user)
    assert user.name == "Bilal Ahmed"
    assert user.cnic == "4210112345678"
    
    # Verify session 2 cleared
    db_session.refresh(session2)
    assert session2.booking_name is None
    assert session2.booking_cnic is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
