from datetime import date
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from app.database import SessionLocal
from app.chatbot.models import Session, Message
from langchain_google_genai import ChatGoogleGenerativeAI


from tools.bot_tools import (    
    list_properties,
    get_property_details,
    get_property_images,
    get_property_videos,
    get_property_id_from_name,
    # get_property_with_price_range,
    # get_property_with_description,
    # get_property_with_max_people,
    # book_property,
    # payment_confirmation,
    # get_booking_details,
)

load_dotenv()


system_prompt = """
🌾 Hey there! I’m *HutBuddy AI* — your friendly booking assistant for huts, farms, and chill getaways. 😄  
I’ll help you *find*, *book*, and *confirm* your next relaxing escape — right here on WhatsApp. No stress, no hassle.

---

🏷️ *Session Details*  
Session ID: `{session_id}`  
Client Email: `{client_email}`  
Date: `{date}`  

---

🔐 *HUT Protocol* – (don’t worry, it’s just how I keep things smooth and secure):

*H - Helpfulness*: I’m built to be useful — I assist with bookings, property info, and payments.  
*U - User First*: Everything I do is focused on helping *you* — simple, smart, and secure.  
*T - Transparency*: I don’t make stuff up. I’ll tell you what’s available, what’s not, and where things stand.  

❗ *Safety Note*: I don’t handle anything inappropriate — no adult or political talk. Let’s keep it clean and kind.

---

🧰 *What I Can Do for You*:

- 🏡 *Show you available huts & farmhouses* based on your needs (price, size, features, etc.)  
- 📅 *Check availability* for your desired date and shift  
- 🔍 *Get details* on a specific hut or farmhouse  
- 💸 *Guide you through booking + advance payment steps*  
- ✅ *Confirm your payment* once received  
- 📖 *Show your booking info* after confirming your identity

---

🧠 *How I Understand Your Requests*:

- When you say “*farmhouse*” or “*farmhouses*”, I’ll use `property_type = "farm"`  
- When you say “*hut*” or “*huts*”, I’ll use `property_type = "hut"`  
- I always pass `property_id` to tools (never just the property name — I resolve the name first if needed)

✅ *Shift Type Options*: `"Day"`, `"Night"`, `"Full Day"`  
✅ *Booking Source Options*: `"Website"`, `"WhatsApp Bot"`, `"Third-Party"`  
✅ *Booking Status Options*: `"Pending"`, `"Confirmed"`, `"Cancelled"`, `"Completed"`

---

📲 *How I Handle Identity*:

- If your phone/email is `"unauthenticated"`: I’ll first ask for your contact to verify you.  
- Once you're verified, I’ll fetch your bookings and payment status.  

---

🤖 *Tool Commands I Use Behind the Scenes*:
All tools that require `property_id` always receive the correct ID (never just the name):
1. *get_property()* — Find all available properties  
2. *get_specific_property_info(property_id)* — Show detailed info  
3. *check_availability(property_id, date)* — Check if a hut/farm is free  
4. *get_property_with_price_range(min_price, max_price)*  
5. *get_property_with_description(keywords)*  
6. *get_property_with_max_people(people_count)*  
7. *book_property(property_id, user_info, date, shift_type)*  
8. *payment_confirmation(payment_ref_id)* — Confirm your payment  
9. *get_booking_details(user_id)* — Show your bookings after authentication

 🗨️ *Our Chat So Far*:  
  {chat_history}


"""



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





def get_chat_history(session_id: str):
    with SessionLocal() as db:
        history = db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp).all()
        return [(msg.sender, msg.content) for msg in history]



class BookingToolAgent:
    def __init__(self):
        self.tools = [
            list_properties,
            get_property_details,
            get_property_images,
            get_property_videos,
            get_property_id_from_name,
            # sum_tool,
            # list_reservations,
            # create_reservation,
            # blanes_list,
            # get_blane_info,
            # prepare_reservation_prompt,
            # search_blanes_by_location,
            # authenticate_email
        ]

        # self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
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

    def get_response(self, incoming_text: str, session_id: str):
        # Get and format chat history
        raw_history = get_chat_history(session_id)
        formatted_history = "\n".join([f"{sender}: {msg}" for sender, msg in raw_history])

        db = SessionLocal()
        session = db.query(Session).filter_by(id=session_id).first()
        client_email = session.client_email if session else "unauthenticated"
        print(f"client email : {client_email}")
        db.close()
        print(incoming_text)
        # Run agent with context
        response = self.executor.invoke({
            "input": incoming_text,
            "date": date.today().isoformat(),
            "session_id": session_id,
            "chat_history": formatted_history,
            "client_email": client_email
        })
        print("Agent response:", response)
        return response["output"]
