"""
Booking service for business logic related to bookings.

This module provides the BookingService class that implements all booking-related
business logic including creation, confirmation, cancellation, and status management.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.booking_repository import BookingRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.models.booking import Booking
from app.core.constants import (
    VALID_SHIFT_TYPES,
    EASYPAISA_NUMBER,
    EASYPAISA_ACCOUNT_HOLDER,
    CNIC_LENGTH
)
from app.core.exceptions import BookingException

logger = logging.getLogger(__name__)


class BookingService:
    """
    Service for managing booking operations.
    
    Handles all booking-related business logic including validation,
    availability checking, booking creation, confirmation, and cancellation.
    """
    
    def __init__(
        self,
        booking_repo: Optional[BookingRepository] = None,
        property_repo: Optional[PropertyRepository] = None,
        user_repo: Optional[UserRepository] = None
    ):
        """
        Initialize the booking service with repository dependencies.
        
        Args:
            booking_repo: Repository for booking operations
            property_repo: Repository for property operations
            user_repo: Repository for user operations
        """
        self.booking_repo = booking_repo or BookingRepository()
        self.property_repo = property_repo or PropertyRepository()
        self.user_repo = user_repo or UserRepository()
    
    def create_booking(
        self,
        db: Session,
        user_id: str,
        property_id: str,
        booking_date: datetime,
        shift_type: str,
        user_name: Optional[str] = None,
        cnic: Optional[str] = None,
        booking_source: str = "Bot",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new booking with validation and availability checking.
        
        This method:
        1. Validates user information (reads from session or user profile)
        2. Validates shift type
        3. Checks property availability
        4. Retrieves pricing information
        5. Creates the booking with Pending status
        6. Clears session booking contact details
        7. Returns formatted confirmation message
        
        Args:
            db: Database session
            user_id: User's unique identifier
            property_id: Property's unique identifier
            booking_date: Date for the booking
            shift_type: Type of shift (Day, Night, Full Day, Full Night)
            user_name: Optional user's full name (from prepare_booking_details)
            cnic: Optional user's CNIC (from prepare_booking_details)
            booking_source: Source of booking (Bot, Website, Third-Party)
            session_id: Optional session ID (to read/clear booking contact details)
        
        Returns:
            Dict containing:
                - success: bool - Whether booking was created successfully
                - message: str - Formatted confirmation message
                - booking_id: str - Created booking ID
                - error: str - Error message if failed
        
        Example:
            >>> service = BookingService()
            >>> result = service.create_booking(
            ...     db=db,
            ...     user_id="user-123",
            ...     property_id="prop-456",
            ...     booking_date=datetime(2024, 12, 25),
            ...     shift_type="Day",
            ...     user_name="John Doe",
            ...     cnic="1234567890123",
            ...     session_id="session-abc"
            ... )
            >>> if result["success"]:
            ...     print(result["booking_id"])
        """
        try:
            # Validate and update user information
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                logger.error(f"User not found: {user_id}")
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            # Get session if session_id provided (to read booking contact details)
            session = None
            if session_id:
                from app.repositories.session_repository import SessionRepository
                session_repo = SessionRepository()
                session = session_repo.get_by_id(db, session_id)
            
            # Priority order for name/CNIC:
            # 1. Provided parameters (from prepare_booking_details tool)
            # 2. Session booking fields (temporary, for this booking)
            # 3. User profile (permanent)
            final_name = user_name
            final_cnic = cnic
            
            if not final_name and session:
                final_name = session.booking_name
            if not final_name:
                final_name = user.name
                
            if not final_cnic and session:
                final_cnic = session.booking_cnic
            if not final_cnic:
                final_cnic = user.cnic
            
            if not final_name:
                return {
                    "success": False,
                    "error": "Please provide your full name for booking"
                }
            
            if not final_cnic:
                return {
                    "success": False,
                    "error": "Please provide your CNIC for booking"
                }
            
            # Validate CNIC if provided
            if cnic:
                # Remove dashes from CNIC
                cnic_clean = cnic.replace("-", "")
                
                # Validate CNIC length
                if len(cnic_clean) != CNIC_LENGTH:
                    return {
                        "success": False,
                        "error": f"Please enter {CNIC_LENGTH} digit CNIC"
                    }
                
                final_cnic = cnic_clean
            
            # DON'T update user table - just use the values for this booking
            print(f"📝 Using booking details - Name: {final_name}, CNIC: {final_cnic}")
            print(f"   User profile unchanged - Name: {user.name}, CNIC: {user.cnic}")
            
            # Validate shift type
            if shift_type not in VALID_SHIFT_TYPES:
                return {
                    "success": False,
                    "error": f"Invalid shift type. Please choose from: {', '.join(VALID_SHIFT_TYPES)}"
                }
            
            # Check property availability
            is_available = self.booking_repo.check_availability(
                db, property_id, booking_date, shift_type
            )
            
            if not is_available:
                # Get property name for error message
                property_details = self.property_repo.get_by_id(db, property_id)
                property_name = property_details.name if property_details else "Property"
                
                return {
                    "success": False,
                    "error": f"Sorry! {property_name} is already booked for {booking_date.strftime('%Y-%m-%d')} ({shift_type} shift). Please choose a different date or shift."
                }
            
            # Get pricing information
            pricing = self.property_repo.get_pricing(
                db, property_id, booking_date, shift_type
            )
            
            if not pricing:
                day_of_week = booking_date.strftime("%A")
                return {
                    "success": False,
                    "error": f"Pricing not found for {shift_type} shift on {day_of_week}. Please contact support."
                }
            
            # Get property details for confirmation message
            property_details = self.property_repo.get_property_details(db, property_id)
            if not property_details:
                return {
                    "success": False,
                    "error": "Property not found"
                }
            
            # Create booking ID
            booking_id = f"{final_name}-{booking_date.strftime('%Y-%m-%d')}-{shift_type}"
            
            # Format contact details for storage (use booking details, not user profile)
            formatted_cnic = f"{final_cnic[:5]}-{final_cnic[5:12]}-{final_cnic[12]}" if final_cnic and len(final_cnic) == 13 else final_cnic
            contact_details = f"Name: {final_name}, CNIC: {formatted_cnic}"
            
            # Create booking
            booking_data = {
                "booking_id": booking_id,
                "user_id": user_id,
                "property_id": property_id,
                "booking_date": booking_date.date(),
                "shift_type": shift_type,
                "total_cost": float(pricing.price),
                "booking_source": booking_source,
                "status": "Pending",
                "contact_details": contact_details,
                "booked_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            booking = self.booking_repo.create(db, booking_data)
            
            # Clear session booking contact details after successful booking
            if session:
                session.booking_name = None
                session.booking_cnic = None
                db.commit()
                print(f"✅ Cleared session booking contact details after booking creation")
            
            logger.info(f"Booking created successfully: {booking_id}")
            
            # Format confirmation message
            message = self._format_booking_confirmation(
                booking=booking,
                property_details=property_details,
                pricing=pricing
            )
            
            return {
                "success": True,
                "message": message,
                "booking_id": booking_id,
                "total_cost": float(pricing.price)
            }
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating booking: {e}", exc_info=True)
            raise BookingException(
                message="Database error occurred while creating booking. Please try again.",
                code="BOOKING_DB_ERROR"
            )
        except BookingException:
            # Re-raise BookingException without wrapping
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating booking: {e}", exc_info=True)
            raise BookingException(
                message="Something went wrong while creating your booking. Please try again or contact support.",
                code="BOOKING_CREATE_FAILED"
            )
    
    def confirm_booking(
        self,
        db: Session,
        booking_id: str,
        confirmed_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Confirm a booking after payment verification.
        
        Updates booking status from Waiting to Confirmed and logs the confirmation.
        
        Args:
            db: Database session
            booking_id: Booking ID to confirm
            confirmed_by: Optional identifier of who confirmed (admin ID, etc.)
        
        Returns:
            Dict containing:
                - success: bool - Whether confirmation was successful
                - message: str - Confirmation message
                - booking: Booking - Updated booking object
                - error: str - Error message if failed
        """
        try:
            # Get booking
            booking = self.booking_repo.get_by_booking_id(db, booking_id)
            
            if not booking:
                logger.warning(f"Booking not found for confirmation: {booking_id}")
                return {
                    "success": False,
                    "error": f"Booking not found: {booking_id}"
                }
            
            # Check if booking is in a confirmable state
            if booking.status == "Confirmed":
                return {
                    "success": False,
                    "error": "Booking is already confirmed"
                }
            
            if booking.status not in ["Pending", "Waiting"]:
                return {
                    "success": False,
                    "error": f"Cannot confirm booking with status: {booking.status}"
                }
            
            # Update booking status
            booking = self.booking_repo.update_status(db, booking_id, "Confirmed")
            
            logger.info(
                f"Booking confirmed: {booking_id} "
                f"(confirmed_by: {confirmed_by or 'system'})"
            )
            
            # Format confirmation message
            message = self._format_confirmation_message(booking)
            
            return {
                "success": True,
                "message": message,
                "booking": booking
            }
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error confirming booking: {e}", exc_info=True)
            raise BookingException(
                message="Database error occurred while confirming booking",
                code="BOOKING_CONFIRM_DB_ERROR"
            )
        except BookingException:
            # Re-raise BookingException without wrapping
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error confirming booking: {e}", exc_info=True)
            raise BookingException(
                message="Failed to confirm booking. Please try again.",
                code="BOOKING_CONFIRM_FAILED"
            )
    
    def cancel_booking(
        self,
        db: Session,
        booking_id: str,
        reason: Optional[str] = None,
        cancelled_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel a booking.
        
        Updates booking status to Cancelled and logs the cancellation reason.
        
        Args:
            db: Database session
            booking_id: Booking ID to cancel
            reason: Optional cancellation reason
            cancelled_by: Optional identifier of who cancelled
        
        Returns:
            Dict containing:
                - success: bool - Whether cancellation was successful
                - message: str - Cancellation message
                - booking: Booking - Updated booking object
                - error: str - Error message if failed
        """
        try:
            # Get booking
            booking = self.booking_repo.get_by_booking_id(db, booking_id)
            
            if not booking:
                logger.warning(f"Booking not found for cancellation: {booking_id}")
                return {
                    "success": False,
                    "error": f"Booking not found: {booking_id}"
                }
            
            # Check if booking can be cancelled
            if booking.status == "Cancelled":
                return {
                    "success": False,
                    "error": "Booking is already cancelled"
                }
            
            if booking.status == "Completed":
                return {
                    "success": False,
                    "error": "Cannot cancel a completed booking"
                }
            
            # Update booking status
            booking = self.booking_repo.update_status(db, booking_id, "Cancelled")
            
            logger.info(
                f"Booking cancelled: {booking_id} "
                f"(reason: {reason or 'not provided'}, "
                f"cancelled_by: {cancelled_by or 'system'})"
            )
            
            # Format cancellation message
            message = self._format_cancellation_message(booking, reason)
            
            return {
                "success": True,
                "message": message,
                "booking": booking
            }
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error cancelling booking: {e}", exc_info=True)
            raise BookingException(
                message="Database error occurred while cancelling booking",
                code="BOOKING_CANCEL_DB_ERROR"
            )
        except BookingException:
            # Re-raise BookingException without wrapping
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error cancelling booking: {e}", exc_info=True)
            raise BookingException(
                message="Failed to cancel booking. Please try again.",
                code="BOOKING_CANCEL_FAILED"
            )
    
    def get_user_bookings(
        self,
        db: Session,
        user_id: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get all bookings for a specific user.
        
        Args:
            db: Database session
            user_id: User's unique identifier
            limit: Optional maximum number of bookings to return
        
        Returns:
            Dict containing:
                - success: bool - Whether retrieval was successful
                - bookings: List[Booking] - List of booking objects
                - count: int - Number of bookings found
                - error: str - Error message if failed
        """
        try:
            # Verify user exists
            user = self.user_repo.get_by_id(db, user_id)
            if not user:
                logger.warning(f"User not found: {user_id}")
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            # Get user bookings
            bookings = self.booking_repo.get_user_bookings(db, user_id, limit)
            
            logger.info(f"Retrieved {len(bookings)} bookings for user: {user_id}")
            
            return {
                "success": True,
                "bookings": bookings,
                "count": len(bookings)
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving bookings: {e}", exc_info=True)
            raise BookingException(
                message="Database error occurred while retrieving bookings",
                code="BOOKING_RETRIEVE_DB_ERROR"
            )
        except BookingException:
            # Re-raise BookingException without wrapping
            raise
        except Exception as e:
            logger.error(f"Error retrieving bookings: {e}", exc_info=True)
            raise BookingException(
                message="Failed to retrieve bookings. Please try again.",
                code="BOOKING_RETRIEVE_FAILED"
            )
    
    def check_booking_status(
        self,
        db: Session,
        booking_id: str
    ) -> Dict[str, Any]:
        """
        Check the status of a booking.
        
        Args:
            db: Database session
            booking_id: Booking ID to check
        
        Returns:
            Dict containing:
                - success: bool - Whether retrieval was successful
                - booking: Booking - Booking object
                - status: str - Current booking status
                - message: str - Formatted status message
                - error: str - Error message if failed
        """
        try:
            # Get booking
            booking = self.booking_repo.get_by_booking_id(db, booking_id)
            
            if not booking:
                logger.warning(f"Booking not found: {booking_id}")
                return {
                    "success": False,
                    "error": f"Booking not found: {booking_id}"
                }
            
            # Format status message
            message = self._format_status_message(booking)
            
            logger.info(f"Booking status checked: {booking_id} - {booking.status}")
            
            return {
                "success": True,
                "booking": booking,
                "status": booking.status,
                "message": message
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error checking booking status: {e}", exc_info=True)
            raise BookingException(
                message="Database error occurred while checking booking status",
                code="BOOKING_STATUS_DB_ERROR"
            )
        except BookingException:
            # Re-raise BookingException without wrapping
            raise
        except Exception as e:
            logger.error(f"Error checking booking status: {e}", exc_info=True)
            raise BookingException(
                message="Failed to check booking status. Please try again.",
                code="BOOKING_STATUS_CHECK_FAILED"
            )
    
    def _format_booking_confirmation(
        self,
        booking: Booking,
        property_details: Dict[str, Any],
        pricing: Any
    ) -> str:
        """
        Format booking confirmation message with payment instructions.
        
        Args:
            booking: Created booking object
            property_details: Property information dict
            pricing: Pricing object
        
        Returns:
            str: Formatted confirmation message
        """
        # Format date for display
        formatted_date = booking.booking_date.strftime("%d %B %Y (%A)")
        
        # Calculate advance and remaining amounts
        # Assuming advance_percentage is stored in property (default to 100% if not available)
        advance_percentage = float(getattr(booking.property, 'advance_percentage', 100))
        total_cost = float(booking.total_cost)
        advance_amount = (advance_percentage / 100) * total_cost
        remaining_amount = total_cost - advance_amount
        
        message = f"""🎉 *Booking Request Created Successfully!*

📋 *Booking Details:*
🆔 Booking ID: `{booking.booking_id}`
🏠 Property: *{property_details['name']}*
📍 Location: {property_details.get('address', 'N/A')}
📅 Date: {formatted_date}
🕐 Shift: {booking.shift_type}
👥 Max Guests: {property_details.get('max_occupancy', 'N/A')}
💰 Total Amount: *Rs. {int(total_cost)}*

━━━━━━━━━━━━━━━━━━━━━━━━━

💳 *PAYMENT INSTRUCTIONS:*

Please send {advance_percentage}% advance *Rs. {int(advance_amount)}* to:
📱 EasyPaisa Number: *{EASYPAISA_NUMBER}*
✍🏼 Account Holder Name: *{EASYPAISA_ACCOUNT_HOLDER}*

Pay remaining Amount *Rs: {int(remaining_amount)}* on the {property_details.get('type', 'property')}

📸 *After Making Payment:*
1️⃣ Send me the payment screenshot, OR
2️⃣ Provide these payment details:
   • Your full name (as sender) ✅ Required
   • Amount paid ✅ Required
   • Transaction ID (if available) ⚪ Optional
   • Your phone number (if different) ⚪ Optional

━━━━━━━━━━━━━━━━━━━━━━━━━

✅ *Verification Process:*
• Our team will verify your payment
• You'll get confirmation within 5-10 minutes
• Then your booking will be confirmed!

⚠️ *Important Notes:*
• Complete payment within 30 minutes
• Keep your payment proof safe
• Payment must match exact amount: Rs. {int(total_cost)}

_Ready to pay? Send your payment proof after completing the transaction!_ 😊"""
        
        return message
    
    def _format_confirmation_message(self, booking: Booking) -> str:
        """
        Format booking confirmation message.
        
        Args:
            booking: Confirmed booking object
        
        Returns:
            str: Formatted confirmation message
        """
        formatted_date = booking.booking_date.strftime("%d %B %Y (%A)")
        
        message = f"""✅ *Booking Confirmed!*

🎉 Your booking has been confirmed!

📋 *Booking Details:*
🆔 Booking ID: `{booking.booking_id}`
🏠 Property: *{booking.property.name}*
📅 Date: {formatted_date}
🕐 Shift: {booking.shift_type}
💰 Amount: Rs. {int(booking.total_cost)}

Thank you for your booking! We look forward to hosting you! 😊"""
        
        return message
    
    def _format_cancellation_message(
        self,
        booking: Booking,
        reason: Optional[str] = None
    ) -> str:
        """
        Format booking cancellation message.
        
        Args:
            booking: Cancelled booking object
            reason: Optional cancellation reason
        
        Returns:
            str: Formatted cancellation message
        """
        message = f"""❌ *Booking Cancelled*

Your booking has been cancelled.

📋 *Booking Details:*
🆔 Booking ID: `{booking.booking_id}`
🏠 Property: *{booking.property.name}*
📅 Date: {booking.booking_date.strftime('%d %B %Y')}
🕐 Shift: {booking.shift_type}"""
        
        if reason:
            message += f"\n\n📝 *Reason:* {reason}"
        
        message += "\n\nIf you have any questions, please contact support."
        
        return message
    
    def _format_status_message(self, booking: Booking) -> str:
        """
        Format booking status message.
        
        Args:
            booking: Booking object
        
        Returns:
            str: Formatted status message
        """
        status_emoji = {
            "Pending": "⏳",
            "Waiting": "🔍",
            "Confirmed": "✅",
            "Cancelled": "❌",
            "Completed": "✔️",
            "Expired": "⌛"
        }
        
        emoji = status_emoji.get(booking.status, "📋")
        
        message = f"""{emoji} *Booking Status*

📋 *Booking Details:*
🆔 Booking ID: `{booking.booking_id}`
🏠 Property: *{booking.property.name}*
📅 Date: {booking.booking_date.strftime('%d %B %Y')}
🕐 Shift: {booking.shift_type}
💰 Amount: Rs. {int(booking.total_cost)}
📊 Status: *{booking.status}*"""
        
        # Add status-specific information
        if booking.status == "Pending":
            message += "\n\n⏳ Awaiting payment. Please complete payment to confirm your booking."
        elif booking.status == "Waiting":
            message += "\n\n🔍 Payment received. Under verification (usually takes 5-10 minutes)."
        elif booking.status == "Confirmed":
            message += "\n\n✅ Your booking is confirmed! Looking forward to hosting you!"
        elif booking.status == "Cancelled":
            message += "\n\n❌ This booking has been cancelled."
        elif booking.status == "Expired":
            message += "\n\n⌛ This booking has expired due to non-payment."
        
        return message
