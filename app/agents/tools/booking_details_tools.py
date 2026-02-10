"""
Booking details collection and validation tools.

This module contains tools for collecting and validating user details
(name and CNIC) before creating a booking.
"""

import logging
from langchain.tools import tool
from typing import Optional

from app.database import SessionLocal
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.core.constants import CNIC_LENGTH

logger = logging.getLogger(__name__)


def format_cnic(cnic: str) -> str:
    """Format CNIC as XXXXX-XXXXXXX-X"""
    if len(cnic) == 13:
        return f"{cnic[:5]}-{cnic[5:12]}-{cnic[12]}"
    return cnic


@tool("prepare_booking_details")
def prepare_booking_details(
    session_id: str,
    user_name: Optional[str] = None,
    cnic: Optional[str] = None,
    action: Optional[str] = None
) -> dict:
    """
    Prepare and validate user details before booking.

    CRITICAL: ALWAYS call this tool BEFORE create_booking!
    
    This tool:
    1. Checks if user has name/CNIC in session
    2. If missing → Asks user to provide them
    3. If exists → Asks user to confirm or edit
    4. Validates CNIC length (must be 13 digits)
    5. Returns ready=true only when both are valid and confirmed
    
    CALL SEQUENCE:
    Step 1: Call with only session_id → Check what's needed
    Step 2: User provides/confirms details → Call with user_name/cnic/action
    Step 3: If ready=true → Call create_booking
    
    CRITICAL RESPONSE HANDLING:
    • ready=false → STOP! Show questions to user and WAIT for response
    • editing=true → User is editing, show form and WAIT
    • needs_confirmation=true → Show confirm/edit options and WAIT
    • ready=true → NOW you can call create_booking
    
    DO NOT call create_booking when ready=false!
    DO NOT call create_booking when editing=true!
    DO NOT call create_booking when needs_confirmation=true!
    
    PARAMS:
    • session_id - Required, current session
    • user_name - Optional, user's full name
    • cnic - Optional, user's CNIC (13 digits)
    • action - Optional, "Confirm and Book" or "Edit Details"
    
    RETURNS:
    • ready: bool - True = can call create_booking now
    • needs_confirmation: bool - True = show confirm/edit choice
    • editing: bool - True = user is editing fields
    • questions_needed: list - Fields that need to be collected
    • questions: list - Question objects for formatter
    • main_message: str - Message for user
    • validation_errors: list - Any validation errors
    
    EXAMPLES:
    1. Check status: prepare_booking_details(session_id="abc")
    2. New user provides: prepare_booking_details(session_id="abc", user_name="Ali", cnic="1234567890123")
    3. Existing user confirms: prepare_booking_details(session_id="abc", action="Confirm and Book")
    4. Existing user edits: prepare_booking_details(session_id="abc", action="Edit Details")
    """
    db = SessionLocal()
    try:
        print("\n" + "="*80)
        print("🔧 PREPARE_BOOKING_DETAILS TOOL CALLED")
        print("="*80)
        print(f"Session ID: {session_id}")
        print(f"User Name provided: {user_name}")
        print(f"CNIC provided: {cnic}")
        print(f"Action: {action}")
        print("="*80 + "\n")
        
        # Get session and user
        session_repo = SessionRepository()
        session = session_repo.get_by_id(db, session_id)
        
        if not session:
            return {"error": "Session not found. Please restart the conversation."}
        
        user = session.user
        if not user:
            return {"error": "User not found in session."}
        
        # Get current values from SESSION (booking-specific, temporary)
        # Fall back to user profile if not set in session
        current_name = session.booking_name or user.name
        current_cnic = session.booking_cnic or user.cnic
        
        print(f"Current session booking values - Name: {current_name}, CNIC: {current_cnic}")
        print(f"User profile values (unchanged) - Name: {user.name}, CNIC: {user.cnic}")
        
        # ========================================
        # CASE 1: User is providing/updating details
        # ========================================
        if user_name or cnic:
            validation_errors = []
            
            # Use current values as defaults if not provided
            final_name = user_name.strip() if user_name else current_name
            final_cnic = cnic.replace("-", "").replace(" ", "").strip() if cnic else current_cnic
            
            # Validate name
            if final_name:
                if len(final_name) < 2:
                    validation_errors.append("Name must be at least 2 characters")
            else:
                validation_errors.append("Name is required")
            
            # Validate CNIC
            if final_cnic:
                if len(final_cnic) != CNIC_LENGTH:
                    validation_errors.append(f"CNIC must be exactly {CNIC_LENGTH} digits")
                elif not final_cnic.isdigit():
                    validation_errors.append("CNIC must contain only numbers")
            else:
                validation_errors.append("CNIC is required")
            
            # If validation errors, show edit form again with error
            if validation_errors:
                print(f"❌ Validation errors: {validation_errors}")
                
                # Show BOTH fields again (like edit mode) with error message
                error_message = ' and '.join(validation_errors)
                
                return {
                    "ready": False,
                    "editing": True,
                    "validation_errors": validation_errors,
                    "main_message": f"❌ {error_message}. Please correct below:",
                    "questions_needed": ["user_name", "cnic"],
                    "questions": [
                        {
                            "id": "user_name",
                            "text": "Your full name",
                            "type": "text",
                            "placeholder": current_name or "e.g., Ahmed Ali",
                            "default_value": final_name or ""
                        },
                        {
                            "id": "cnic",
                            "text": "Your CNIC number",
                            "type": "text",
                            "placeholder": "13 digits without dashes",
                            "default_value": final_cnic or ""
                        }
                    ],
                    "instruction": "Show ONLY the error message and edit form. Do NOT add any additional text or options."
                }
            
            # All validations passed - SAVE to session (temporary, for this booking only)
            session.booking_name = final_name
            session.booking_cnic = final_cnic
            db.commit()
            
            print(f"✅ Booking details saved to session - Name: {final_name}, CNIC: {final_cnic}")
            print(f"   User profile unchanged - Name: {user.name}, CNIC: {user.cnic}")
            
            # Return ready status for create_booking
            return {
                "ready": True,
                "confirmed": True,
                "user_name": final_name,
                "cnic": final_cnic,
                "main_message": "✅ Details confirmed! Creating your booking..."
            }
        
        # ========================================
        # CASE 2: User selected action (Confirm or Edit)
        # ========================================
        if action:
            if action == "Confirm and Book":
                # User confirmed existing details
                print("✅ User confirmed existing details")
                return {
                    "ready": True,
                    "confirmed": True,
                    "user_name": current_name,
                    "cnic": current_cnic,
                    "main_message": "✅ Details confirmed! Creating your booking..."
                }
            
            elif action == "Edit Details":
                # User wants to edit - show form with pre-filled values
                print("📝 User wants to edit details")
                return {
                    "ready": False,
                    "editing": True,
                    "current_name": current_name,
                    "current_cnic": current_cnic,
                    "main_message": "Edit your details below:",
                    "questions_needed": ["user_name", "cnic"],
                    "questions": [
                        {
                            "id": "user_name",
                            "text": "Your full name",
                            "type": "text",
                            "placeholder": current_name or "e.g., Ahmed Ali",
                            "default_value": current_name or ""
                        },
                        {
                            "id": "cnic",
                            "text": "Your CNIC number",
                            "type": "text",
                            "placeholder": current_cnic or "13 digits without dashes",
                            "default_value": current_cnic or ""
                        }
                    ]
                }
        
        # ========================================
        # CASE 3: Initial check - determine what's needed
        # ========================================
        
        # Both exist - ask for confirmation
        if current_name and current_cnic:
            print("ℹ️ Both name and CNIC exist - asking for confirmation")
            formatted_cnic = format_cnic(current_cnic)
            
            return {
                "ready": False,
                "needs_confirmation": True,
                "current_name": current_name,
                "current_cnic": current_cnic,
                "main_message": f"Please confirm your booking details:\n\n👤 Name: {current_name}\n🆔 CNIC: {formatted_cnic}",
                "questions_needed": ["action"],
                "questions": [
                    {
                        "id": "action",
                        "text": "What would you like to do?",
                        "type": "choice",
                        "options": ["Confirm and Book", "Edit Details"]
                    }
                ]
            }
        
        # Missing one or both - ask for them
        print("ℹ️ Missing name or CNIC - asking user to provide")
        questions = []
        questions_needed = []
        
        if not current_name:
            questions.append({
                "id": "user_name",
                "text": "Your full name",
                "type": "text",
                "placeholder": "e.g., Ahmed Ali"
            })
            questions_needed.append("user_name")
        
        if not current_cnic:
            questions.append({
                "id": "cnic",
                "text": "Your CNIC number",
                "type": "text",
                "placeholder": "13 digits without dashes"
            })
            questions_needed.append("cnic")
        
        return {
            "ready": False,
            "questions_needed": questions_needed,
            "main_message": "To proceed with booking, I need your details.",
            "questions": questions
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in prepare_booking_details tool: {e}", exc_info=True)
        return {"error": "Something went wrong while preparing booking details. Please try again."}
    finally:
        db.close()


# Export tools list
booking_details_tools = [
    prepare_booking_details,
]

__all__ = [
    "prepare_booking_details",
    "booking_details_tools",
]
