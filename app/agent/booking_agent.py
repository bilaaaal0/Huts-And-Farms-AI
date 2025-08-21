from datetime import date
from xml.parsers.expat import model
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent
from app.database import SessionLocal
from app.chatbot.models import Session, Message
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai
import os
from sqlalchemy import text
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from langchain.schema import HumanMessage, AIMessage



genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

from tools.booking import (
    create_booking,
    process_payment_screenshot,
    process_payment_details,
    check_booking_status,
    cancel_booking,
    get_payment_instructions,
    
)

from tools.bot_tools import (    
    list_properties,
    get_property_details,
    get_property_images,
    get_property_videos,
    get_property_id_from_name,
    introduction_message,
    # get_booking_id_from_user_booking_id,
    check_message_relevance,
    check_booking_date,
    translate_response
    # validate_and_extract_date
    # get_property_with_price_range,
    # get_property_with_description,
    # get_property_with_max_people,
    # book_property,
    # payment_confirmation,
    # get_booking_details,
)

load_dotenv()

system_prompt = """
🌾 Assalam-u-Alaikum! Main HutBuddy AI hun — ap ka friendly booking assistant huts aur farmhouses ke liye. 😄  
Main ap ki madad karunga relaxing getaways find karne, book karne, aur confirm karne mein — bilkul yahan WhatsApp par.

---
🏷️ **Session Context**  
ID: {session_id} | Email: {client_email} | Date: {date}  
Current Search: {property_type} | {booking_date} | {shift_type} | Price Range: {min_price}-{max_price} | Guests: {max_occupancy}

---

🧰 **Main Services**
- 🏡 Available huts/farmhouses search with filters (price, size, features)
- 📅 Availability checking for specific dates and shifts  
- 🔍 Detailed information with images/videos
- 💸 Booking process and payment guidance
- ✅ Payment confirmation and booking management

---

🗣️ **Communication Rules**
- **Language**: Match user's language (English/Roman Urdu). Use *translate_response* tool to convert into user qeuried langauge. Use respectful "ap", never "tum"
- **Terminology**: Always say "farmhouse"/"hut", never "property"  
- **Boundaries**: Only discuss booking-related topics
- **Creator**: If asked who made me → "I am a product of Prismify-Core"
- **Irrelevant queries** → "Main sirf farmhouse aur hut booking mein madad kar sakta hun. Kya main ap ko koi farmhouse ya hut dhundne mein madad kar sakta hun?"

---

🗓️ **Date & Booking Logic**
- **Input Mapping**: "farmhouse/farmhouses" → farm | "hut/huts" → hut
- **Shifts**: Day, Night, Full Day only
- **Date Validation**: 
  - Only current/next month bookings allowed
  - Past dates → "Yeh date past mein hai, future date select kariye"  
  - Relative dates ("Sunday night") → Extract and confirm exact date
  - Invalid years (2090) → Reject politely
- **Smart Recognition**: 
  - Partial names: "White Palace" → "White Palace FarmHouse"
  - Numbers: "1st", "second", "#2" → Select from list
  - Misspellings: Auto-correct common mistakes

---

🔐 **Security & Privacy**  
- Never show internal IDs (booking_id, property_id) to users
- Use user-friendly booking references only  
- Require authentication before showing personal booking details
- Keep all interactions appropriate and family-friendly

---

🎯 **Required Tools Usage**
- `check_message_relevance()` before processing queries  
- Always use `property_id` when calling tools, resolve names first if needed
- Always call 'translate_response()' in the end

---

**Response Templates:**
- Date Confirmation: "Ap ka matlab [extracted_date] ([day_name]) hai? Please confirm kar dijiye."
- Authentication needed: "Booking details dekhne ke liye pehle ap ka contact verify karna hoga."

Use chat history to provide context and continuity. Meharbani kar ke batayiye, main ap ki kya madad kar sakta hun? 🙏
"""


# system_prompt = """
# 🌾 Assalam-u-Alaikum! Main HutBuddy AI hun — ap ka friendly booking assistant huts, farms, aur chill getaways ke liye. 😄  
# Main ap ki madad karunga huts/farmhouses find karne, book karne, aur confirm karne mein ap ka next relaxing escape — bilkul yahan WhatsApp par. No stress, no hassle.

# ---

# 🏷️ Session Details  
# Session ID: {session_id}  
# Client Email: {client_email}  
# Date: {date}  

# Booking Details:
# -property_type: {property_type}
# -booking_date: {booking_date}
# -shift_type: {shift_type}
# -min_price: {min_price}
# -max_price: {max_price}
# -max_occupancy: {max_occupancy}

# ---

# 🔐 HUT Protocol – (don't worry, yeh bas mera tarika hai smooth aur secure rakhne ka):

# H - Helpfulness: Main helpful banne ke liye bana hun — main assist karta hun bookings, property info, aur payments mein.  
# U - User First: Jo bhi main karta hun ap ke liye karta hun — simple, smart, aur secure.  
# T - Transparency: Main jhooth nahi bolta. Bataunga kya available hai, kya nahi, aur situation kya hai.  

# ❗ Safety Note: Main kuch inappropriate handle nahi karta — koi adult ya political baat nahi. Bhai jaan, sab kuch clean aur kind rakhte hain.

# ---

# 🧰 Main Ap Ke Liye Kya Kar Sakta Hun:

# 🏡 Dikhaunga available huts & farmhouses ap ki needs ke hisab se (price, size, features, etc.)
# 📅 Check karunga availability ap ki desired date aur shift ke liye
# 🔍 Details dunga kisi specific hut ya farmhouse ki
# 💸 Guide karunga booking + advance payment steps mein
# ✅ Confirm karunga ap ka payment jab receive ho jaye
# 📖 Dikhaunga ap ki booking info identity confirm karne ke baad
# ---

# 🧠 Main Kaise Samajhta Hun Ap Ki Requests:

# Jab ap "farmhouse" ya "farmhouses" kehte hain, main use karunga property_type = "farm"
# Jab ap "hut" ya "huts" kehte hain, main use karunga property_type = "hut"
# Main hamesha property_id pass karta hun tools ko (kabhi sirf property name nahi — pehle name resolve karta hun agar zarurat ho)
# ✅ Shift Type Options: "Day", "Night", "Full Day"  
# ✅ Booking Source Options: "Website", "WhatsApp Bot", "Third-Party"  
# ✅ Booking Status Options: "Pending", "Confirmed", "Cancelled", "Completed"


# ---

# 🚫 **Conversation Boundaries & Guidelines:**

# - **Irrelevant Questions**: Main sirf farmhouse/hut booking ke baare mein baat karta hun. Agar koi off-topic sawal ho to politely redirect karunga.
# - **Creator Question**: Agar koi puchhe "who created you" ya "tumhe kisne banaya", to main kahunga: "I am a product of Prismify-Core"
# - **Language**: Hamesha "farmhouse" ya "hut" kehna hai, kabhi "property" word use nahi karna
# - **ID Security**: Kabhi bhi booking_id, property_id ya koi internal IDs user ko nahi dikhana. User ko sirf user-friendly booking reference dena

# 🗓️ **Date Validation Rules:**
# - **Relative Dates**: Agar user "Sunday night" kehta hai to nearest upcoming Sunday confirm karna
# - **Future Dates Only**: Sirf current month aur next month ki dates accept karna  
# - **Past Dates**: Agar past date ho to kehna "Yeh date past mein hai, koi future date select kariye"
# - **Invalid Years**: 2090 jaise unrealistic dates ko reject karna

# 🎯 **Smart Date Recognition Examples:**
# - "Sunday night" → "Ap ka matlab [date] (next Sunday) hai?"
# - "Tomorrow" → Extract exact date and confirm
# - "Next weekend" → Show upcoming weekend dates for confirmation
# - "Christmas" → Extract 25th December of current year if future, else next year

# ---

# 📋 **Booking Flow Requirements:**
# - Pehle date validate karna using validate_and_extract_date tool
# - Agar user "Sunday night" kehta hai to exact date extract kar ke confirm karna
# - Booking reference generate karne ke liye generate_user_booking_reference tool use karna
# - User ko kabhi internal IDs nahi dikhana, sirf user-friendly reference dena
# - Har message pehle check_message_relevance se validate karna

# **Response Templates:**
# - Irrelevant: "Main sirf farmhouse aur hut booking mein madad kar sakta hun. Kya main ap ko koi farmhouse ya hut dhundne mein madad kar sakta hun?"
# - Creator: "I am a product of Prismify-Core. Kya main ap ko farmhouse booking mein madad kar sakta hun?"
# - Date Confirmation: "Ap ka matlab [extracted_date] ([day_name]) hai? Please confirm kar dijiye."


# 🎯 **Smart Property Recognition**: Main samajh sakta hun:
# - Partial names: "White Palace" se "White Palace FarmHouse" find kar dunga
# - Misspelled names: "Whit Palac" ya "farmhous" bhi samajh jaunga  
# - Serial numbers: "1", "first", "pehla", "#1" se first property select kar dunga
# - Natural language: "details of second property", "show me number 2"


# 📲 Main Kaise Handle Karta Hun Identity:

# Agar ap ka phone/email "unauthenticated" hai: Pehle puchunga ap ka contact verify karne ke liye.
# Jab ap verified ho jaenge, tab fetch karunga ap ki bookings aur payment status.




# ---

# 🗣️ Language Guidelines:

# - Main wahi language use karta hun jis mein ap sawal puchte hain
# - Urdu speakers ke liye Roman Urdu use karta hun
# - Urdu words use karta hun: Bhai jaan, Janab, Meharbani, Shukria
# - Hamesha "ap" kehta hun, "tum" nahi
# - Agar ap English mein puchte hain, main English mein jawab deta hun
# - Agar ap Urdu/Roman mein puchte hain, main Roman Urdu mein jawab deta hun

# Meharbani kar ke batayiye, main ap ki kya madad kar sakta hun? 🙏

# Use chat history to provide context and continuity in our conversation.

# """

#  🗨️ Our Chat So Far:  
#    {chat_history}



# ---

# 🤖 *Tool Commands I Use Behind the Scenes*:
# All tools that require `property_id` always receive the correct ID (never just the name):
# 1. *get_property()* — Find all available properties  
# 2. *get_specific_property_info(property_id)* — Show detailed info  
# 3. *check_availability(property_id, date)* — Check if a hut/farm is free  
# 4. *get_property_with_price_range(min_price, max_price)*  
# 5. *get_property_with_description(keywords)*  
# 6. *get_property_with_max_people(people_count)*  
# 7. *book_property(property_id, user_info, date, shift_type)*  
# 8. *payment_confirmation(payment_ref_id)* — Confirm your payment  
# 9. *get_booking_details(user_id)* — Show your bookings after authentication
# ---

# 💬 *WhatsApp Message Style*  
# Since you're chatting with me on WhatsApp, I follow this style:

# * _Italics_: _text_  
# * *Bold*: *text*  
# * ~Strikethrough~: ~text~  
# * Monospace: ```text```  
# * Bullet Lists:  
#   - item 1  
#   - item 2  
# * Numbered Lists:  
#   1. item one  
#   2. item two  
# * Quotes:  
#   > quoted message  
# * Inline code: `text`

# ---





# def get_chat_history(session_id: str):
#     with SessionLocal() as db:
#         history = db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp).all()
#         return [(msg.sender, msg.content) for msg in history]

# def get_chat_history(session_id: str, current_query_embedding: List[float], top_k: int = 15) -> List[Tuple[str, str]]:
#     with SessionLocal() as db:
#         sql = """
#                 SELECT DISTINCT user_msg.content AS user_query,
#                     bot_msg.content AS bot_response,
#                     user_msg.query_embedding <#> (:embedding)::vector AS similarity
#                 FROM messages AS user_msg
#                 JOIN messages AS bot_msg
#                     ON bot_msg.timestamp > user_msg.timestamp
#                     AND bot_msg.session_id = user_msg.session_id
#                     AND bot_msg.sender = 'bot'
#                 WHERE user_msg.session_id = :session_id
#                 AND user_msg.sender = 'user'
#                 AND user_msg.query_embedding IS NOT NULL
#                 ORDER BY similarity ASC
#                 LIMIT :top_k
#                 """

#         result = db.execute(
#             text(sql),
#             {"embedding": current_query_embedding, "session_id": session_id, "top_k": top_k}
#         ).fetchall()

#         return [{"user": row[0], "bot": row[1]} for row in result]
    
from sqlalchemy import desc

def get_chat_history_normal(user_id: str):
    with SessionLocal() as db:
        
        history = (
            db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(desc(Message.timestamp))
            .limit(30)
            .all()
        )
        # reverse the order to show oldest first (chat style)
        return [msg.content for msg in reversed(history)]


def get_chat_history(user_id: str, current_query_embedding: List[float], top_k: int = 15, chat_history: List[Dict[str, str]] = []) -> List[Dict[str, str]]:
    """
    Retrieve chat history using cosine similarity, properly grouping multi-message conversations.
    
    Args:
        session_id (str): The session ID to filter messages
        current_query_embedding (List[float]): The embedding of the current user query (3072 dimensions)
        top_k (int): Number of most similar conversations to return
    
    Returns:
        List[Dict[str, str]]: List of conversation pairs with format [{"user": "...", "bot": "..."}]
    """
    print("Inside get_chat_history")
    
    # If no embedding provided, return empty list
    if not current_query_embedding or len(current_query_embedding) == 0:
        print("[⚠️] No embedding provided, returning empty chat history")
        return []
    
    db = SessionLocal()
    
    try:
        # Step 1: Get top similar user queries using cosine similarity
        similarity_sql = """
        SELECT 
            id,
            content,
            timestamp,
            (query_embedding <#> (:embedding)::vector) as similarity_score
        FROM messages 
        WHERE user_id = :user_id 
        AND sender = 'user' 
        AND query_embedding IS NOT NULL
        ORDER BY similarity_score ASC
        LIMIT :top_k
        """
        
        similar_queries = db.execute(
            text(similarity_sql),
            {
                "embedding": current_query_embedding,
                "user_id": user_id,
                "top_k": top_k
            }
        ).fetchall()
        
        if not similar_queries:
            print("[⚠️] No similar queries found")
            return []
        
        print(f"[🔍] Found {len(similar_queries)} similar queries")
        
        # Extract the message IDs of similar queries
        similar_query_ids = [row[0] for row in similar_queries]
        
        # Step 2: Get ALL messages for this session to build conversation groups
        all_messages_sql = """
        SELECT id, content, sender, timestamp
        FROM messages 
        WHERE user_id = :user_id
        ORDER BY timestamp ASC, id ASC
        """
        
        all_messages = db.execute(
            text(all_messages_sql),
            {"user_id": user_id}
        ).fetchall()
        
        if not all_messages:
            print("[⚠️] No messages found for session")
            return []
        
        # Step 3: Group consecutive messages by sender and find conversation pairs
        conversation_pairs = build_conversation_pairs(all_messages, similar_query_ids)
        
        # Step 4: Sort by similarity (maintain order from similarity query)
        ordered_pairs = []
        for query_row in similar_queries:
            query_id = query_row[0]
            similarity_score = query_row[3]
            
            # Find the conversation pair that starts with this query
            for pair in conversation_pairs:
                if pair['query_start_id'] == query_id:
                    pair['similarity_score'] = similarity_score
                    ordered_pairs.append(pair)
                    break
        
        print(f"[📜] Built {len(ordered_pairs)} conversation pairs")
        
        # Debug: Print similarity scores
        if ordered_pairs:
            print("[🔍] Top conversation pairs:")
            for i, pair in enumerate(ordered_pairs[:3]):
                user_preview = pair['user'][:50] + "..." if len(pair['user']) > 50 else pair['user']
                print(f"  {i+1}. Score: {pair['similarity_score']:.4f} | User: {user_preview}")
        
        # Return only user/bot content (remove metadata)
        # return [{"user": pair["user"], "bot": pair["bot"]} for pair in ordered_pairs]
        for pair in ordered_pairs:
            if pair["user"]:
                chat_history.append(HumanMessage(content=pair["user"]))
            if pair["bot"]:
                chat_history.append(AIMessage(content=pair["bot"]))
        return chat_history
    except Exception as e:
        print(f"[❌] Error retrieving chat history: {e}")
        
        # Fallback: Get recent sequential conversations
        try:
            print("[🔄] Falling back to sequential history...")
            return get_sequential_fallback_history(db, user_id, min(top_k, 10))
        except Exception as e2:
            print(f"[❌] Fallback also failed: {e2}")
            return []
    
    finally:
        db.close()


def build_conversation_pairs(all_messages: List, similar_query_ids: List[int]) -> List[Dict]:
    """
    Build conversation pairs by grouping consecutive messages from same sender.
    
    Args:
        all_messages: All messages ordered by timestamp
        similar_query_ids: IDs of similar user queries to prioritize
    
    Returns:
        List of conversation pairs with grouped messages
    """
    conversation_pairs = []
    i = 0
    
    while i < len(all_messages):
        current_msg = all_messages[i]
        
        # Only process if this is a user message that's in our similar queries
        if current_msg[2] == 'user' and current_msg[0] in similar_query_ids:
            
            # Step 1: Group consecutive user messages
            user_messages = [current_msg[1]]  # content
            query_start_id = current_msg[0]   # first message ID
            j = i + 1
            
            # Collect all consecutive user messages
            while j < len(all_messages) and all_messages[j][2] == 'user':
                user_messages.append(all_messages[j][1])
                j += 1
            
            # Step 2: Group consecutive bot responses that follow
            bot_messages = []
            while j < len(all_messages) and all_messages[j][2] == 'bot':
                bot_messages.append(all_messages[j][1])
                j += 1
            
            # Step 3: Create conversation pair if we have both user and bot messages
            if bot_messages:
                conversation_pairs.append({
                    'query_start_id': query_start_id,
                    'user': ' '.join(user_messages),  # Combine multi-part user messages
                    'bot': ' '.join(bot_messages),    # Combine multi-part bot responses
                })
            
            # Move to next unprocessed message
            i = j
        else:
            i += 1
    
    return conversation_pairs


def get_sequential_fallback_history(db, user_id: str, limit: int = 5) -> List[Dict[str, str]]:
    """
    Fallback function to get recent conversation history sequentially when similarity search fails.
    Enhanced to handle multi-message conversations.
    
    Args:
        db: Database session
        session_id (str): The session ID
        limit (int): Maximum number of conversation pairs to return
    
    Returns:
        List[Dict[str, str]]: Recent conversation pairs
    """
    try:
        # Get recent messages ordered by timestamp
        recent_messages_query = """
        SELECT id, content, sender, timestamp
        FROM messages 
        WHERE user_id = :user_id
        ORDER BY timestamp ASC, id ASC
        """
        
        recent_messages = db.execute(
            text(recent_messages_query),
            {"user_id": user_id}
        ).fetchall()
        
        if not recent_messages:
            return []
        
        # Use the same grouping logic but for all recent messages
        all_query_ids = [msg[0] for msg in recent_messages if msg[2] == 'user']
        conversation_pairs = build_conversation_pairs(recent_messages, all_query_ids)
        
        # Return the most recent conversations (up to limit)
        return [{"user": pair["user"], "bot": pair["bot"]} 
                for pair in conversation_pairs[-limit:]]
    
    except Exception as e:
        print(f"[❌] Sequential fallback failed: {e}")
        return []


def format_chat_history_for_prompt(chat_history: List[Dict[str, str]]) -> str:
    """
    Format chat history for inclusion in the system prompt.
    
    Args:
        chat_history: List of conversation pairs
    
    Returns:
        str: Formatted chat history string
    """
    if not chat_history:
        return "No previous conversation history."
    
    formatted_lines = []
    for i, conversation in enumerate(chat_history, 1):
        formatted_lines.append(f"Previous Conversation {i}:")
        formatted_lines.append(f"User: {conversation['user']}")
        formatted_lines.append(f"Assistant: {conversation['bot']}")
        formatted_lines.append("---")
    
    return "\n".join(formatted_lines)


# Additional helper function for debugging
def debug_message_flow(session_id: str, db_session=None):
    """
    Debug function to visualize message flow in a session.
    Useful for understanding how messages are grouped.
    """
    if not db_session:
        db_session = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        messages = db_session.execute(
            text("SELECT id, content, sender, timestamp FROM messages WHERE session_id = :session_id ORDER BY timestamp ASC"),
            {"session_id": session_id}
        ).fetchall()
        
        print(f"\n[🔍] Message Flow for Session: {session_id}")
        print("=" * 60)
        
        for msg in messages:
            sender_icon = "👤" if msg[2] == 'user' else "🤖"
            content_preview = msg[1][:50] + "..." if len(msg[1]) > 50 else msg[1]
            print(f"{sender_icon} ID:{msg[0]} | {msg[2]}: {content_preview}")
            
    finally:
        if should_close:
            db_session.close()

class BookingToolAgent:
    def __init__(self):
        self.tools = [
            list_properties,
            get_property_details,
            get_property_images,
            get_property_videos,
            get_property_id_from_name,
            introduction_message,
            create_booking,
            check_booking_status,
            process_payment_screenshot,
            process_payment_details,
            # cancel_booking,
            get_payment_instructions,
            # get_booking_id_from_user_booking_id,
            check_message_relevance,
            check_booking_date,
            translate_response
            # validate_and_extract_date
            
        ]
        
        # self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)



        self.prompt = ChatPromptTemplate(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name='chat_history'),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        ).partial()

        self.agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )

  
    def get_embedding(self,text: str, task_type: str = "retrieval_document") -> List[float]:
        """
        Generate an embedding for the given text using Google's Gemini embedding model.

        Args:
            text (str): The text to embed.
            task_type (str): Either "retrieval_document" or "retrieval_query".

        Returns:
            List[float]: A list of embedding floats (3072 dimensions).
        """
        try:
            response = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type=task_type,
            )
            return response["embedding"]
        except Exception as e:
            print(f"[❌] Embedding generation failed: {e}")
            return []

    def get_response(self, incoming_text: str, session_id: str, whatsapp_message_id: Optional[str]= None):
        # Get and format chat history
        # raw_history = get_chat_history(session_id)
        # formatted_history = "\n".join([f"{sender}: {msg}" for sender, msg in raw_history])
        

        db = SessionLocal()
        session = db.query(Session).filter_by(id=session_id).first()

        if incoming_text == "Image recieved run process_payment_screenshot":
            booking_id = session.booking_id if session else "None"
            print(f"Booking ID: {booking_id}")
            if booking_id == "None":
                return False
        # --- Save user message ---
        user_id = session.user.user_id
        
        # embedding_user = self.get_embedding(incoming_text)  # Get embedding for user message
        chat_history = []
        # get_chat_history(user_id, embedding_user, chat_history=chat_history)
        chat_history = get_chat_history_normal(user_id=user_id)
        print(f"Chat history: {chat_history}")

        
        db.add(Message(
            user_id=user_id,
            sender="user",
            content=incoming_text,
            # query_embedding = embedding_user,  # Get embedding for user message
            whatsapp_message_id = whatsapp_message_id,
            timestamp=datetime.utcnow()
        ))
        db.commit()


        client_email = session.user.email if session else "unauthenticated"
        property_type = session.property_type if session else "None"
        booking_date = session.booking_date if session else "None"
        shift_type = session.shift_type if session else "None"
        min_price = session.min_price if session else "None"
        max_price = session.max_price if session else "None"
        max_occupancy = session.max_occupancy if session else "None"
        print(f"client email : {client_email}")
        db.close()
        print(incoming_text)
        # Run agent with context
        response = self.executor.invoke({
            "input": incoming_text,
            "date": date.today().isoformat(),
            "session_id": session_id,
            "chat_history": chat_history,
            "client_email": client_email,
            "property_type": property_type,
            "booking_date": booking_date,
            "shift_type": shift_type,
            "min_price": min_price,
            "max_price": max_price,
            "max_occupancy": max_occupancy,
        })
        print("Agent response:", response)
        return response["output"]