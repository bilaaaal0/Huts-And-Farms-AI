# from langchain.tools import tool
# from app.database import SessionLocal
# from app.chatbot.models import (
#     Property, PropertyImage, PropertyAmenity, PropertyPricing, PropertyVideo,
#     OwnerProperty, Owner, User, Booking
# )
# from sqlalchemy import text

# from app.database import SessionLocal
# from app.chatbot.models import Property, PropertyPricing,Session
# import asyncio
# import aiohttp
# import base64
# from typing import List, Dict, Optional
# import requests
# import uuid
# from datetime import datetime




# @tool("get_property_id_from_name")
# def get_property_id_from_name(property_name: str) -> dict:
#     """
#     Get the unique property_id using the property name.
#     Returns the ID and basic property details if found.
#     """
#     with SessionLocal() as db:
#         sql = """
#         SELECT property_id, name, city, country
#         FROM properties
#         WHERE LOWER(name) = LOWER(:name)
#         LIMIT 1
#         """
#         result = db.execute(text(sql), {"name": property_name.strip()}).fetchone()
        
#         if not result:
#             return {
#                 "success": False,
#                 "message": f"❌ No property found with the name '{property_name}'.",
#                 "property_id": None
#             }

#         property_id, name, city, country = result
#         return {
#             "success": True,
#             "property_id": property_id,
#             "name": name,
#             "city": city,
#             "country": country,
#             "message": f"✅ Found: *{name}* in _{city}, {country}_ (ID: `{property_id}`)"
#         }




# @tool("list_properties")
# def list_properties(
#     session_id: str,
#     property_type: str = None,
#     city: str = "Karachi",
#     country: str = "Pakistan",
#     date: Optional[str] = None,
#     shift_type: Optional[str] = None,
#     min_price: Optional[float] = None,
#     max_price: Optional[float] = None,
#     max_occupancy: Optional[int] = None,
# ) -> dict:
#     """
#     Search and filter available properties for booking.
    
#     REQUIRED: property_type, date, shift_type must be provided.
#     Updates session state with search filters for future queries.
#     Only shows properties available on specified date/shift.
    
#     Args:
#         session_id: Current user session identifier (prompt has this info)
#         property_type: "hut" or "farm" (maps to database values)
#         city: Search city (default: "Karachi") 
#         country: Search country (default: "Pakistan")
#         date: Booking date in YYYY-MM-DD format
#         shift_type: "Day", "Night", or "Full Day"
#         min_price: Minimum price filter for selected shift
#         max_price: Maximum price filter for selected shift  
#         max_occupancy: Maximum guest capacity (±10 tolerance)
        
#     Returns:
#         {
#             "message": str (WhatsApp formatted list),
#             "results": [{"property_id", "name", "city", "shift_type", "price"}],
#             "count": int,
#             "error": str (if validation fails)
#         }
        
#     Validation errors:
#         - Missing property_type: "🤔 Do you want to see huts or farmhouses?"
#         - Missing date/shift: "📅 Please provide both date and shift type"
#         - Invalid shift: "❌ Invalid shift_type. Use 'Day', 'Night', or 'Full Day'"
#     """
#     if not property_type:
#         return {"error": "🤔 Do you want to see huts or farmhouses?"}
    
#     if not date or not shift_type:
#         return {"error": "📅 Please provide both the date and shift type (Day, Night, or Full Day)."}

#     with SessionLocal() as db:
#         # Determine which price column to filter
#         session = db.query(Session).filter_by(id=session_id).first()
#         if session:
#             session.property_type = property_type
#             # FIXED: Convert string date to datetime if needed
#             if isinstance(date, str):
#                 try:
#                     session.booking_date = datetime.strptime(date, "%Y-%m-%d").date()
#                 except ValueError:
#                     session.booking_date = None
#             else:
#                 session.booking_date = date
                
#             session.shift_type = shift_type
#             session.min_price = min_price
#             session.max_price = max_price
#             session.max_occupancy = max_occupancy
#             db.commit()

#         db.commit()
#         price_column = {
#             "Day": "pp.base_price_day_shift",
#             "Night": "pp.base_price_night_shift",
#             "Full Day": "pp.base_price_full_day"
#         }.get(shift_type)

#         if not price_column:
#             return {"error": "❌ Invalid shift_type. Please use 'Day', 'Night', or 'Full Day'."}

#         # SQL to get properties matching filters
#         sql = f"""
#             SELECT p.property_id, p.name, p.city, p.max_occupancy,
#                    pp.base_price_day_shift, pp.base_price_night_shift, pp.base_price_full_day
#             FROM properties p
#             JOIN property_pricing pp ON p.property_id = pp.property_id
#             WHERE p.city = :city AND p.country = :country AND p.type = :type
#         """

#         # Add price range filter
#         if min_price is not None:
#             sql += f" AND {price_column} >= :min_price"
#         if max_price is not None:
#             sql += f" AND {price_column} <= :max_price"

#         params = {
#             "city": city,
#             "country": country,
#             "type": property_type
#         }
#         if min_price is not None:
#             params["min_price"] = min_price
#         if max_price is not None:
#             params["max_price"] = max_price

#         result = db.execute(text(sql), params).fetchall()
#         if not result:
#             return {"message": "❌ No properties match the given filters."}

#         available_props = []
#         formatted_lines = []
        
#         for prop in result:
#             property_id, name, city, occupancy, day_price, night_price, full_price = prop

#             # Occupancy check
#             occupancy = occupancy + 10
#             if max_occupancy and (max_occupancy > occupancy):
#             # if max_occupancy and not (max_occupancy - 10 <= occupancy <= max_occupancy + 10):
#                 continue

#             # Check if property is already booked on this date and shift
#             booking_sql = """
#                 SELECT 1 FROM bookings
#                 WHERE property_id = :pid AND booking_date = :date
#                 AND shift_type = :shift AND status IN ('Pending', 'Confirmed')
#             """
#             booking = db.execute(text(booking_sql), {
#                 "pid": property_id,
#                 "date": date,
#                 "shift": shift_type
#             }).first()

#             if booking:
#                 continue  # Skip already booked

#             selected_price = {
#                 "Day": day_price,
#                 "Night": night_price,
#                 "Full Day": full_price
#             }.get(shift_type, "N/A")

#             # Save full details
#             available_props.append({
#                 "property_id": property_id,
#                 "name": name,
#                 "city": city,
#                 "shift_type": shift_type,
#                 "price": selected_price
#             })

#             # Build message line
#             formatted_lines.append(
#                 f"• *{name}*  — Rs {selected_price}"
#             )
        
#         if not available_props:
#             return {
#                 "message": f"❌ No {property_type}s available on {date} for {shift_type}.",
#                 "results": []
#             }

#         # Final message
#         message = f"📅 *{date}* | Shift: *{shift_type}*\n" + "\n".join(formatted_lines)

      

#         return {
#             "message": message,
#             "results": available_props,
#             "count": len(available_props)
#         }


# @tool("get_property_details")
# def get_property_details(property_id: str) -> dict:
#     """
#     Always use the property ID (UUID), not just the name. If getting details by name, use get_property_id_from_name first.
#     Get detailed information about a specific property by its ID.
#     Returns text details only - use get_property_images and get_property_videos for media.
#     """
#     print(property_id)
#     with SessionLocal() as db:
#         sql = """
#          SELECT p.name, p.description, p.city, p.country, p.max_occupancy, p.address, p.description,
#                 pp.base_price_day_shift, pp.base_price_night_shift, pp.base_price_full_day,
#                 pa.type, pa.value 
#          FROM properties p
#          LEFT JOIN property_pricing pp ON p.property_id = pp.property_id
#          LEFT JOIN property_amenities pa ON p.property_id = pa.property_id
#          WHERE p.property_id = :property_id
#         """
#         params = {"property_id": property_id}
#         result = db.execute(text(sql), params).fetchall()
        
#         if not result:
#             return {"error": f"No details found for property ID `{property_id}`."}
        
#         # Process the data
#         property_info = {}
#         amenities = []
        
#         for row in result:
#             name, description, city, country, max_occupancy, address, desc, day_price, night_price, full_price, amenity_type, amenity_value = row
            
#             # Set basic property info (will be same for all rows)
#             if not property_info:
#                 property_info = {
#                     "name": name,
#                     "description": desc,
#                     "city": city,
#                     "country": country,
#                     "max_occupancy": max_occupancy,
#                     "address": address,
#                     "day_price": day_price,
#                     "night_price": night_price,
#                     "full_price": full_price
#                 }
            
#             # Collect amenities
#             if amenity_type and amenity_value:
#                 amenity_str = f"{amenity_type} - {amenity_value}"
#                 if amenity_str not in amenities:
#                     amenities.append(amenity_str)
        
#         # Format text response
#         text_response = (f"*{property_info['name']}* in _{property_info['city']}, {property_info['country']}_\n"
#                         f"Max Guests: {property_info['max_occupancy']}\n"
#                         f"Address: {property_info['address']}\n"
#                         f"Description: {property_info['description']}\n"
#                         f"Day Price: Rs.{property_info['day_price']}/-, "
#                         f"Night Price: Rs.{property_info['night_price']}/-, "
#                         f"Full Day Price: Rs.{property_info['full_price']}/-\n"
#                         f"Amenities: {', '.join(amenities) if amenities else 'None listed'}")

#         # images = get_property_images.invoke({"property_id": property_id})
#         return {
#             "success": True,
#             "property_id": property_id,
#             "details": text_response,
#             "property_info": property_info,
#             # "images": images
#         }









# @tool("get_property_images")
# def get_property_images(property_id: str) -> dict:
#     """
#     Get all public image URLs for a specific property by its ID.
#     """
#     with SessionLocal() as db:
#         sql = """
#             SELECT DISTINCT pi.image_url 
#             FROM property_images pi
#             WHERE pi.property_id = :property_id
#             AND pi.image_url IS NOT NULL
#             AND pi.image_url != ''
#         """
#         result = db.execute(text(sql), {"property_id": property_id}).fetchall()

#     image_urls = [row[0].strip() for row in result if row[0] and row[0].strip()]

#     return {
#         "success": True,
#         "property_id": property_id,
#         "images": image_urls,
#         "images_count": len(image_urls),
#         "message": "Fetched image URLs successfully" if image_urls else "No images found"
#     }


# @tool("get_property_videos")
# def get_property_videos(property_id: str) -> dict:
#     """
#     Get all public video URLs for a specific property by its ID.
#     """
#     with SessionLocal() as db:
#         sql = """
#             SELECT DISTINCT pv.video_url 
#             FROM property_videos pv
#             WHERE pv.property_id = :property_id
#             AND pv.video_url IS NOT NULL
#             AND pv.video_url != ''
#         """
#         result = db.execute(text(sql), {"property_id": property_id}).fetchall()

#     video_urls = [row[0].strip() for row in result if row[0] and row[0].strip()]

#     return {
#         "success": True,
#         "property_id": property_id,
#         "videos": video_urls,
#         "videos_count": len(video_urls),
#         "message": "Fetched video URLs successfully" if video_urls else "No videos found"
#     }






# @tool("Check_availability_of_property")
# async def check_availability_of_property(property_id: str, dates: List[str]) -> Dict[str, str]:
#     """
#     When to use: When users want to check availability for specific dates on a particular property.
#     Description: Checks if a property is available on given date(s) and shows which shifts are free. Use when user has already selected a specific property.
#     Use cases:

#     "Is Green Valley available next weekend?"
#     "Check availability for December 20-25"
#     "What shifts are free on Christmas?"
#     Before proceeding with booking confirmation

#     Returns: Date-by-date availability status with shift information
#     """
#     availability = {}

#     with SessionLocal() as db:
#         for date in dates:
#             sql = """
#                 SELECT shift_type FROM bookings
#                 WHERE property_id = :property_id 
#                   AND booking_date::date = :date 
#                   AND status IN ('Pending', 'Confirmed')
#             """
#             result = db.execute(
#                 text(sql),
#                 {"property_id": property_id, "date": date}
#             ).fetchall()

#             shifts = [row[0] for row in result]

#             if not shifts:
#                 availability[date] = "✅ available full day"
#             elif len(shifts) >= 2:
#                 availability[date] = "❌ not available"
#             elif len(shifts) == 1:
#                 shift = shifts[0]
#                 if shift == "Full Day":
#                     availability[date] = "❌ not available"
#                 elif shift == "Day":
#                     availability[date] = "✅ available night shift"
#                 elif shift == "Night":
#                     availability[date] = "✅ available day shift"
#                 else:
#                     availability[date] = f"❓ unknown shift: {shift}"
#             else:
#                 availability[date] = "❓ unknown status"

#     return availability


from email.mime import message
from langchain.tools import tool
from langchain_core.tools import StructuredTool
from app.database import SessionLocal
from app.chatbot.models import (
    Property, PropertyImage, PropertyAmenity, PropertyPricing, PropertyVideo,
    OwnerProperty, Owner, User, Booking, Session
)
from sqlalchemy import text
from typing import List, Dict, Optional
import asyncio
import aiohttp
import base64
import requests
import uuid
from datetime import datetime

# Import the Pydantic models
from app.chatbot.pydantic_models import (
    PropertyIdResponse, PropertyListResponse, PropertyDetailsResponse,
    PropertyImagesResponse, PropertyVideosResponse, AvailabilityResponse,
    PropertyResult, PropertyInfo
)


def get_property_id_from_name_func(session_id: str, property_name: str) -> PropertyIdResponse:
    """
    Get the unique property_id using the property name.
    Returns the ID and basic property details if found.
    """
    with SessionLocal() as db:
        sql = """
        SELECT property_id, name, city, country
        FROM properties
        WHERE LOWER(name) = LOWER(:name)
        LIMIT 1
        """
        result = db.execute(text(sql), {"name": property_name.strip()}).fetchone()
        session = db.query(Session).filter_by(id=session_id).first()
        
        if not result:
            return PropertyIdResponse(
                success=False,
                message=f"❌ No property found with the name '{property_name}'.",
                property_id=None
            )

        property_id, name, city, country = result

        session.property_id = str(property_id)
        db.commit()

        from uuid import UUID
        property_id_uuid = UUID(str(property_id))

        return PropertyIdResponse(
            success=True,
            property_id=property_id_uuid,
            name=name,
            city=city,
            country=country,
            message=f"✅ Found: *{name}* in _{city}, {country}_ (ID: `{property_id}`)"
        )
from enum import Enum

class DayOfWeek(str, Enum):
    saturday = "saturday"
    sunday = "sunday"
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"

class ShiftType(str, Enum):
    day = "Day"
    night = "Night"
    full_day = "Full Day"
    full_night = "Full Night"

class PropertyType(str, Enum):
    hut = "hut"
    farm = "farm"


def list_properties_func(
    session_id: str,
    property_type: Optional[PropertyType] = None,
    city: str = "Karachi",
    country: str = "Pakistan",
    date: Optional[str] = None,
    day_of_the_week: Optional[DayOfWeek] = None,
    shift_type: Optional[ShiftType] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    max_occupancy: Optional[int] = None,
) -> PropertyListResponse:
    
    with SessionLocal() as db:
        # Update session
        session = db.query(Session).filter_by(id=session_id).first()
        print(f"property_type parameter: {property_type}")
        print(f"date parameter: {date}")
        print(f"shift_type parameter: {shift_type}")
        
        # Check for property type - use current parameter OR session value
        current_property_type = property_type or session.property_type
        if not current_property_type:
            return PropertyListResponse(
                message="",
                error="🤔 Do you want to see huts or farmhouses?"
            )
        
        # Check for required parameters - use current parameters OR session values
        current_date = date or (session.booking_date.strftime("%Y-%m-%d") if session.booking_date else None)
        current_shift_type = shift_type or session.shift_type
        
        if not current_date or not current_shift_type:
            return PropertyListResponse(
                message="",
                error = """**📅 Please provide the following details so we can find the best available farmhouse or hut for you:**

                    * **Date** of booking
                    * **Shift Type**: Day, Night, Full Day, or Full Night
                    * **Number of People**
                    * **Price Range** (Minimum and Maximum) (If applicable)"""
            )

        # Calculate day of week from date if not provided
        if current_date and not day_of_the_week:
            try:
                date_obj = datetime.strptime(current_date, "%Y-%m-%d")
                day_name = date_obj.strftime("%A").lower()
                day_of_the_week = DayOfWeek(day_name)
            except (ValueError, ValueError):
                return PropertyListResponse(
                    message="",
                    error="❌ Invalid date format. Please use YYYY-MM-DD format."
                )
    
        # Update session with new values (only if provided)
        if session:
            if property_type:
                session.property_type = property_type
            if date:
                try:
                    session.booking_date = datetime.strptime(date, "%Y-%m-%d").date()
                except ValueError:
                    pass  # Keep existing value
            if shift_type:
                session.shift_type = shift_type
            if min_price is not None:
                session.min_price = min_price
            if max_price is not None:
                session.max_price = max_price
            if max_occupancy is not None:
                session.max_occupancy = max_occupancy
            db.commit()

        # Validate shift_type
        valid_shifts = ["Day", "Night", "Full Day", "Full Night"]
        if current_shift_type not in valid_shifts:
            return PropertyListResponse(
                message="",
                error="❌ Invalid shift_type. Please use 'Day', 'Night', 'Full Day', or 'Full Night'."
            )
        print("hey")
        # SQL to get properties with exact pricing based on day of week and shift type
        sql = """
            SELECT DISTINCT p.property_id, p.name, p.city, p.max_occupancy, psp.price
            FROM properties p
            JOIN property_pricing pp ON p.property_id = pp.property_id
            JOIN property_shift_pricing psp ON pp.pricing_id = psp.pricing_id
            WHERE p.city = :city 
            AND p.country = :country 
            AND p.type = :type
            AND psp.day_of_week = :day_of_week
            AND psp.shift_type = :shift_type
        """
        print("hello")
        # Add price range filters
        if min_price is not None:
            sql += " AND psp.price >= :min_price"
        if max_price is not None:
            sql += " AND psp.price <= :max_price"

        params = {
            "city": city,
            "country": country,
            "type": current_property_type,  # Use the resolved property type
            "day_of_week": day_of_the_week,
            "shift_type": current_shift_type  # Use the resolved shift type
        }
        
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price

        result = db.execute(text(sql), params).fetchall()
        
        if not result:
            return PropertyListResponse(
                message="❌ No properties match the given filters.",
            )

        available_props = []
        
        for prop in result:
            property_id, name, city, occupancy, price = prop

            # Occupancy check
            occupancy = occupancy + 10
            if max_occupancy and (max_occupancy > occupancy):
                continue

            # Check if property is already booked on this date and shift
            booking_sql = """
                SELECT 1 FROM bookings
                WHERE property_id = :pid AND booking_date = :date
                AND shift_type = :shift AND status IN ('Pending', 'Confirmed')
            """
            booking = db.execute(text(booking_sql), {
                "pid": property_id,
                "date": current_date,  # Use resolved date
                "shift": current_shift_type  # Use resolved shift type
            }).first()

            if booking:
                continue  # Skip already booked

            # Save property details
            available_props.append(PropertyResult(
                property_id=property_id,
                name=name,
                city=city,
                shift_type=current_shift_type,  # Use resolved shift type
                price=float(price)
            ))
        
        if not available_props:
            return PropertyListResponse(
                message=f"❌ No {current_property_type}s available on {current_date} for {current_shift_type}."
            )

        # Format date with day name
        try:
            date_obj = datetime.strptime(current_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d-%B-%Y (%A)")
        except:
            formatted_date = current_date
        
        # Property type display name
        property_display = "farmhouses" if current_property_type == "farm" else "huts"
        
        # Create numbered list
        numbered_lines = []
        for i, prop in enumerate(available_props, 1):
            numbered_lines.append(f"{i}. {prop.name}  Price (Rs) - {int(prop.price)}")
        
        # Final message
        header = f"Available *{property_display}* and their *Price* for *{formatted_date} {current_shift_type}* shift:"
        message = header + "\n" + "\n\n".join(numbered_lines)
        message += f"\n\nAgr ap inme sy kisi {current_property_type} ki details ya pictures aur videos chahte hain to mujhe uska naam batayein! Shukriya."

        return PropertyListResponse(
            message=message,
            # results=available_props,
            # count=len(available_props)
        )
# def list_properties_func(
#     session_id: str,
#     property_type: Optional[PropertyType] = None,
#     city: str = "Karachi",
#     country: str = "Pakistan",
#     date: Optional[str] = None,
#     day_of_the_week: Optional[DayOfWeek] = None ,
#     shift_type: Optional[ShiftType] = None,
#     min_price: Optional[float] = None,
#     max_price: Optional[float] = None,
#     max_occupancy: Optional[int] = None,
# ) -> PropertyListResponse:
#     """
#     Search and filter available properties for booking.

#     REQUIRED:
#         - property_type
#         - date
#         - shift_type

#     BEHAVIOR:
#         - `day_of_the_week` will be automatically 
#           calculated from the given `date`.(Possible values are "saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday")
#         - Updates session state with search filters for future queries.
#         - Only shows properties available on the specified date and shift type.
    
#     PARAMETERS:
#         session_id       : Unique identifier for the user session.
#         property_type    : Category/type of property to filter by.
#         city             : City where the property is located (default: "Karachi").
#         country          : Country where the property is located (default: "Pakistan").
#         date             : Booking date in YYYY-MM-DD format.
#         day_of_the_week  : Optional. Specific day of week (auto-filled from `date` if None).
#         shift_type       : Type of booking shift (day, night, full_day, full_night).
#         min_price        : Minimum price filter.
#         max_price        : Maximum price filter.
#         max_occupancy    : Maximum occupancy filter.
#     """
#     with SessionLocal() as db:
#         # Update session
#         session = db.query(Session).filter_by(id=session_id).first()

#         # property_type = session.property_type
#         # date = session.booking_date
#         # min_price = session.min_price
#         # max_price = session.max_price
#         # max_occupancy = session.max_occupancy
#         # shift_type = session.shift_type
#         if not session.property_type and not property_type:
#             return PropertyListResponse(
#                 message="",
#                 error="🤔 Do you want to see huts or farmhouses?"
#             )
        
#         if (not session.booking_date or not session.shift_type) and (not date or not shift_type):
#             return PropertyListResponse(
#                 message="",
#                 error = """**📅 Please provide the following details so we can find the best available farmhouse or hut for you:**

#                     * **Date** of booking
#                     * **Shift Type**: Day, Night, or Full Day
#                     * **Number of People**
#                     * **Price Range** (Minimum and Maximum) (If applicable)"""
#             )

    
#         if session:
#             session.property_type = property_type
#             if isinstance(date, str):
#                 try:
#                     session.booking_date = datetime.strptime(date, "%Y-%m-%d").date()
#                 except ValueError:
#                     session.booking_date = None
#             else:
#                 session.booking_date = date
                
#             session.shift_type = shift_type
#             session.min_price = min_price
#             session.max_price = max_price
#             session.max_occupancy = max_occupancy
#             db.commit()

#         price_column = {
#             "Day": "pp.base_price_day_shift",
#             "Night": "pp.base_price_night_shift",
#             "Full Day": "pp.base_price_full_day"
#         }.get(shift_type)

#         if not price_column:
#             return PropertyListResponse(
#                 message="",
#                 error="❌ Invalid shift_type. Please use 'Day', 'Night', or 'Full Day'."
#             )

#         # SQL to get properties matching filters
#         sql = f"""
#             SELECT p.property_id, p.name, p.city, p.max_occupancy,
#                    pp.base_price_day_shift, pp.base_price_night_shift, pp.base_price_full_day
#             FROM properties p
#             JOIN property_pricing pp ON p.property_id = pp.property_id
#             WHERE p.city = :city AND p.country = :country AND p.type = :type
#         """

#         # Add price range filter
#         if min_price is not None:
#             sql += f" AND {price_column} >= :min_price"
#         if max_price is not None:
#             sql += f" AND {price_column} <= :max_price"

#         params = {
#             "city": city,
#             "country": country,
#             "type": property_type
#         }
#         if min_price is not None:
#             params["min_price"] = min_price
#         if max_price is not None:
#             params["max_price"] = max_price

#         result = db.execute(text(sql), params).fetchall()
#         if not result:
#             return PropertyListResponse(
#                 message="❌ No properties match the given filters.",
#             )

#         available_props = []
        
#         for prop in result:
#             property_id, name, city, occupancy, day_price, night_price, full_price = prop

#             # Occupancy check
#             occupancy = occupancy + 10
#             if max_occupancy and (max_occupancy > occupancy):
#                 continue

#             # Check if property is already booked on this date and shift
#             booking_sql = """
#                 SELECT 1 FROM bookings
#                 WHERE property_id = :pid AND booking_date = :date
#                 AND shift_type = :shift AND status IN ('Pending', 'Confirmed')
#             """
#             booking = db.execute(text(booking_sql), {
#                 "pid": property_id,
#                 "date": date,
#                 "shift": shift_type
#             }).first()

#             if booking:
#                 continue  # Skip already booked

#             selected_price = {
#                 "Day": day_price,
#                 "Night": night_price,
#                 "Full Day": full_price
#             }.get(shift_type, 0)

#             # Save full details
#             available_props.append(PropertyResult(
#                 property_id=property_id,
#                 name=name,
#                 city=city,
#                 shift_type=shift_type,
#                 price=selected_price
#             ))
        
#         if not available_props:
#             return PropertyListResponse(
#                 message=f"❌ No {property_type}s available on {date} for {shift_type}."
#             )

#         # Format date with day name
#         try:
#             date_obj = datetime.strptime(date, "%Y-%m-%d")
#             formatted_date = date_obj.strftime("%d-%B-%Y (%A)")
#         except:
#             formatted_date = date
        
#         # Property type display name
#         property_display = "farmhouses" if property_type == "farm" else "huts"
        
#         # Create numbered list
#         numbered_lines = []
#         for i, prop in enumerate(available_props, 1):
#             numbered_lines.append(f"{i}. {prop.name}     {int(prop.price)}")
        
#         # Final message
#         header = f"Available *{property_display}* and their *Price* for *{formatted_date} {shift_type}* shift:"
#         message = header + "\n" + "\n\n".join(numbered_lines)
#         message += f"\n\nAgr ap inme sy kisi {property_type} ki details ya pictures aur videos chahte hain to mujhe uska naam batayein! Shukriya."

#         return PropertyListResponse(
#             message=message,
#             # results=available_props,
#             # count=len(available_props)
#         )



@tool("introduction_message")
def introduction_message() -> str:
    """
    Returns the introduction message for HutBuddy AI booking assistant.
    
    Use this tool when:
    - User sends greeting messages like "hello", "hi", "salam", "assalam o alaikum"
    - User asks "what can you do" or "help me"
    - User starts a new conversation
    - User asks about the bot's capabilities or services
    - User sends any initial greeting or inquiry about services
    
    The tool provides a comprehensive introduction explaining:
    - Bot identity as HutBuddy AI booking assistant
    - Available services (finding huts/farmhouses, checking availability, booking process)
    - Required information needed from users (date, shift type, number of people, price range)
    - Friendly greeting response in local language (Urdu/Roman)
    
    Also use this when user says "salam" in any form - respond with "Walikum Assalam" instead of Hello.

    """
    message = """
    Hello! Main HutBuddy AI hun, ap ka booking assistant.

    Main ap ki madad kar sakta hun:
    ‣   🏡 Huts aur farmhouses book krny mein
    ‣  📅 Availability check karne mein
    ‣   💸 Booking aur payment process mein guide karne mein
    
    Agar aap mujhe yeh tafseelat batayenge to main aapko sab se behtareen farmhouses/huts dikhaunga:

       ‣ *Farmhouse / hut*
       ‣ *Date*
       ‣ *Shift Type (Day / Night / Full Day / Full Night)*
            - Day   -> 8 am to 6 pm
            - Night -> 8 pm to 6 am
            - Full Day   -> 8 am to 6 am of next day
            - Full Night -> 8 pm to 6 pm of next day
       ‣ *No. of people*
       ‣ *Price Range* (optional)

    """
    return message

# def get_property_details_func(session_id: str) -> PropertyDetailsResponse:
#     """
#     Always use the property ID (UUID), not just the name. If getting details by name, use get_property_id_from_name first.
#     Get detailed information about a specific property by its ID.
#     Returns text details only - use get_property_images and get_property_videos for media.
#     """
#     with SessionLocal() as db:
#         session = db.query(Session).filter_by(id=session_id).first()
        
#         if not session or not session.property_id:
#             return PropertyDetailsResponse(
#                 success=False,
#                 message="Please provide property name first.",
#                 error="Please provide property name first.",
#                 property_id=None
#             )
            
#         property_id = session.property_id
        
#         sql = """
#          SELECT p.name, p.description, p.city, p.country, p.max_occupancy, p.address, 
#                 pp.base_price_day_shift, pp.base_price_night_shift, pp.base_price_full_day,
#                 pa.type, pa.value 
#          FROM properties p
#          LEFT JOIN property_pricing pp ON p.property_id = pp.property_id
#          LEFT JOIN property_amenities pa ON p.property_id = pa.property_id
#          WHERE p.property_id = :property_id
#         """
#         params = {"property_id": property_id}
#         result = db.execute(text(sql), {"property_id": property_id}).fetchall()
        
#         if not result:
#             return PropertyDetailsResponse(
#                 success=False,
#                 message=f"No details found for property ID `{property_id}`.",
#                 error=f"No details found for property ID `{property_id}`.",
#                 property_id=property_id
#             )
        
#         # Process the data
#         property_info = {}
#         amenities = []
        
#         for row in result:
#             name, description, city, country, max_occupancy, address, day_price, night_price, full_price, amenity_type, amenity_value = row
            
#             # Set basic property info (will be same for all rows)
#             if not property_info:
#                 property_info = {
#                     "name": name,
#                     "description": description,
#                     "city": city,
#                     "country": country,
#                     "max_occupancy": max_occupancy,
#                     "address": address,
#                     "day_price": day_price,
#                     "night_price": night_price,
#                     "full_price": full_price
#                 }
            
#             # Collect amenities
#             if amenity_type and amenity_value:
#                 amenity_str = f"{amenity_type} - {amenity_value}"
#                 if amenity_str not in amenities:
#                     amenities.append(amenity_str)
        
#         # Format text response
#         text_response = (f"*{property_info['name']}* in _{property_info['city']}, {property_info['country']}_\n"
#                         f"Max Guests: {property_info['max_occupancy']}\n"
#                         f"Address: {property_info['address']}\n"
#                         f"Description: {property_info['description']}\n"
#                         f"Day Price: Rs.{property_info['day_price']}/-, "
#                         f"Night Price: Rs.{property_info['night_price']}/-, "
#                         f"Full Day Price: Rs.{property_info['full_price']}/-\n"
#                         f"Amenities: {', '.join(amenities) if amenities else 'None listed'}")
        
#         from uuid import UUID
#         property_id_uuid = UUID(str(property_id))

#         return PropertyDetailsResponse(
#             success=True,
#             message="Property details retrieved successfully",
#             property_id=property_id_uuid,
#             details=text_response,
#             property_info=PropertyInfo(**property_info)
#         )


def get_property_images_func(session_id: str) -> PropertyImagesResponse:
    """
    Get all public image URLs for a specific property by its ID (getting property_id from session).
    """
    with SessionLocal() as db:
        session = db.query(Session).filter_by(id=session_id).first()
        
        print(f"Property Id : {session.property_id}")
        if not session or not session.property_id:
            return PropertyImagesResponse(
                success=False,
                message="Please provide property name first.",
                property_id=None,
                images=[],
                images_count=0
            )
            
        property_id = session.property_id
        
        sql = """
            SELECT DISTINCT pi.image_url 
            FROM property_images pi
            WHERE pi.property_id = :property_id
            AND pi.image_url IS NOT NULL
            AND pi.image_url != ''
        """
        result = db.execute(text(sql), {"property_id": property_id}).fetchall()

        image_urls = [row[0].strip() for row in result if row[0] and row[0].strip()]

        from uuid import UUID
        property_id_uuid = UUID(str(property_id))

        return PropertyImagesResponse(
            success=True,
            message="Fetched image URLs successfully" if image_urls else "No images found",
            property_id=property_id_uuid,
            images=image_urls,
            images_count=len(image_urls)
        )


def get_property_videos_func(session_id: str) -> PropertyVideosResponse:
    """
    Get all public video URLs for a specific property by its ID (getting property_id from session).
    """
    with SessionLocal() as db:
        session = db.query(Session).filter_by(id=session_id).first()
        
        if not session or not session.property_id:
            return PropertyVideosResponse(
                success=False,
                message="Please provide property name first.",
                property_id=None,
                videos=[],
                videos_count=0
            )
            
        property_id = session.property_id
        
        sql = """
            SELECT DISTINCT pv.video_url 
            FROM property_videos pv
            WHERE pv.property_id = :property_id
            AND pv.video_url IS NOT NULL
            AND pv.video_url != ''
        """
        result = db.execute(text(sql), {"property_id": property_id}).fetchall()

        video_urls = [row[0].strip() for row in result if row[0] and row[0].strip()]

        from uuid import UUID
        property_id_uuid = UUID(str(property_id))

        return PropertyVideosResponse(
            success=True,
            message="Fetched video URLs successfully" if video_urls else "No videos found",
            property_id=property_id_uuid,
            videos=video_urls,
            videos_count=len(video_urls)
        )
    
def get_property_details_func(session_id: str) -> PropertyDetailsResponse:
    """
    Always use the property ID (UUID), not just the name. If getting details by name, use get_property_id_from_name first.
    Get detailed information about a specific property by its ID.
    Returns text details only - use get_property_images and get_property_videos for media.
    """
    with SessionLocal() as db:
        session = db.query(Session).filter_by(id=session_id).first()
        
        if not session or not session.property_id:
            return PropertyDetailsResponse(
                success=False,
                message="Please provide property name first.",
                error="Please provide property name first.",
                property_id=None
            )
            
        property_id = session.property_id
        
        # Get basic property info
        property_sql = """
         SELECT p.name, p.description, p.city, p.country, p.max_occupancy, p.address
         FROM properties p
         WHERE p.property_id = :property_id
        """
        
        property_result = db.execute(text(property_sql), {"property_id": property_id}).first()
        
        if not property_result:
            return PropertyDetailsResponse(
                success=False,
                message=f"No details found for property ID `{property_id}`.",
                error=f"No details found for property ID `{property_id}`.",
                property_id=property_id
            )
        
        name, description, city, country, max_occupancy, address = property_result
        
        # Get pricing info - show sample pricing for different days/shifts
        pricing_sql = """
         SELECT psp.day_of_week, psp.shift_type, psp.price
         FROM property_pricing pp
         JOIN property_shift_pricing psp ON pp.pricing_id = psp.pricing_id
         WHERE pp.property_id = :property_id
         ORDER BY 
           CASE psp.day_of_week 
             WHEN 'monday' THEN 1
             WHEN 'tuesday' THEN 2
             WHEN 'wednesday' THEN 3
             WHEN 'thursday' THEN 4
             WHEN 'friday' THEN 5
             WHEN 'saturday' THEN 6
             WHEN 'sunday' THEN 7
           END,
           CASE psp.shift_type
             WHEN 'Day' THEN 1
             WHEN 'Night' THEN 2
             WHEN 'Full Day' THEN 3
             WHEN 'Full Night' THEN 4
           END
        """
        
        pricing_results = db.execute(text(pricing_sql), {"property_id": property_id}).fetchall()
        
        # Get amenities
        amenities_sql = """
         SELECT pa.type, pa.value 
         FROM property_amenities pa
         WHERE pa.property_id = :property_id
        """
        
        amenities_results = db.execute(text(amenities_sql), {"property_id": property_id}).fetchall()
        
        # Process amenities
        amenities = []
        for row in amenities_results:
            amenity_type, amenity_value = row
            if amenity_type and amenity_value:
                amenity_str = f"{amenity_type} - {amenity_value}"
                if amenity_str not in amenities:
                    amenities.append(amenity_str)
        
        # Process pricing info
        pricing_text = ""
        if pricing_results:
            pricing_text = "\n*Pricing by Day & Shift:*\n"
            current_day = None
            for day_of_week, shift_type, price in pricing_results:
                if current_day != day_of_week:
                    pricing_text += f"\n*{day_of_week.capitalize()}:*\n"
                    current_day = day_of_week
                pricing_text += f"  • {shift_type}: Rs.{int(price)}/-\n"
        else:
            pricing_text = "\nPricing: Contact for rates"
        
        # Format text response
        text_response = (f"*{name}* in _{city}, {country}_\n"
                        f"Max Guests: {max_occupancy}\n"
                        f"Address: {address}\n"
                        f"Description: {description}\n"
                        f"{pricing_text}"
                        f"Amenities: {', '.join(amenities) if amenities else 'None listed'}")
        
        from uuid import UUID
        property_id_uuid = UUID(str(property_id))
        
        # Create property info with sample pricing (using first available price)
        sample_price = pricing_results[0][2] if pricing_results else 0
        property_info = {
            "name": name,
            "description": description,
            "city": city,
            "country": country,
            "max_occupancy": max_occupancy,
            "address": address,
            "day_price": sample_price,  # Using sample price for backward compatibility
            "night_price": sample_price,
            "full_price": sample_price
        }

        return PropertyDetailsResponse(
            success=True,
            message="Property details retrieved successfully",
            property_id=property_id_uuid,
            details=text_response,
            property_info=PropertyInfo(**property_info)
        )


async def check_availability_of_property_func(session_id: str, dates: List[str]) -> AvailabilityResponse:
    """
    When to use: When users want to check availability for specific dates on a particular property.
    Description: Checks if a property is available on given date(s) and shows which shifts are free. 
    Use when user has already selected a specific property.
    Use cases:
    - "Is Green Valley available next weekend?"
    - "Check availability for December 20-25"
    - "What shifts are free on Christmas?"
    - Before proceeding with booking confirmation

    Returns: Date-by-date availability status with shift information
    """
    availability = {}

    with SessionLocal() as db:
        session = db.query(Session).filter_by(id=session_id).first()
        
        if not session or not session.property_id:
            return AvailabilityResponse(
                availability={"error": "Please provide property name first."}
            )
            
        property_id = session.property_id
        
        for date in dates:
            sql = """
                SELECT shift_type FROM bookings
                WHERE property_id = :property_id 
                  AND booking_date::date = :date 
                  AND status IN ('Pending', 'Confirmed')
            """
            result = db.execute(
                text(sql),
                {"property_id": property_id, "date": date}
            ).fetchall()

            shifts = [row[0] for row in result]

            if not shifts:
                availability[date] = "✅ Available for all shifts (Day, Night, Full Day, Full Night)"
            else:
                # Check which shifts are booked
                booked_shifts = set(shifts)
                all_shifts = {"Day", "Night", "Full Day", "Full Night"}
                
                # If Full Day or Full Night is booked, property is unavailable
                if "Full Day" in booked_shifts or "Full Night" in booked_shifts:
                    availability[date] = "❌ Not available (Full day/night booked)"
                # If both Day and Night are booked, property is unavailable
                elif "Day" in booked_shifts and "Night" in booked_shifts:
                    availability[date] = "❌ Not available (Both day & night shifts booked)"
                else:
                    # Show which shifts are still available
                    available_shifts = all_shifts - booked_shifts
                    # Remove conflicting shifts
                    if "Day" in booked_shifts:
                        available_shifts.discard("Full Day")
                        available_shifts.discard("Full Night")
                    if "Night" in booked_shifts:
                        available_shifts.discard("Full Day") 
                        available_shifts.discard("Full Night")
                    
                    if available_shifts:
                        available_list = sorted(list(available_shifts))
                        availability[date] = f"✅ Available shifts: {', '.join(available_list)}"
                    else:
                        availability[date] = "❌ Not available"

    return AvailabilityResponse(availability=availability)

# async def check_availability_of_property_func(session_id: str, dates: List[str]) -> AvailabilityResponse:
#     """
#     When to use: When users want to check availability for specific dates on a particular property.
#     Description: Checks if a property is available on given date(s) and shows which shifts are free. Use when user has already selected a specific property.
#     Use cases:

#     "Is Green Valley available next weekend?"
#     "Check availability for December 20-25"
#     "What shifts are free on Christmas?"
#     Before proceeding with booking confirmation

#     Returns: Date-by-date availability status with shift information
#     """
#     availability = {}

#     with SessionLocal() as db:
#         session = db.query(Session).filter_by(id=session_id).first()
        
#         if not session or not session.property_id:
#             return AvailabilityResponse(
#                 availability={"error": "Please provide property name first."}
#             )
            
#         property_id = session.property_id
        
#         for date in dates:
#             sql = """
#                 SELECT shift_type FROM bookings
#                 WHERE property_id = :property_id 
#                   AND booking_date::date = :date 
#                   AND status IN ('Pending', 'Confirmed')
#             """
#             result = db.execute(
#                 text(sql),
#                 {"property_id": property_id, "date": date}
#             ).fetchall()

#             shifts = [row[0] for row in result]

#             if not shifts:
#                 availability[date] = "✅ available full day"
#             elif len(shifts) >= 2:
#                 availability[date] = "❌ not available"
#             elif len(shifts) == 1:
#                 shift = shifts[0]
#                 if shift == "Full Day":
#                     availability[date] = "❌ not available"
#                 elif shift == "Day":
#                     availability[date] = "✅ available night shift"
#                 elif shift == "Night":
#                     availability[date] = "✅ available day shift"
#                 else:
#                     availability[date] = f"❓ unknown shift: {shift}"
#             else:
#                 availability[date] = "❓ unknown status"

#     return AvailabilityResponse(availability=availability)


# Helper function to convert Pydantic models to dict for database storage
def serialize_response(response):
    """Convert Pydantic model to dict for database storage and LangChain compatibility"""
    if hasattr(response, 'dict'):
        return response.dict()
    return response

# Wrapper functions that return serialized responses
def get_property_id_from_name_wrapper(session_id: str, property_name: str) -> dict:
    result = get_property_id_from_name_func(session_id, property_name)
    return serialize_response(result)



def list_properties_wrapper(
    session_id: str,
    property_type: Optional[PropertyType] = None,
    city: str = "Karachi",
    country: str = "Pakistan",
    date: Optional[str] = None,
    day_of_the_week: Optional[DayOfWeek] = None,
    shift_type: Optional[ShiftType] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    max_occupancy: Optional[int] = None,
) -> dict:
    
    print(property_type)
    print(shift_type)
    print(day_of_the_week)
    result = list_properties_func(session_id,property_type, city, country, date, day_of_the_week,shift_type, min_price, max_price, max_occupancy)
    return serialize_response(result)

def get_property_details_wrapper(session_id: str) -> dict:
    result = get_property_details_func(session_id)
    return serialize_response(result)

def get_property_images_wrapper(session_id: str) -> dict:
    result = get_property_images_func(session_id)
    return serialize_response(result)

def get_property_videos_wrapper(session_id: str) -> dict:
    result = get_property_videos_func(session_id)
    return serialize_response(result)

async def check_availability_wrapper(session_id: str, dates: List[str]) -> dict:
    result = await check_availability_of_property_func(session_id, dates)
    return serialize_response(result)

# Create structured tools with wrapper functions
get_property_id_from_name = StructuredTool.from_function(
    func=get_property_id_from_name_wrapper,
    name="get_property_id_from_name",
    description="Get the unique property_id using the property name. Returns the ID and basic property details if found.",
    return_direct=False
)

list_properties = StructuredTool.from_function(
    func=list_properties_wrapper,
    name="list_properties",
    description="""
    Search and filter available properties for booking.

    REQUIRED:
        - property_type
        - date
        - shift_type

    BEHAVIOR:
        - `day_of_the_week` will be automatically 
          calculated from the given `date`.(Possible values are "saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday")
        - Updates session state with search filters for future queries.
        - Only shows properties available on the specified date and shift type.
    
    PARAMETERS:
        session_id       : Unique identifier for the user session.
        property_type    : Category/type of property to filter by.
        city             : City where the property is located (default: "Karachi").
        country          : Country where the property is located (default: "Pakistan").
        date             : Booking date in YYYY-MM-DD format.
        day_of_the_week  : Optional. Specific day of week (auto-filled from `date` if None).
        shift_type       : Type of booking shift (Day, Night, Full Day, Full Night).
        min_price        : Minimum price filter.
        max_price        : Maximum price filter.
        max_occupancy    : Maximum occupancy filter.
    """,
    return_direct=True
)

get_property_details = StructuredTool.from_function(
    func=get_property_details_wrapper,
    name="get_property_details",
    description="""Always use the property ID (UUID), not just the name. If getting details by name, use get_property_id_from_name first.
    Get detailed information about a specific property by its ID.
    Returns text details only - use get_property_images and get_property_videos for media.""",
    return_direct=False
)

get_property_images = StructuredTool.from_function(
    func=get_property_images_wrapper,
    name="get_property_images",
    description="Get all public image URLs for a specific property by its ID.",
    return_direct=False
)

get_property_videos = StructuredTool.from_function(
    func=get_property_videos_wrapper,
    name="get_property_videos",
    description="Get all public video URLs for a specific property by its ID.",
    return_direct=False
)

check_availability_of_property = StructuredTool.from_function(
    func=check_availability_wrapper,
    name="check_availability_of_property",
    description="""When to use: When users want to check availability for specific dates on a particular property.
    Description: Checks if a property is available on given date(s) and shows which shifts are free. Use when user has already selected a specific property.
    Use cases:
    - "Is Green Valley available next weekend?"
    - "Check availability for December 20-25"
    - "What shifts are free on Christmas?"
    - Before proceeding with booking confirmation

    Returns: Date-by-date availability status with shift information""",
    return_direct=False
)

# Export all tools
tools = [
    get_property_id_from_name,
    list_properties,
    get_property_details,
    get_property_images,
    get_property_videos,
    check_availability_of_property
]

# Export both the wrapper functions (for direct use) and the Pydantic functions (for type validation)
__all__ = [
    'tools',
    'get_property_id_from_name_func',
    'list_properties_func', 
    'get_property_details_func',
    'get_property_images_func',
    'get_property_videos_func',
    'check_availability_of_property_func',
    'serialize_response'
]


@tool("check_message_relevance")
def check_message_relevance(user_message: str) -> dict:
    """
    Check if user message is relevant to farmhouse/hut booking.
    
    Args:
        user_message: User's input message
    
    Returns:
        {
            "is_relevant": bool,
            "category": "booking|greeting|irrelevant|creator_question",
            "redirect_message": str (if irrelevant)
        }
    """


from datetime import datetime, date
import calendar

@tool("check_booking_date")
def check_booking_date(day: int, month: int = None, year: int = None) -> dict:
    """
    Validate booking date based on current date and booking constraints.
    Only allows booking for current month and next month.
    
    Args:
        day: Day of the month (1-31)
        month: Month (1-12, optional - defaults to current month)
        year: Year (optional - defaults to current year)
    
    Returns:
        {
            "is_valid": bool,
            "message": str,
            "date_info": dict (if valid)
        }
    """
    
    # Get current date information
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    current_day = current_date.day
    
    # Calculate next month and year
    if current_month == 12:
        next_month = 1
        next_year = current_year + 1
    else:
        next_month = current_month + 1
        next_year = current_year
    
    # Get month names
    current_month_name = calendar.month_name[current_month]
    next_month_name = calendar.month_name[next_month]
    
    # Set default values if not provided
    if month is None:
        month = current_month
    if year is None:
        year = current_year
    
    # Validation checks
    
    # Check for negative day
    if day < 1:
        return {
            "is_valid": False,
            "message": "Day cannot be negative or zero. Please enter a valid day number.",
            "date_info": None
        }
    
    # Check for invalid month
    if month < 1 or month > 12:
        return {
            "is_valid": False,
            "message": "Invalid month. Month should be between 1 and 12.",
            "date_info": None
        }
    
    # Check if year is in the past (only if explicitly provided)
    if year < current_year:
        return {
            "is_valid": False,
            "message": "Cannot book for past years. Please select a date from this year or next year.",
            "date_info": None
        }
    
    # Check if month/year combination is allowed (current month, current year OR next month, next year)
    allowed_dates = [
        (current_month, current_year),
        (next_month, next_year)
    ]
    
    if (month, year) not in allowed_dates:
        return {
            "is_valid": False,
            "message": f"We are doing booking for {current_month_name} and {next_month_name}",
            "date_info": None
        }
    
    # Check if day exists in the given month
    try:
        days_in_month = calendar.monthrange(year, month)[1]
        if day > days_in_month:
            month_name = calendar.month_name[month]
            return {
                "is_valid": False,
                "message": f"Invalid date. {month_name} has only {days_in_month} days, but you entered day {day}.",
                "date_info": None
            }
    except ValueError:
        return {
            "is_valid": False,
            "message": "Invalid date combination.",
            "date_info": None
        }
    
    # Check if the date is in the past (for current month)
    try:
        booking_date = date(year, month, day)
        if booking_date < current_date.date():
            return {
                "is_valid": False,
                "message": "Cannot book for past dates. Please select a future date.",
                "date_info": None
            }
    except ValueError:
        return {
            "is_valid": False,
            "message": "Invalid date.",
            "date_info": None
        }
    
    # If all validations pass
    month_name = calendar.month_name[month]
    return {
        "is_valid": True,
        "message": f"Valid booking date: {day} {month_name} {year}",
        "date_info": {
            "day": day,
            "month": month,
            "year": year,
            "month_name": month_name,
            "formatted_date": f"{day}/{month}/{year}"
        }
    }



@tool("translate_response")
def translate_response(user_query: str, previous_tool_response: str) -> str:
    """
    Automatically detects user's language from their query and converts the previous tool response to match that language.
    
    Use this tool:
    - At the END of every conversation after any other tool has provided a response
    - When you need to convert a response to match the user's language preference
    - Always call this as the final step before giving response to user
    
    Language Detection & Conversion Rules:
    
    **ENGLISH**: If user query contains English words like:
    - "show me farms", "available huts", "book farmhouse", "what is price"
    → Convert response to pure English
    
    **ROMAN** (Urdu written in English alphabets): If user query contains Roman Urdu words like:
    - "mujhe farm dikhao", "farmhouse chahiye", "kya available hai", "kitna paisa"
    - "aaj booking", "kal ke liye", "price kya hai", "dikhayein"
    → Convert response to Roman (mix of Urdu-English)
    
    Examples:
    
    English Query: "show me available farms for tomorrow night"
    → Response: "Available farmhouses for 21-August-2025 (Thursday) Night shift: 1. ABC Farm - Price Rs 15000..."
    
    Roman Query: "mujhe kal night ke liye farmhouse chahiye"  
    → Response: "Available farmhouse aur unke prices 21-August-2025 (Thursday) Night shift ke liye: 1. ABC Farm - Price Rs 15000..."
    
    Roman Query: "farmhouse dikhao"
    → Response: "Farmhouse dekhne ke liye mujhe ye details chahiye: Date, Shift Type, kitne log hain..."
    
    The tool will automatically:
    1. Detect language from user_query
    2. Convert previous_response to match that language
    3. Return the translated response
    
    Args:
        user_query: The original user question/request to detect language from
        previous_response: The response from previous tool that needs language conversion
        
    Returns:
        str: Response converted to match user's language preference
    """
    return previous_tool_response