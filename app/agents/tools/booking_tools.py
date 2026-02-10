"""
Booking-related agent tools.

This module contains tools for:
- Creating bookings
- Checking booking status
- Getting user bookings
- Getting payment instructions

These tools use the BookingService layer for all business logic.
"""

import logging
from langchain.tools import tool
from typing import Dict, Optional
from datetime import datetime

from app.database import SessionLocal
from app.services.booking_service import BookingService
from app.repositories.session_repository import SessionRepository
from app.core.constants import EASYPAISA_NUMBER

logger = logging.getLogger(__name__)


@tool("create_booking")
def create_booking(
    session_id: str,
    booking_date: str,
    shift_type: str,
    cnic: Optional[str] = None,
    user_name: Optional[str] = None
) -> dict:
    """
    Create booking after user confirmation.

    CALL: User confirms + has CNIC/name (in DB or provided)
    NO CALL: Browsing | Exploring | No confirmation

    REQ:
    • booking_date YYYY-MM-DD future
    • shift_type Day|Night|Full Day|Full Night
    • property_id in session
    • User confirmed booking

    PARAMS:
    • cnic - Optional, uses DB if not provided
    • user_name - Optional, uses DB if not provided

    RETURNS:
    success {message} - Booking created with payment info
    error {error} - Availability/validation errors
    """
    db = SessionLocal()
    try:
        print("\n" + "="*80)
        print("🔧 CREATE_BOOKING TOOL CALLED")
        print("="*80)
        print(f"Session ID: {session_id}")
        print(f"Booking Date: {booking_date}")
        print(f"Shift Type: {shift_type}")
        print(f"CNIC provided: {bool(cnic)}")
        print(f"User Name provided: {bool(user_name)}")
        print("="*80 + "\n")
        
        # Get session to find user and property
        session_repo = SessionRepository()
        session = session_repo.get_by_id(db, session_id)
        
        if not session:
            return {"error": "Session not found. Please restart the conversation."}
        
        if not session.property_id:
            return {"error": "Please provide me name of the property."}
        
        # Parse booking date
        try:
            booking_date_obj = datetime.strptime(booking_date, "%Y-%m-%d")
        except ValueError:
            return {"error": "Invalid date format. Please use YYYY-MM-DD format."}
        
        # Create booking using service
        booking_service = BookingService()
        result = booking_service.create_booking(
            db=db,
            user_id=str(session.user_id),
            property_id=session.property_id,
            booking_date=booking_date_obj,
            shift_type=shift_type,
            user_name=user_name,
            cnic=cnic,
            booking_source="Bot",
            session_id=session_id  # Pass session_id to read/clear booking contact details
        )
        
        # Update session with booking_id if successful
        if result.get("success"):
            session.booking_id = result["booking_id"]
            db.commit()
            
            # Mark state change for memory system
            from app.agents.memory.state_detector import mark_state_change
            mark_state_change(session_id, db)
        
        # Return message or error
        if result.get("success"):
            print("\n" + "="*80)
            print("✅ CREATE_BOOKING TOOL - SUCCESS")
            print("="*80)
            print(f"Booking ID: {result.get('booking_id')}")
            print(f"Message length: {len(result.get('message', ''))}")
            print("="*80 + "\n")
            return {"message": result["message"]}
        else:
            print("\n" + "="*80)
            print("❌ CREATE_BOOKING TOOL - ERROR")
            print("="*80)
            print(f"Error: {result.get('error')}")
            print("="*80 + "\n")
            # All errors from service are actual errors (availability, validation, missing data, etc.)
            return {"error": result.get("error", "Failed to create booking")}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in create_booking tool: {e}", exc_info=True)
        return {"error": "Something went wrong while creating your booking. Please try again or contact support."}
    finally:
        db.close()


@tool("check_booking_status")
def check_booking_status(booking_id: str) -> dict:
    """
    Check booking status.

    CALL: booking_id + status/progress query
    NO CALL: create booking | browse | price | availability | missing booking_id

    REQ:
    • booking_id valid and exists

    RETURNS:
    ok {status, message, booking_id, needs_payment, property_name, amount}
    err {error}
    """
    db = SessionLocal()
    try:
        print("\n" + "="*80)
        print("🔧 CHECK_BOOKING_STATUS TOOL CALLED")
        print("="*80)
        print(f"Booking ID (raw): '{booking_id}'")
        print("="*80 + "\n")
        
        booking_id = booking_id.strip()
        
        print(f"Booking ID (stripped): '{booking_id}'")
        
        # Check booking status using service
        booking_service = BookingService()
        result = booking_service.check_booking_status(db, booking_id)
        
        if not result.get("success"):
            print("\n" + "="*80)
            print("❌ CHECK_BOOKING_STATUS - NOT FOUND")
            print("="*80)
            print(f"Error: {result.get('error')}")
            print("="*80 + "\n")
            return {"error": result.get("error", "Booking not found. Please check your booking ID.")}
        
        booking = result["booking"]
        
        # Build response with additional details
        return {
            "success": True,
            "status": booking.status,
            "message": result["message"],
            "booking_id": str(booking.booking_id),
            "needs_payment": booking.status == "Pending",
            "property_name": booking.property.name,
            "amount": float(booking.total_cost)
        }
        
    except Exception as e:
        logger.error(f"Error in check_booking_status tool: {e}", exc_info=True)
        return {"error": "Error checking booking status. Please try again."}
    finally:
        db.close()


@tool("get_user_bookings")
def get_user_bookings(session_id: str, cnic: Optional[str] = None, limit: int = 5) -> dict:
    """
    Get user bookings.

    CALL: user bookings/history query + verified user/session
    NO CALL: booking status by ID | create booking | browse | missing verification

    REQ:
    • valid session with user_id
    • CNIC required if user not already verified
    • limit: positive integer

    SENSITIVE: verify CNIC, never echo full CNIC

    RETURNS:
    ok {message, bookings_count}
    err {error}
    """
    db = SessionLocal()
    try:
        # Get session to find user
        session_repo = SessionRepository()
        session = session_repo.get_by_id(db, session_id)
        
        if not session:
            return {"error": "Session not found. Please restart the conversation."}
        
        # Verify CNIC if provided
        if cnic:
            cnic = cnic.replace("-", "")
            if session.user.cnic and session.user.cnic != cnic:
                return {"error": "CNIC does not match our records. Please provide the correct CNIC."}
        elif not session.user.cnic:
            return {"error": "Please provide me CNIC number which you used to confirm booking."}
        
        # Get user bookings using service
        booking_service = BookingService()
        result = booking_service.get_user_bookings(
            db=db,
            user_id=str(session.user_id),
            limit=limit
        )
        
        if not result.get("success"):
            return {"error": result.get("error", "Error retrieving your bookings")}
        
        bookings = result["bookings"]
        
        if not bookings:
            return {
                "success": True,
                "message": """📋 *YOUR BOOKINGS*

No bookings found yet.

Ready to make your first booking? Just tell me what kind of property you're looking for! 🏡"""
            }
        
        # Format bookings list
        bookings_list = []
        for booking in bookings:
            # Format date
            try:
                formatted_date = booking.booking_date.strftime("%d %b %Y")
            except:
                formatted_date = str(booking.booking_date)
            
            # Status emoji
            status_emoji = {
                "Pending": "⏳",
                "Waiting": "🔍",
                "Confirmed": "✅",
                "Cancelled": "❌",
                "Completed": "🎉",
                "Expired": "⌛"
            }.get(booking.status, "📋")
            
            booking_info = f"""{status_emoji} *{booking.property.name}*
📅 {formatted_date} | {booking.shift_type}
💰 Rs. {int(booking.total_cost)} | {booking.status}
🆔 `{booking.booking_id}`"""
            
            bookings_list.append(booking_info)
        
        message = f"""📋 *YOUR RECENT BOOKINGS*

{chr(10).join(bookings_list)}

━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Quick Actions:*
• Check status: Share booking ID
• Need help: Contact support
• New booking: Tell me your requirements!"""
        
        return {
            "success": True,
            "message": message,
            "bookings_count": len(bookings)
        }
        
    except Exception as e:
        logger.error(f"Error in get_user_bookings tool: {e}", exc_info=True)
        return {"error": "Error retrieving your bookings. Please try again."}
    finally:
        db.close()


@tool("get_payment_instructions")
def get_payment_instructions(booking_id: str) -> dict:
    """
    Get payment instructions.

    CALL: booking_id + payment/how to pay query + pending booking
    NO CALL: booking confirmed/cancelled/completed | browse | missing booking_id

    REQ:
    • booking_id valid
    • booking status must be Pending

    RETURNS:
    ok {message, amount, easypaisa_number}
    err {error}
    """
    db = SessionLocal()
    try:
        print("\n" + "="*80)
        print("🔧 GET_PAYMENT_INSTRUCTIONS TOOL CALLED")
        print("="*80)
        print(f"Booking ID (raw): '{booking_id}'")
        print("="*80 + "\n")
        
        booking_id = booking_id.strip()
        
        # Check booking status using service
        booking_service = BookingService()
        result = booking_service.check_booking_status(db, booking_id)
        
        if not result.get("success"):
            return {"error": result.get("error", "Booking not found")}
        
        booking = result["booking"]
        
        if booking.status != "Pending":
            return {"error": f"This booking is {booking.status.lower()}. No payment needed."}
        
        message = f"""💳 *PAYMENT INSTRUCTIONS*

🆔 Booking ID: `{booking.booking_id}`
💰 Amount to Pay: *Rs. {int(booking.total_cost)}*

━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *EasyPaisa Payment:*
Send Rs. {int(booking.total_cost)} to: *{EASYPAISA_NUMBER}*

📸 *After Payment:*
Send me:
1️⃣ Payment screenshot, OR
2️⃣ Payment details:
   • Your full name ✅ Required
   • Amount paid ✅ Required
   • Transaction ID ⚪ Optional
   • Your phone number ⚪ Optional

✅ We'll verify and confirm your booking within minutes!

_Ready when you are!_ 😊"""
        
        return {
            "success": True,
            "message": message,
            "amount": float(booking.total_cost),
            "easypaisa_number": EASYPAISA_NUMBER
        }
        
    except Exception as e:
        logger.error(f"Error in get_payment_instructions tool: {e}", exc_info=True)
        return {"error": "Error retrieving payment instructions"}
    finally:
        db.close()


# Export tools list for agent registration
booking_tools = [
    create_booking,
    check_booking_status,
    get_user_bookings,
    get_payment_instructions,
]

__all__ = [
    "create_booking",
    "check_booking_status",
    "get_user_bookings",
    "get_payment_instructions",
    "booking_tools",
]
