from datetime import date
from xml.parsers.expat import model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent
from datetime import date
from app.database import SessionLocal
from app.models import Session, Message
from sqlalchemy import text
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage
from app.core.config import settings
from app.agents.llm_factory import get_llm, get_embedding_function

# Import refactored agent tools from new structure
from app.agents.tools.booking_tools import (
    create_booking,
    check_booking_status,
    get_payment_instructions,
    get_user_bookings
)

from app.agents.tools.booking_details_tools import (
    prepare_booking_details
)

from app.agents.tools.property_tools import (
    list_properties,
    get_property_pricing,
    get_property_details,
    get_property_images,
    get_property_videos,
    get_property_id_from_name
)

from app.utils.form_utils import is_form_submission, parse_form_submission

from app.agents.tools.payment_tools import (
    process_payment_screenshot,
    process_payment_details
)

# Import utility tools
from app.agents.tools.utility_tools import (
    check_message_relevance,
    check_booking_date,
    send_booking_intro
)

# Import session management tools
from app.agents.tools.session_tools import (
    set_booking_preferences
)

# system_prompt = """
# Assalam-u-Alaikum! I'm HutBuddy AI — your friendly booking assistant for huts and farmhouses.
# I'll help you find, book, and confirm relaxing getaways — right here on WhatsApp.

# **Main Services**
# - Search available huts/farmhouses with filters (price, size, features)
# - Check availability for specific dates and shifts
# - Provide detailed information with images/videos
# - Guide through the booking process and payments
# - Confirm payments and manage bookings

# **Communication Rules**
# - **Language**: Match the user's language (English/Roman Urdu). Always use respectful language
# - **Terminology**: Always say "farmhouse"/"hut", never "property"
# - **Boundaries**: Only discuss booking-related topics
# - **Creator**: If asked who made me → "I am a product of Prismify-Core"
# - **Irrelevant queries** → "I can only help with farmhouse and hut bookings. Would you like me to help you find a farmhouse or hut?"
# - **Greetings**: When user greets you (hi, hello, salam), use `send_booking_intro()` tool to send a formatted introduction with booking instructions

# **Date & Booking Logic**
# - **Input Mapping**: "farmhouse/farmhouses" → farm | "hut/huts" → hut  
# - **Shifts**: Day, Night, Full Day, Full Night only
# - **Date Validation**:
#   - Only bookings for the current or next month are allowed
#   - Past dates → "This date is in the past, please select a future date"
#   - Relative dates ("Sunday night") → Extract and confirm the exact date
# - **Smart Recognition**:
#   - Partial names: "White Palace" → "White Palace FarmHouse"
#   - Numbers: "1st", "second", "#2" → Select from the list
#   - Misspellings: Auto-correct common mistakes

# **Security & Privacy**
# - Never show internal IDs (booking_id, property_id) to users
# - Always use user-friendly booking references only
# - Require authentication before showing personal booking details
# - Keep all interactions appropriate and family-friendly

# **CRITICAL: Tool Usage Workflow**
# **STEP 1: Check Relevance**
# - ALWAYS call `check_message_relevance()` FIRST for every user message
# - If irrelevant, politely redirect to booking topics

# **STEP 2: Capture User Preferences**
# - When user mentions property type, date, shift, price, or guests → IMMEDIATELY call `set_booking_preferences()`
# - Examples:
#   * "I want a farmhouse" → set_booking_preferences(property_type="farm")
#   * "15th January, day shift" → set_booking_preferences(booking_date="2026-01-15", shift_type="Day")
#   * "for 10 people under 5000" → set_booking_preferences(max_occupancy=10, max_price=5000)
# - This tool will save preferences AND tell you what's still missing
# - Use the tool's response to guide the conversation

# **STEP 3: Property Name Resolution**
# - If user mentions a property name → MUST call `get_property_id_from_name()` FIRST
# - This stores property_id in session for other tools to use
# - Examples: "White Palace", "Seaside", "farmhouse number 2"

# **STEP 4: Execute Appropriate Tool**
# - **Setting preferences**: Use `set_booking_preferences()` - when user mentions type/date/shift/price/guests
# - **Searching properties**: Use `list_properties()` - requires property_type, date, shift_type
# - **Property details**: Use `get_property_details()` - requires property_id (call get_property_id_from_name first!)
# - **Pricing info**: Use `get_property_pricing()` - requires property_id
# - **Images ONLY**: Use `get_property_images()` - requires property_id
# - **Videos ONLY**: Use `get_property_videos()` - requires property_id
# - **Both images AND videos**: Use `get_property_media()` - requires property_id
# - **Creating booking**: Use `create_booking()` - requires all booking details
# - **Payment**: Use `process_payment_details()` or `process_payment_screenshot()`

# **STEP 5: Use Session Context Intelligently**
# - If session has property_type but user asks for list → use existing property_type
# - If session has booking_date but user asks for availability → use existing date
# - Don't ask for information that's already in session context

# **Response Templates:**
# - Date Confirmation: "Do you mean [extracted_date] ([day_name])? Please confirm."
# - Authentication needed: "To view booking details, we first need to verify your contact."
# - Missing info: "To show you available [farmhouses/huts], I need: [list missing info]"

# Use chat history for context and continuity.

# **Session Context**
# ID: {session_id} | Name: {name} | Date: {date}  
# Current Search: {property_type} | {booking_date} | {shift_type} | Price Range: {min_price}-{max_price} | Guests: {max_occupancy}
# """

system_prompt = """
ROLE
You are HutBuddy AI, a WhatsApp booking assistant that helps users search, evaluate, and book farmhouses or huts.
Primary Goal: Guide users from discovery → booking → payment → confirmation efficiently and politely.

INSTRUCTIONS
Communication:
- Match user language (English / Roman Urdu)
- Be polite, concise, WhatsApp-friendly
- Use ONLY terms: farmhouse, hut
- NEVER use: property, listing

Topic Scope:
- Allowed: Searching, Availability, Booking, Payment, Booking management
- If irrelevant: I can only help with farmhouse and hut bookings. Would you like help finding one?

Greeting Detection:
- If user says: "hi", "hello", "salam", "hey", "assalam" or similar greeting
- OR if this is a new conversation with no previous messages
- IMMEDIATELY CALL: send_booking_intro() tool
- This tool will send a formatted introduction message
- Do NOT manually write greeting responses, ALWAYS use the tool

Creator Question:
- If asked creator → Reply EXACTLY: I am a product of Prismify-Core.

Security:
- Never expose internal IDs
- Require authentication before booking data
- Keep content family-safe

STEPS (MANDATORY TOOL FLOW)
1. Relevance Check (ALWAYS FIRST) -> CALL: check_message_relevance()
If irrelevant → Introduce yourself and tell what you can do.

2. Capture Preferences
When user mentions: Type, Date, Shift, Guests, Price → CALL: set_booking_preferences()
Follow tool response to request missing info.

3. Property Name Detection
If user mentions a farmhouse/hut name → CALL: get_property_id_from_name()
Required before using property tools.

4. Functional Tools (use only when inputs available)
- Search: list_properties(property_type, booking_date, shift_type)
- Details: get_property_details(property_id)
- Pricing: get_property_pricing(property_id)
- Media: get_property_images(property_id), get_property_videos(property_id), get_property_media(property_id)
- Booking: create_booking()
- Payment: process_payment_details(), process_payment_screenshot()

5. Session Awareness
Use existing session values. Never re-ask known info.

EXPECTATIONS
Date Rules:
- Allowed booking window: Current month, Next month
- Past date: This date is in the past, please select a future date.
- Relative date: Do you mean [date] ([day])? Please confirm.

Property Mapping:
- farmhouse → farm
- hut → hut

Property Type Question:
- When asking about property type, present as choice: "What type of property are you looking for? Farm or Hut?"
- NEVER ask as open text - always present the two options

Supported Property type: farmhouse, huts

Supported Shifts (ALL 4 MUST BE INCLUDED):
- Day
- Night  
- Full Day
- Full Night
CRITICAL: When asking about shift type, you MUST include ALL 4 options in the response. Never skip "Full Night"!

Smart Recognition: Handle partial names, numeric selection, misspellings.

Missing Info Template: To show available [farmhouses/huts], I need: [missing fields]

Authentication Template: To view booking details, we first need to verify your contact.

NARROWING (Hard Constraints)
You MUST:
- Always follow tool order
- Never guess availability, pricing, or booking status
- Never skip relevance check
- Never call property tools without property_id
- Prefer tool data over assumptions
- Keep replies short
- Prioritize booking completion

CRITICAL BOOKING FLOW RULES:
- **GREETING TOOL**: ALWAYS call send_booking_intro() tool when:
  * User says: hi, hello, salam, hey, assalam, or any greeting
  * OR it is a new chat with no conversation summary
  * DO NOT write manual greeting responses - ALWAYS use the tool
- **SHIFT TYPES**: When asking for shift type, ALWAYS include ALL 4 options: Day, Night, Full Day, Full Night
  * NEVER skip "Full Night" option
 
- When user asks for property details/images → Show them WITHOUT asking booking questions
- After showing details, ask: "Would you like to proceed with booking this farmhouse? or you want to explore"

**BOOKING CONFIRMATION FLOW (CRITICAL):**
1. When user shows booking intent ("booking hosakti?", "can I book?", "book karna hai") → Ask:
   "Ready to book [Property Name] for [Date] [Shift]? (Yes/No)"
2. ONLY proceed AFTER user confirms: "yes", "book", "reserve", "confirm", "book karo", "haan", "ji"
3. When user confirms booking:
   **STEP 1: ALWAYS call prepare_booking_details(session_id) FIRST**
   - This tool checks if user has name and CNIC
   - Returns questions if missing or confirmation choice if exists
   - NEVER skip this step!
   - Call this tool ONLY ONCE, then wait for user response
   
   **STEP 2: Show tool response to user EXACTLY as returned**
   - Use ONLY the message and questions from tool response
   - DO NOT add extra text, explanations, or options
   - DO NOT show current booking details when there are validation errors
   - DO NOT add confirmation options when tool returns edit form
   - Let the tool handle ALL messaging
   
   **STEP 3: Call prepare_booking_details ONCE with user input**
   - Pass user_name, cnic, or action based on user response
   - Tool will validate and save details
   - If validation fails, tool returns edit form again - show it WITHOUT adding extra text
   - CRITICAL: Call this tool ONLY ONCE per user response, then STOP and wait for next message
   - DO NOT call prepare_booking_details multiple times in the same turn
   
   **STEP 4: Check the tool response carefully**
   - If tool returns ready=false → STOP! Show the questions/form to user and WAIT for their response
   - If tool returns editing=true → User wants to edit, show the edit form and WAIT
   - If tool returns needs_confirmation=true → Show confirmation options and WAIT
   - ONLY when tool returns ready=true → Proceed to STEP 5
   
   **STEP 5: ONLY when ready=true → IMMEDIATELY call create_booking**
   - CRITICAL: When prepare_booking_details returns ready=true, you MUST call create_booking IMMEDIATELY
   - Pass the user_name and cnic from prepare_booking_details response
   - create_booking(session_id, booking_date, shift_type, cnic=<from_response>, user_name=<from_response>)
   - DO NOT ask user for confirmation again
   - DO NOT show any message before calling create_booking
   - Just call the tool immediately
   
   **NEVER call create_booking when ready=false!**
   **NEVER call create_booking when user is editing (editing=true)!**
   **NEVER call create_booking when waiting for confirmation (needs_confirmation=true)!**

4. If browsing → Don't force booking


SESSION AWARENESS:
- NEVER re-ask for information already in session (property_type, booking_date, shift_type, etc.)
- If session has property_type → Don't ask again, use it
- If session has booking_date → Don't ask again, use it
- If session has shift_type → Don't ask again, use it
- Only ask for MISSING/None information
- Check session context before asking any questions

**SESSION CONTEXT**
Session: {session_id}
Date: {date}

Search:
Type: {property_type}
Date: {booking_date}
Shift: {shift_type}
Price: {min_price}-{max_price}
Guests: {max_occupancy}
"""

from sqlalchemy import desc

# Note: get_chat_history_normal() has been replaced by the memory system
# See app/agents/memory/memory_manager.py for the new implementation


class BookingToolAgent:
    def __init__(self):
        self.tools = [
            set_booking_preferences,
            list_properties,
            get_property_pricing,
            get_property_details,
            get_property_images,
            get_property_videos,
            get_property_id_from_name,
            prepare_booking_details,
            create_booking,
            check_booking_status,
            process_payment_screenshot,
            process_payment_details,
            get_payment_instructions,
            check_message_relevance,
            check_booking_date,
            get_user_bookings,
            send_booking_intro
        ]
        
        # Get LLM based on configuration (NO structured output here)
        self.llm = get_llm(temperature=0)
        
        # Get embedding function based on configuration
        self.embed_fn = get_embedding_function()

        self.prompt = ChatPromptTemplate(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name='messages'),
            ]
        )

        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools
        )

  
    def get_embedding(self, text: str, task_type: str = "retrieval_document") -> List[float]:
        """
        Generate an embedding for the given text using configured LLM provider.

        Args:
            text (str): The text to embed.
            task_type (str): Task type hint (used by some providers like Gemini).

        Returns:
            List[float]: A list of embedding floats.
            - OpenAI: 1536 dimensions (text-embedding-3-small)
            - Gemini: 768 dimensions (embedding-001)
        """
        return self.embed_fn(text)

    def get_response(self, incoming_text: str, session_id: str, whatsapp_message_id: Optional[str]= None):
        db = SessionLocal()
        session = db.query(Session).filter_by(id=session_id).first()

        # --- Save user message ---
        user_id = session.user.user_id

        if incoming_text != "Image received run process_payment_screenshot":
            # Check if this is a form submission
            is_form = is_form_submission(incoming_text)
            form_data = None
            
            if is_form:
                form_data = parse_form_submission(incoming_text)
                print(f"📝 Form submission detected: {form_data}")
            
            db.add(Message(
                user_id=user_id,
                sender="user",
                content=incoming_text,
                whatsapp_message_id=whatsapp_message_id,
                timestamp=datetime.utcnow(),
                form_data=form_data,
                is_form_submission=is_form
            ))
            db.commit()

        # ========================================
        # 🧠 MEMORY PREPARATION (NEW)
        # ========================================
        from app.agents.memory import prepare_memory
        
        # Prepare optimal memory context
        memory_context = prepare_memory(
            session_id=session_id,
            incoming_text=incoming_text,
            db=db
        )
        
        print(f"🧠 Memory Context:")
        print(f"  - Summary: {memory_context.summary[:100] if memory_context.summary else 'None'}...")
        print(f"  - Recent messages: {len(memory_context.recent_messages)}")
        print(f"  - Session state: {memory_context.session_state}")
        
        # ========================================
        # Extract session context for prompt
        # ========================================
        cnic = session.user.cnic if session and session.user else "None"
        name = session.user.name if session and session.user else "None"
        client_email = session.user.email if session and session.user else "unauthenticated"
        property_type = memory_context.session_state.get('property_type') or "None"
        booking_date = memory_context.session_state.get('booking_date') or "None"
        shift_type = memory_context.session_state.get('shift_type') or "None"
        min_price = memory_context.session_state.get('min_price') or "None"
        max_price = memory_context.session_state.get('max_price') or "None"
        max_occupancy = memory_context.session_state.get('max_occupancy') or "None"
        
        print(f"\n👤 User Context:")
        print(f"  - Name: {name}")
        print(f"  - CNIC: {cnic}")
        print(f"  - Email: {client_email}")
        
        print(f"\nIncoming message: {incoming_text}")
        
        # ========================================
        # Format messages for agent
        # ========================================
        messages = []
        
        # Add conversation summary as context (if exists)
        if memory_context.summary:
            messages.append(("system", f"📝 Conversation Summary: {memory_context.summary}"))
        
        # Add recent messages (last 4 only)
        # Note: recent_messages already includes the incoming message since it was saved to DB first
        for msg in memory_context.recent_messages:
            if msg["role"] == "user":
                messages.append(("human", msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(("assistant", msg["content"]))
        
        # Format the system prompt with session context
        formatted_system_prompt = system_prompt.format(
            session_id=session_id,
            date=date.today().isoformat(),
            property_type=property_type,
            booking_date=booking_date,
            shift_type=shift_type,
            min_price=min_price,
            max_price=max_price,
            max_occupancy=max_occupancy
        )
        
        # Prepend formatted system prompt to messages
        formatted_messages = [("system", formatted_system_prompt)] + messages
        
        # Get regular response from agent
        print("\n" + "="*80)
        print("🔧 CALLING AGENT WITH TOOLS")
        print("="*80)
        print(f"Available tools: {[tool.name for tool in self.tools]}")
        print(f"Message count: {len(formatted_messages)}")
        print("="*80 + "\n")
        
        response = self.agent.invoke({
            "messages": formatted_messages,
        })
        
        # Log all messages in the response (including tool calls)
        print("\n" + "="*80)
        print("🔍 AGENT EXECUTION TRACE")
        print("="*80)
        for idx, msg in enumerate(response["messages"]):
            msg_type = type(msg).__name__
            print(f"\n[{idx}] Message Type: {msg_type}")
            
            if hasattr(msg, 'content'):
                content_preview = str(msg.content)[:200] if msg.content else "None"
                print(f"    Content: {content_preview}...")
            
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"    Tool Calls: {len(msg.tool_calls)}")
                for tool_call in msg.tool_calls:
                    print(f"      - Tool: {tool_call.get('name', 'unknown')}")
                    print(f"        Args: {tool_call.get('args', {})}")
            
            if hasattr(msg, 'name'):
                print(f"    Tool Name: {msg.name}")
        print("="*80 + "\n")
        
        # Extract raw text response
        raw_response = response["messages"][-1].content
        
        print("\n" + "="*80)
        print("🤖 BOOKING AGENT - RAW OUTPUT")
        print("="*80)
        print(f"Response Type: {type(raw_response)}")
        print(f"Response Length: {len(str(raw_response))} characters")
        print(f"Response Content:")
        print("-" * 80)
        print(raw_response)
        print("="*80 + "\n")
        
        db.close()
        return raw_response
