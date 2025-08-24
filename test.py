
import google.generativeai as genai
import re
from typing import Dict, Optional, List
from langchain.tools import tool
import requests
from PIL import Image
import io
import base64
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
import google.generativeai as genai
import requests
from PIL import Image
import io
import os
import json

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))



def extract_text_from_payment_image(image_url: str) -> Dict:
    """
    Extract text from payment screenshot using Google's Gemini Vision API.
    Also determines if the image is actually a payment screenshot.
    
    Args:
        image_url: URL of the payment screenshot image
        
    Returns:
        Dict containing:
        - success: bool
        - is_payment_screenshot: bool
        - extracted_data: Dict with payment info
        - confidence_score: float (0-1)
        - error: str (if any)
    """
    try:
        # Download image from URL
        response = requests.get(image_url, timeout=10)
        if response.status_code != 200:
            return {
                "success": False, 
                "is_payment_screenshot": False,
                "error": "Failed to download image"
            }
        
        # Load image using PIL
        image = Image.open(io.BytesIO(response.content))
        
        # Use Gemini Vision to analyze and extract text
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        extraction_prompt = """
        First, determine if this image is a payment/transaction screenshot from any payment app 
        (EasyPaisa, JazzCash, Bank apps, PayPal, etc.) or receipt. Look for indicators like:
        - Transaction IDs or reference numbers
        - Amount with currency symbols (Rs, PKR, $, etc.)
        - Payment app interfaces/logos
        - Transaction status messages
        - Sender/receiver information
        - Date/time stamps in transaction context
        
        Then, if it IS a payment screenshot, extract the following information:
        
        1. Transaction/Reference ID (any alphanumeric ID)
        2. Amount paid (look for numbers with Rs, PKR, or currency symbols)
        3. Sender name (person who made the payment)
        4. Sender phone number (if visible)
        5. Receiver name or account title
        6. Receiver phone number
        7. Date and time of transaction
        8. Payment method (EasyPaisa, JazzCash, Bank transfer, etc.)
        9. Transaction status (Success, Completed, etc.)
        
        Return the information in this exact JSON format:
        {
            "is_payment_screenshot": true or false,
            "confidence_score": 0.0 to 1.0 (how confident you are this is a payment screenshot),
            "transaction_id": "extracted transaction ID or null",
            "amount": "extracted amount number only or null",
            "sender_name": "sender name or null",
            "sender_phone": "sender phone or null",
            "receiver_name": "receiver name or null", 
            "receiver_phone": "receiver phone or null",
            "transaction_date": "date and time or null",
            "payment_method": "payment method or null",
            "status": "transaction status or null",
            "raw_text": "all visible text in the image"
        }
        
        If this is NOT a payment screenshot, set all payment fields to null and explain what type of image it is in raw_text.
        If you cannot find any information, set the field to null. Be precise and only extract what is clearly visible.
        """
        
        response = model.generate_content([extraction_prompt, image])
        
        # Parse the response to extract JSON
        response_text = response.text.strip()
        
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_text = response_text[json_start:json_end]
            
            extracted_data = json.loads(json_text)
            
            # Ensure required fields exist
            is_payment = extracted_data.get("is_payment_screenshot", False)
            confidence = extracted_data.get("confidence_score", 0.0)
            
        except (json.JSONDecodeError, ValueError) as e:
            # If JSON parsing fails, assume it's not a payment screenshot
            extracted_data = {
                "is_payment_screenshot": False,
                "confidence_score": 0.0,
                "raw_text": response_text,
                "transaction_id": None,
                "amount": None,
                "sender_name": None,
                "sender_phone": None,
                "receiver_name": None,
                "receiver_phone": None,
                "transaction_date": None,
                "payment_method": None,
                "status": None
            }
            is_payment = False
            confidence = 0.0
        
        # ✅ Print extracted info in a nice format
        print(f"\n📌 Image Analysis Results:")
        print(f"   Is Payment Screenshot: {'✅ Yes' if is_payment else '❌ No'}")
        print(f"   Confidence Score: {confidence:.2f}")
        
        if is_payment:
            print("\n💳 Extracted Payment Information:")
            for key, value in extracted_data.items():
                if key not in ["is_payment_screenshot", "confidence_score", "raw_text"]:
                    print(f"   {key}: {value}")
        else:
            print(f"   Image Content: {extracted_data.get('raw_text', 'Could not analyze image')}")
        
        print("-" * 50)

        return {
            "success": True,
            "is_payment_screenshot": is_payment,
            "confidence_score": confidence,
            "extracted_data": extracted_data,
            "raw_response": response_text
        }
            
    except Exception as e:
        print(f"❌ Error extracting text from image: {e}")
        return {
            "success": False,
            "is_payment_screenshot": False,
            "confidence_score": 0.0,
            "error": f"Failed to extract text: {str(e)}"
        }


def is_valid_payment_screenshot(result: Dict) -> bool:
    """
    Helper function to check if the result indicates a valid payment screenshot
    with sufficient confidence and required data.
    
    Args:
        result: Dict returned from extract_text_from_payment_image
        
    Returns:
        bool: True if it's a valid payment screenshot with good confidence
    """
    if not result.get("success", False):
        return False
    
    if not result.get("is_payment_screenshot", False):
        return False
    
    # Check confidence threshold
    confidence = result.get("confidence_score", 0.0)
    if confidence < 0.7:  # Require at least 70% confidence
        return False
    
    # Check if at least some key payment data is present
    extracted_data = result.get("extracted_data", {})
    has_amount = extracted_data.get("amount") is not None
    has_transaction_id = extracted_data.get("transaction_id") is not None
    has_payment_method = extracted_data.get("payment_method") is not None
    
    # At least 2 out of these 3 key fields should be present
    key_fields_count = sum([has_amount, has_transaction_id, has_payment_method])
    
    return key_fields_count >= 2


# Example usage:

# Test the function
result = extract_text_from_payment_image("https://res.cloudinary.com/dxoqq3372/image/upload/v1755111930/veui7is45nctujommxur.jpg")


if result["success"]:
    if result["is_payment_screenshot"]:
        print("✅ Valid payment screenshot detected!")
        print(f"Confidence: {result['confidence_score']:.2f}")
        
        # Use helper function for validation
        if is_valid_payment_screenshot(result):
            print("💰 Payment data extraction successful!")
            # Process the payment data
            payment_data = result["extracted_data"]
        else:
            print("⚠️ Low confidence or insufficient payment data")
    else:
        print("❌ This is not a payment screenshot")
        print(f"Image contains: {result['extracted_data']['raw_text']}")
else:
    print(f"❌ Error: {result['error']}")
