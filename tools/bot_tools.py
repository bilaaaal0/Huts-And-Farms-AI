from langchain.tools import tool
from app.database import SessionLocal
from app.chatbot.models import (
    Property, PropertyImage, PropertyAmenity, PropertyPricing, PropertyVideo,
    OwnerProperty, Owner, User, Booking
)
from sqlalchemy import text

from app.database import SessionLocal
from app.chatbot.models import Property, PropertyPricing
import asyncio
import aiohttp
import base64
from typing import List, Dict, Optional
import requests
import uuid

# @tool("list_properties")
# def list_properties(property_type: str = None, city: str = "Karachi", country: str = "Pakistan") -> str:
#     """
#     List huts, farmhouses, or both in a specific city and country.
#     - Set property_type to 'hut', 'farm', or leave None for all.
#     - Defaults to city='Karachi' and country='Pakistan'.
#     Returns name, city, max occupancy, and pricing.
#     """
#     with SessionLocal() as db:
#         query = db.query(Property).filter(
#             Property.city.ilike(city),
#             Property.country.ilike(country)
#         )

#         if property_type:
#             query = query.filter(Property.type == property_type.lower())

#         properties = query.order_by(Property.created_at.desc()).limit(15).all()

#         if not properties:
#             return f"No {property_type or ''} properties found in {city}, {country}."

#         result_lines = []
#         for i, prop in enumerate(properties, start=1):
#             pricing = (
#                 db.query(PropertyPricing)
#                 .filter(PropertyPricing.property_id == prop.property_id)
#                 .first()
#             )

#             # Show pricing info
#             price_info = (
#                 f"Day: Rs.{pricing.base_price_day_shift}/- | "
#                 f"Night: Rs.{pricing.base_price_night_shift}/- | "
#                 f"Full Day: Rs.{pricing.base_price_full_day}/-"
#                 if pricing else "Price not available"
#             )

#             line = (
#                 f"{i}. *{prop.name}* in _{prop.city}_ — Max guests: {prop.max_occupancy}\n"
#                 f"   💰 {price_info}\n"
#                 f"   🆔 `{prop.property_id}`"
#             )
#             result_lines.append(line)

#         return "\n\n".join(result_lines)








# @tool('list_properties')
# def list_properties(property_type: str = None, city: str = "Karachi", country: str = "Pakistan") -> str:
#     """
#     List huts, farmhouses, or both in a specific city and country.
#     Set property_type to 'hut', 'farm', or leave None for all.
#     Defaults: city='Karachi', country='Pakistan'.

#     Returns name, city, max occupancy, and pricing.
#     """
#     with SessionLocal() as db:
#         sql = """
#         SELECT p.name, p.city, p.max_occupancy, 
#                 pp.base_price_day_shift, pp.base_price_night_shift, pp.base_price_full_day 
#                 FROM properties p, property_pricing pp 
#                 WHERE p.property_id = pp.property_id
#                 AND p.city = :city AND p.country = :country
#         """
#         params = {"city": city, "country": country}

#         if property_type:
#             sql += " AND p.type = :type"
#             params["type"] = property_type

#         result = db.execute(text(sql), params).fetchall()

#         if not result:
#             return f"No {property_type or 'properties'} found in {city}, {country}."

#         lines = []
#         for i, row in enumerate(result, 1):
#             name, city, max_occupancy, day, night, full = row
#             line = (
#                 f"{i}. *{name}* in _{city}_ — Guests: {max_occupancy} | "
#                 f"Day: Rs {day or 'N/A'}, Night: Rs {night or 'N/A'}, Full: Rs {full or 'N/A'}"
#             )
#             lines.append(line)

#         return "\n".join(lines)



@tool("get_property_id_from_name")
def get_property_id_from_name(property_name: str) -> dict:
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
        
        if not result:
            return {
                "success": False,
                "message": f"❌ No property found with the name '{property_name}'.",
                "property_id": None
            }

        property_id, name, city, country = result
        return {
            "success": True,
            "property_id": property_id,
            "name": name,
            "city": city,
            "country": country,
            "message": f"✅ Found: *{name}* in _{city}, {country}_ (ID: `{property_id}`)"
        }




@tool("list_properties")
def list_properties(
    property_type: str = None,
    city: str = "Karachi",
    country: str = "Pakistan",
    date: Optional[str] = None,
    shift_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    max_occupancy: Optional[int] = None,
) -> dict:
    """
    List properties based on filters:
    - property_type, date, shift_type, occupancy range, price range.
    Returns both structured data and formatted message.
    """
    if not property_type:
        return {"error": "🤔 Do you want to see huts or farmhouses?"}
    
    if not date or not shift_type:
        return {"error": "📅 Please provide both the date and shift type (Day, Night, or Full Day)."}

    with SessionLocal() as db:
        # Determine which price column to filter
        price_column = {
            "Day": "pp.base_price_day_shift",
            "Night": "pp.base_price_night_shift",
            "Full Day": "pp.base_price_full_day"
        }.get(shift_type)

        if not price_column:
            return {"error": "❌ Invalid shift_type. Please use 'Day', 'Night', or 'Full Day'."}

        # SQL to get properties matching filters
        sql = f"""
            SELECT p.property_id, p.name, p.city, p.max_occupancy,
                   pp.base_price_day_shift, pp.base_price_night_shift, pp.base_price_full_day
            FROM properties p
            JOIN property_pricing pp ON p.property_id = pp.property_id
            WHERE p.city = :city AND p.country = :country AND p.type = :type
        """

        # Add price range filter
        if min_price is not None:
            sql += f" AND {price_column} >= :min_price"
        if max_price is not None:
            sql += f" AND {price_column} <= :max_price"

        params = {
            "city": city,
            "country": country,
            "type": property_type
        }
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price

        result = db.execute(text(sql), params).fetchall()
        if not result:
            return {"message": "❌ No properties match the given filters."}

        available_props = []
        formatted_lines = []
        
        for prop in result:
            property_id, name, city, occupancy, day_price, night_price, full_price = prop

            # Occupancy check
            if max_occupancy and not (max_occupancy - 10 <= occupancy <= max_occupancy + 10):
                continue

            # Check if property is already booked on this date and shift
            booking_sql = """
                SELECT 1 FROM bookings
                WHERE property_id = :pid AND booking_date = :date
                AND shift_type = :shift AND status IN ('Pending', 'Confirmed')
            """
            booking = db.execute(text(booking_sql), {
                "pid": property_id,
                "date": date,
                "shift": shift_type
            }).first()

            if booking:
                continue  # Skip already booked

            selected_price = {
                "Day": day_price,
                "Night": night_price,
                "Full Day": full_price
            }.get(shift_type, "N/A")

            # Save full details
            available_props.append({
                "property_id": property_id,
                "name": name,
                "city": city,
                "shift_type": shift_type,
                "price": selected_price
            })

            # Build message line
            formatted_lines.append(
                f"• *{name}* (ID: `{property_id}`) — Rs {selected_price}"
            )

        if not available_props:
            return {
                "message": f"❌ No {property_type}s available on {date} for {shift_type}.",
                "results": []
            }

        # Final message
        message = f"📅 *{date}* | Shift: *{shift_type}*\n" + "\n".join(formatted_lines)

        return {
            "message": message,
            "results": available_props,
            "count": len(available_props)
        }


@tool("get_property_details")
def get_property_details(property_id: str) -> dict:
    """
    Always use the property ID (UUID), not just the name. If getting details by name, use get_property_id_from_name first.
    Get detailed information about a specific property by its ID.
    Returns text details only - use get_property_images and get_property_videos for media.
    """
    print(property_id)
    with SessionLocal() as db:
        sql = """
         SELECT p.name, p.description, p.city, p.country, p.max_occupancy, p.address, p.description,
                pp.base_price_day_shift, pp.base_price_night_shift, pp.base_price_full_day,
                pa.type, pa.value 
         FROM properties p
         LEFT JOIN property_pricing pp ON p.property_id = pp.property_id
         LEFT JOIN property_amenities pa ON p.property_id = pa.property_id
         WHERE p.property_id = :property_id
        """
        params = {"property_id": property_id}
        result = db.execute(text(sql), params).fetchall()
        
        if not result:
            return {"error": f"No details found for property ID `{property_id}`."}
        
        # Process the data
        property_info = {}
        amenities = []
        
        for row in result:
            name, description, city, country, max_occupancy, address, desc, day_price, night_price, full_price, amenity_type, amenity_value = row
            
            # Set basic property info (will be same for all rows)
            if not property_info:
                property_info = {
                    "name": name,
                    "description": desc,
                    "city": city,
                    "country": country,
                    "max_occupancy": max_occupancy,
                    "address": address,
                    "day_price": day_price,
                    "night_price": night_price,
                    "full_price": full_price
                }
            
            # Collect amenities
            if amenity_type and amenity_value:
                amenity_str = f"{amenity_type} - {amenity_value}"
                if amenity_str not in amenities:
                    amenities.append(amenity_str)
        
        # Format text response
        text_response = (f"*{property_info['name']}* in _{property_info['city']}, {property_info['country']}_\n"
                        f"Max Guests: {property_info['max_occupancy']}\n"
                        f"Address: {property_info['address']}\n"
                        f"Description: {property_info['description']}\n"
                        f"Day Price: Rs.{property_info['day_price']}/-, "
                        f"Night Price: Rs.{property_info['night_price']}/-, "
                        f"Full Day Price: Rs.{property_info['full_price']}/-\n"
                        f"Amenities: {', '.join(amenities) if amenities else 'None listed'}")

        # images = get_property_images.invoke({"property_id": property_id})
        return {
            "success": True,
            "property_id": property_id,
            "details": text_response,
            "property_info": property_info,
            # "images": images
        }









@tool("get_property_images")
def get_property_images(property_id: str) -> dict:
    """
    Get all public image URLs for a specific property by its ID.
    """
    with SessionLocal() as db:
        sql = """
            SELECT DISTINCT pi.image_url 
            FROM property_images pi
            WHERE pi.property_id = :property_id
            AND pi.image_url IS NOT NULL
            AND pi.image_url != ''
        """
        result = db.execute(text(sql), {"property_id": property_id}).fetchall()

    image_urls = [row[0].strip() for row in result if row[0] and row[0].strip()]

    return {
        "success": True,
        "property_id": property_id,
        "images": image_urls,
        "images_count": len(image_urls),
        "message": "Fetched image URLs successfully" if image_urls else "No images found"
    }


@tool("get_property_videos")
def get_property_videos(property_id: str) -> dict:
    """
    Get all public video URLs for a specific property by its ID.
    """
    with SessionLocal() as db:
        sql = """
            SELECT DISTINCT pv.video_url 
            FROM property_videos pv
            WHERE pv.property_id = :property_id
            AND pv.video_url IS NOT NULL
            AND pv.video_url != ''
        """
        result = db.execute(text(sql), {"property_id": property_id}).fetchall()

    video_urls = [row[0].strip() for row in result if row[0] and row[0].strip()]

    return {
        "success": True,
        "property_id": property_id,
        "videos": video_urls,
        "videos_count": len(video_urls),
        "message": "Fetched video URLs successfully" if video_urls else "No videos found"
    }






@tool("Check_availability_of_property")
async def check_availability_of_property(property_id: str, dates: List[str]) -> Dict[str, str]:
    """
    Check if a property is available on a list of given dates.
    Returns a dictionary with each date and whether it's available or not.
    """
    availability = {}

    with SessionLocal() as db:
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
                availability[date] = "✅ available full day"
            elif len(shifts) >= 2:
                availability[date] = "❌ not available"
            elif len(shifts) == 1:
                shift = shifts[0]
                if shift == "Full Day":
                    availability[date] = "❌ not available"
                elif shift == "Day":
                    availability[date] = "✅ available night shift"
                elif shift == "Night":
                    availability[date] = "✅ available day shift"
                else:
                    availability[date] = f"❓ unknown shift: {shift}"
            else:
                availability[date] = "❓ unknown status"

    return availability




   