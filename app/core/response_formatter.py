"""
Response formatter with Pydantic schemas for structured LLM output.

This module defines the response schemas and formatter for consistent
frontend rendering of different response types.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum


class ResponseType(str, Enum):
    """Enum for different response types."""
    INFO = "info"
    QUESTIONS = "questions"
    MEDIA = "media"
    PROPERTY_LIST = "property_list"
    BOOKING_CONFIRMATION = "booking_confirmation"
    ERROR = "error"


class QuestionType(str, Enum):
    """Enum for different question input types."""
    DATE = "date"
    CHOICE = "choice"
    NUMBER = "number"
    TEXT = "text"
    PRICE_RANGE = "price_range"


class Question(BaseModel):
    """Schema for individual questions."""
    id: str = Field(description="Unique identifier for the question")
    text: str = Field(description="Question text to display to user")
    type: QuestionType = Field(description="Type of input expected")
    required: bool = Field(default=True, description="Whether this field is required")
    options: Optional[List[str]] = Field(default=None, description="Options for choice type questions")
    placeholder: Optional[str] = Field(default=None, description="Placeholder text for input")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class MediaUrls(BaseModel):
    """Schema for media URLs."""
    images: Optional[List[str]] = Field(default=None, description="List of image URLs")
    videos: Optional[List[str]] = Field(default=None, description="List of video URLs")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class Property(BaseModel):
    """Schema for property in property list."""
    id: str = Field(description="Property identifier")
    name: str = Field(description="Property name")
    price: float = Field(description="Property price")
    location: Optional[str] = Field(default=None, description="Property location")
    capacity: Optional[int] = Field(default=None, description="Maximum capacity")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class InfoResponse(BaseModel):
    """Schema for informational responses."""
    type: ResponseType = Field(default=ResponseType.INFO, description="Response type")
    main_message: str = Field(description="Main message to display")
    info: Dict[str, Any] = Field(default_factory=dict, description="Structured information data")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class QuestionsResponse(BaseModel):
    """Schema for question responses."""
    type: ResponseType = Field(default=ResponseType.QUESTIONS, description="Response type")
    main_message: str = Field(description="Main message to display")
    questions: List[Question] = Field(description="List of questions to ask user")
    show_cancel: bool = Field(default=False, description="Whether to show Cancel/Explore More button on form")
    cancel_text: Optional[str] = Field(default="Not now", description="Text for cancel button")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class MediaResponse(BaseModel):
    """Schema for media responses."""
    type: ResponseType = Field(default=ResponseType.MEDIA, description="Response type")
    main_message: str = Field(description="Main message to display")
    media: MediaUrls = Field(description="Media URLs")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class PropertyListResponse(BaseModel):
    """Schema for property list responses."""
    type: ResponseType = Field(default=ResponseType.PROPERTY_LIST, description="Response type")
    main_message: str = Field(description="Main message to display")
    properties: List[Property] = Field(description="List of available properties")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Applied filters")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class BookingConfirmationResponse(BaseModel):
    """Schema for booking confirmation responses."""
    type: ResponseType = Field(default=ResponseType.BOOKING_CONFIRMATION, description="Response type")
    main_message: str = Field(description="Main message to display")
    booking_id: str = Field(description="Booking reference ID")
    amount: float = Field(description="Total amount to pay")
    payment_instructions: str = Field(description="Payment instructions")
    property_name: str = Field(description="Name of booked property")
    booking_date: str = Field(description="Booking date")
    shift_type: str = Field(description="Booking shift type")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    type: ResponseType = Field(default=ResponseType.ERROR, description="Response type")
    main_message: str = Field(description="Error message to display")
    error_code: Optional[str] = Field(default=None, description="Error code for debugging")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


# Union type for all possible responses
ResponseItem = Union[
    InfoResponse,
    QuestionsResponse,
    MediaResponse,
    PropertyListResponse,
    BookingConfirmationResponse,
    ErrorResponse
]


class StructuredResponse(BaseModel):
    """Schema for the complete structured response array."""
    responses: List[ResponseItem] = Field(description="Array of response items")
    
    class Config:
        extra = "allow"  # Allow extra fields from LLM


class ResponseFormatterAgent:
    """Separate agent for formatting responses into structured format."""
    
    def __init__(self):
        from app.agents.llm_factory import get_llm
        
        # Create separate LLM instance for formatting
        self.llm = get_llm(temperature=0)
        # Use function_calling method to avoid strict schema constraints
        self.structured_llm = self.llm.with_structured_output(
            StructuredResponse,
            method="function_calling"
        )
        
        self.formatting_prompt = """
You are a response formatter. Your job is to take a raw agent response and convert it into a structured format for the frontend.

ANALYZE the raw response and determine what type(s) of content it contains:

1. **INFO** - General information, details, location, facilities, pricing, etc.
   - ONLY extract data that is EXPLICITLY present in the raw response
   - ONLY add keys for data that actually exists
   - If raw response has location → add info.location
   - If raw response has amenities/facilities → add info.facilities as array
   - If raw response has pricing → add info.pricing as object
   - If raw response has capacity → add info.capacity
   - If raw response has description → add info.description
   - If raw response is just a greeting/simple message with NO details → DO NOT use INFO type, just return the message as-is

2. **QUESTIONS** - When asking user for input (detect question marks, numbered lists asking for info)
   - Extract each question with appropriate field type (date/choice/number/text/price_range)
   - Include all options for choice questions
   - Mark questions as required=true by default
   - **BOOKING DETAILS DETECTION**: If asking for name, CNIC, or contact details for booking:
     * Check for keywords: "user_name", "cnic", "contact", "full name", "CNIC number", "questions_needed", "required_fields", "confirm your details", "booking details"
     * If NEW USER (no existing details) → Set show_cancel=false (must provide details)
     * If EXISTING USER (confirming/editing) → Set show_cancel=true with cancel_text="Cancel"
   - Detect patterns: "To proceed with booking", "confirm your details", "edit your details"
   - If questions include "action" with options "Confirm and Book" or "Edit Details" → This is confirmation, show_cancel=false

3. **MEDIA** - When mentioning images, videos, or media URLs
   - Extract ALL image and video URLs into separate arrays

4. **PROPERTY_LIST** - When showing available properties with names and prices
   - Extract property id, name, price, location, capacity

5. **BOOKING_CONFIRMATION** - When confirming a booking with booking ID and payment details

6. **ERROR** - Error messages or problems

CRITICAL RULES:
- NEVER add empty fields or keys that don't exist in the raw response
- If the raw response is just a simple message (greeting, acknowledgment, etc.) → Return it as plain INFO with empty info object OR just the main_message
- ONLY create structured info objects when there is ACTUAL data to extract
- For simple messages like "I can help you find a farmhouse" → Just use main_message, leave info empty
- **IMPORTANT**: Multiple response types can be returned in one array - if there's a property list AND a follow-up message, create BOTH responses
- Keep main_message concise, put details in structured fields ONLY if they exist
- For final booking questions (name, CNIC, contact) → Set required=false to allow users to back out
- **NEVER skip any part of the raw response** - if there's text after a property list, include it as a separate INFO response

PREDEFINED CHOICE OPTIONS:
- property_type: ["Farm", "Hut"]
- shift_type: ["Day", "Night", "Full Day", "Full Night"]
- payment_method: ["Bank Transfer", "Cash", "JazzCash", "EasyPaisa"]

these are tenatative EXAMPLES for you to understand:

Input: "I can help you find a farmhouse or hut whenever you're ready. Just let me know!"
Output: 
{{
  "responses": [
    {{
      "type": "info",
      "main_message": "I can help you find a farmhouse or hut whenever you're ready. Just let me know!",
      "info": {{}}
    }}
  ]
}}

Input: "**Location:** Super Highway, Karachi **Amenities:** Pool, BBQ, AC **Capacity:** 20 people"
Output: 
{{
  "responses": [
    {{
      "type": "info",
      "main_message": "Here are the details:",
      "info": {{
        "location": "Super Highway, Karachi",
        "facilities": ["Pool", "BBQ", "AC"],
        "capacity": "20 people"
      }}
    }}
  ]
}}

Input: "What type of property? Farm or Hut?"
Output:
{{
  "responses": [
    {{
      "type": "questions",
      "main_message": "What type of property are you looking for?",
      "questions": [
        {{"id": "property_type", "text": "Property Type", "type": "choice", "options": ["Farm", "Hut"], "required": true}}
      ]
    }}
  ]
}}

Input: "I need these details: 1. Date? 2. Shift type? 3. Number of guests?"
Output:
{{
  "responses": [
    {{
      "type": "questions",
      "main_message": "I need these details:",
      "questions": [
        {{"id": "booking_date", "text": "Date?", "type": "date", "required": true}},
        {{"id": "shift_type", "text": "Shift type?", "type": "choice", "options": ["Day", "Night", "Full Day", "Full Night"], "required": true}},
        {{"id": "guest_count", "text": "Number of guests?", "type": "number", "required": true}}
      ]
    }}
  ]
}}

Input: "To proceed with the booking, I need some details from you. Required fields: cnic, user_name"
Output:
{{
  "responses": [
    {{
      "type": "questions",
      "main_message": "To proceed with the booking, I need some details from you.",
      "show_cancel": false,
      "questions": [
        {{"id": "user_name", "text": "Your full name", "type": "text", "required": true}},
        {{"id": "cnic", "text": "CNIC number", "type": "text", "required": true, "placeholder": "13 digits without dashes"}}
      ]
    }}
  ]
}}

Input: "To proceed with booking, I need to confirm your details. 1. Your full name 2. Your CNIC number"
Output:
{{
  "responses": [
    {{
      "type": "questions",
      "main_message": "To proceed with booking, I need to confirm your details.",
      "show_cancel": false,
      "questions": [
        {{"id": "user_name", "text": "Your full name", "type": "text", "required": true}},
        {{"id": "cnic", "text": "Your CNIC number", "type": "text", "required": true, "placeholder": "13 digits"}}
      ]
    }}
  ]
}}

Input: "Please confirm your booking details: Name: Ahmed Ali, CNIC: 12345-6789012-3. What would you like to do? Options: Confirm and Book, Edit Details"
Output:
{{
  "responses": [
    {{
      "type": "questions",
      "main_message": "Please confirm your booking details:\\n\\n👤 Name: Ahmed Ali\\n🆔 CNIC: 12345-6789012-3",
      "show_cancel": false,
      "questions": [
        {{"id": "action", "text": "What would you like to do?", "type": "choice", "required": true, "options": ["Confirm and Book", "Edit Details"]}}
      ]
    }}
  ]
}}

Input: "Edit your details below: 1. Your full name (current: Ahmed Ali) 2. Your CNIC number (current: 1234567890123)"
Output:
{{
  "responses": [
    {{
      "type": "questions",
      "main_message": "Edit your details below:",
      "show_cancel": true,
      "cancel_text": "Cancel",
      "questions": [
        {{"id": "user_name", "text": "Your full name", "type": "text", "required": true, "placeholder": "Ahmed Ali", "default_value": "Ahmed Ali"}},
        {{"id": "cnic", "text": "Your CNIC number", "type": "text", "required": true, "placeholder": "1234567890123", "default_value": "1234567890123"}}
      ]
    }}
  ]
}}

Input: "❌ CNIC must be exactly 13 digits. Please correct below: 1. Your full name 2. Your CNIC number"
Output:
{{
  "responses": [
    {{
      "type": "questions",
      "main_message": "❌ CNIC must be exactly 13 digits. Please correct below:",
      "show_cancel": true,
      "cancel_text": "Cancel",
      "questions": [
        {{"id": "user_name", "text": "Your full name", "type": "text", "required": true, "placeholder": "e.g., Ahmed Ali", "default_value": "Billu"}},
        {{"id": "cnic", "text": "Your CNIC number", "type": "text", "required": true, "placeholder": "13 digits without dashes", "default_value": "421011234567"}}
      ]
    }}
  ]
}}

Input: "Available farmhouses for 17-Feb-2026 Night shift: 1. Seaside Farmhouse - Rs. 22000 2. Green Valley - Rs. 18000. If you want to see details or pictures, let me know!"
Output:
{{
  "responses": [
    {{
      "type": "property_list",
      "main_message": "Available farmhouses for 17-Feb-2026 Night shift:",
      "properties": [
        {{"id": "1", "name": "Seaside Farmhouse", "price": 22000}},
        {{"id": "2", "name": "Green Valley", "price": 18000}}
      ]
    }},
    {{
      "type": "info",
      "main_message": "If you want to see details or pictures, let me know!",
      "info": {{}}
    }}
  ]
}}

Raw agent response to format:
{raw_response}

IMPORTANT: ONLY extract information that is EXPLICITLY present in the raw response. DO NOT add empty fields! If there are multiple parts (like property list + follow-up message), create multiple response objects.
"""
    
    def format_response(self, raw_response: str) -> Dict[str, Any]:
        """
        Format raw agent response into structured format.
        
        Args:
            raw_response: Raw text response from booking agent
            
        Returns:
            Structured response dictionary for frontend
        """
        try:
            print("\n" + "="*80)
            print("📥 FORMATTER AGENT - INPUT")
            print("="*80)
            print(f"Raw Response Length: {len(raw_response)} characters")
            print(f"Raw Response Preview: {raw_response[:500]}...")
            print("="*80 + "\n")
            
            # Use structured LLM to format the response
            formatted_prompt = self.formatting_prompt.format(raw_response=raw_response)
            
            # Print complete prompt details
            print("\n" + "="*80)
            print("📝 FORMATTER AGENT - COMPLETE PROMPT")
            print("="*80)
            print(f"Total Prompt Length: {len(formatted_prompt)} characters")
            print(f"Estimated Tokens: ~{len(formatted_prompt) // 4} tokens (rough estimate)")
            print("-" * 80)
            print("FULL PROMPT:")
            print("-" * 80)
            print(formatted_prompt)
            print("="*80 + "\n")
            
            structured_response = self.structured_llm.invoke(formatted_prompt)
            
            print("\n" + "="*80)
            print("📤 FORMATTER AGENT - OUTPUT (Structured)")
            print("="*80)
            print(f"Response Type: {type(structured_response)}")
            print(f"Number of Responses: {len(structured_response.responses) if hasattr(structured_response, 'responses') else 'N/A'}")
            if hasattr(structured_response, 'responses'):
                for idx, resp in enumerate(structured_response.responses):
                    print(f"\n  Response {idx + 1}:")
                    print(f"    Type: {resp.type}")
                    print(f"    Main Message: {resp.main_message[:100]}..." if len(resp.main_message) > 100 else f"    Main Message: {resp.main_message}")
                    
                    # Print type-specific details
                    if resp.type == 'info' and hasattr(resp, 'info'):
                        print(f"    Info Keys: {list(resp.info.keys())}")
                        for key, value in resp.info.items():
                            if isinstance(value, list):
                                print(f"      {key}: {len(value)} items - {value[:3]}...")
                            elif isinstance(value, dict):
                                print(f"      {key}: {list(value.keys())}")
                            else:
                                print(f"      {key}: {str(value)[:100]}")
                    
                    elif resp.type == 'questions' and hasattr(resp, 'questions'):
                        print(f"    Questions Count: {len(resp.questions)}")
                        for q_idx, q in enumerate(resp.questions):
                            print(f"      Q{q_idx + 1}: id={q.id}, type={q.type}, required={q.required}")
                    
                    elif resp.type == 'media' and hasattr(resp, 'media'):
                        print(f"    Images: {len(resp.media.images) if resp.media.images else 0}")
                        print(f"    Videos: {len(resp.media.videos) if resp.media.videos else 0}")
                        if resp.media.images:
                            print(f"      First Image: {resp.media.images[0][:80]}...")
                    
                    elif resp.type == 'property_list' and hasattr(resp, 'properties'):
                        print(f"    Properties Count: {len(resp.properties)}")
                        for p_idx, p in enumerate(resp.properties[:3]):
                            print(f"      P{p_idx + 1}: {p.name} - Rs. {p.price}")
            print("="*80 + "\n")
            
            # Convert to frontend format
            frontend_response = self._convert_to_frontend_format(structured_response)
            
            print("\n" + "="*80)
            print("🎨 FORMATTER AGENT - FRONTEND FORMAT")
            print("="*80)
            print(f"Status: {frontend_response.get('status')}")
            print(f"Response Count: {frontend_response.get('response_count')}")
            print(f"Response Types: {[r.get('type') for r in frontend_response.get('responses', [])]}")
            
            # Print detailed content for each response
            for idx, resp in enumerate(frontend_response.get('responses', [])):
                print(f"\n  Frontend Response {idx + 1}:")
                print(f"    Type: {resp.get('type')}")
                print(f"    Main Message: {resp.get('main_message', '')[:100]}...")
                
                if resp.get('type') == 'info' and resp.get('info'):
                    print(f"    Info Data:")
                    for key, value in resp.get('info', {}).items():
                        if isinstance(value, list):
                            print(f"      {key}: {len(value)} items")
                        elif isinstance(value, dict):
                            print(f"      {key}: {len(value)} keys")
                        else:
                            print(f"      {key}: {str(value)[:80]}")
                
                elif resp.get('type') == 'questions' and resp.get('questions'):
                    print(f"    Questions: {len(resp.get('questions', []))} questions")
                    for q in resp.get('questions', []):
                        print(f"      - {q.get('id')}: {q.get('type')} ({'required' if q.get('required') else 'optional'})")
                
                elif resp.get('type') == 'media' and resp.get('media'):
                    media = resp.get('media', {})
                    print(f"    Media: {len(media.get('images', []))} images, {len(media.get('videos', []))} videos")
            
            print("="*80 + "\n")
            
            return frontend_response
            
        except Exception as e:
            print("\n" + "="*80)
            print("❌ FORMATTER AGENT - ERROR")
            print("="*80)
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            print("="*80 + "\n")
            
            # Fallback to simple info response
            return self._create_fallback_response(raw_response)
    
    def _convert_to_frontend_format(self, structured_response: StructuredResponse) -> Dict[str, Any]:
        """Convert Pydantic response to frontend dictionary."""
        formatted_responses = []
        
        for response in structured_response.responses:
            formatted_response = {
                "type": response.type,
                "main_message": response.main_message
            }
            
            # Add type-specific data
            if response.type == ResponseType.INFO:
                # Filter out empty values from info object
                cleaned_info = {}
                for key, value in response.info.items():
                    # Only include non-empty values
                    if value is not None:
                        if isinstance(value, str) and value.strip():
                            cleaned_info[key] = value
                        elif isinstance(value, list) and len(value) > 0:
                            cleaned_info[key] = value
                        elif isinstance(value, dict) and len(value) > 0:
                            cleaned_info[key] = value
                        elif not isinstance(value, (str, list, dict)):
                            cleaned_info[key] = value
                
                formatted_response["info"] = cleaned_info
                
            elif response.type == ResponseType.QUESTIONS:
                formatted_response["questions"] = [
                    {
                        "id": q.id,
                        "text": q.text,
                        "type": q.type,
                        "required": q.required,
                        "options": q.options,
                        "placeholder": q.placeholder
                    }
                    for q in response.questions
                ]
                formatted_response["show_cancel"] = response.show_cancel
                if response.show_cancel:
                    formatted_response["cancel_text"] = response.cancel_text
                
            elif response.type == ResponseType.MEDIA:
                formatted_response["media"] = {
                    "images": response.media.images or [],
                    "videos": response.media.videos or []
                }
                
            elif response.type == ResponseType.PROPERTY_LIST:
                formatted_response["properties"] = [
                    {
                        "id": p.id,
                        "name": p.name,
                        "price": p.price,
                        "location": p.location,
                        "capacity": p.capacity
                    }
                    for p in response.properties
                ]
                formatted_response["filters"] = response.filters
                
            elif response.type == ResponseType.BOOKING_CONFIRMATION:
                formatted_response.update({
                    "booking_id": response.booking_id,
                    "amount": response.amount,
                    "payment_instructions": response.payment_instructions,
                    "property_name": response.property_name,
                    "booking_date": response.booking_date,
                    "shift_type": response.shift_type
                })
                
            elif response.type == ResponseType.ERROR:
                formatted_response["error_code"] = response.error_code
            
            formatted_responses.append(formatted_response)
        
        return {
            "status": "success",
            "responses": formatted_responses,
            "response_count": len(formatted_responses)
        }
    
    def _create_fallback_response(self, text_response: str) -> Dict[str, Any]:
        """Create fallback response when formatting fails."""
        return {
            "status": "success",
            "responses": [
                {
                    "type": "info",
                    "main_message": text_response,
                    "info": {}
                }
            ],
            "response_count": 1
        }


# Legacy ResponseFormatter class for backward compatibility
class ResponseFormatter:
    """Legacy formatter - now uses ResponseFormatterAgent internally."""
    
    def __init__(self):
        self.formatter_agent = ResponseFormatterAgent()
    
    def format_for_frontend(self, raw_response: str) -> Dict[str, Any]:
        """Format response using the formatter agent."""
        return self.formatter_agent.format_response(raw_response)
    
    @staticmethod
    def create_fallback_response(text_response: str) -> Dict[str, Any]:
        """Create a fallback response when structured output fails."""
        return {
            "status": "success",
            "responses": [
                {
                    "type": "info",
                    "main_message": text_response,
                    "info": {}
                }
            ],
            "response_count": 1
        }


# Helper functions for creating common response types
def create_info_response(
    main_message: str,
    info_data: Dict[str, Any]
) -> InfoResponse:
    """Create an info response."""
    return InfoResponse(
        main_message=main_message,
        info=info_data
    )


def create_questions_response(
    main_message: str,
    questions: List[Dict[str, Any]]
) -> QuestionsResponse:
    """Create a questions response."""
    question_objects = [
        Question(
            id=q["id"],
            text=q["text"],
            type=QuestionType(q["type"]),
            required=q.get("required", True),
            options=q.get("options"),
            placeholder=q.get("placeholder")
        )
        for q in questions
    ]
    
    return QuestionsResponse(
        main_message=main_message,
        questions=question_objects
    )


def create_media_response(
    main_message: str,
    images: Optional[List[str]] = None,
    videos: Optional[List[str]] = None
) -> MediaResponse:
    """Create a media response."""
    return MediaResponse(
        main_message=main_message,
        media=MediaUrls(images=images, videos=videos)
    )


def create_error_response(
    main_message: str,
    error_code: Optional[str] = None
) -> ErrorResponse:
    """Create an error response."""
    return ErrorResponse(
        main_message=main_message,
        error_code=error_code
    )