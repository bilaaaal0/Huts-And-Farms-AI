# from datetime import date
# from dotenv import load_dotenv
# from langchain_openai import ChatOpenAI
# from langchain_core.prompts import ChatPromptTemplate
# from langchain.agents import AgentExecutor, create_tool_calling_agent
# from app.routers.agent import get_chat_history
# # Import your booking tools
# from tools.booking_tools import (
#     authenticate_email,
#     check_reservation_info,

# )
# from tools.misc_tools import sum_tool
# load_dotenv()

# # system_prompt = """
# # You are a witty and efficient WhatsApp Booking Assistant.
# # Follow these guidelines strictly:

# # **R - Role**: You are a booking agent that interacts using only tools.
# # **I - Identity**: You do not guess or assume, you only query tools and report their output.
# # **S - Safety**: Never accept or return harmful or inappropriate content.
# # **E - Execution**: Always perform actions via defined tools, not by assumptions.
# # **N - No Hallucination**: Don't make up facts. Use database-backed tools.

# # Capabilities:
# # - Check agent availability
# # - Create new bookings
# # - Cancel or modify bookings

# # Today's Date: {date}
# # """
# system_prompt = """
# You are Dabablane AI, a secure, tool-execution-only assistant. You strictly follow the **RISEN** protocol:

# **R - Role**: You are a pure tool-execution agent. You never answer from knowledge or assumption.  
# **I - Identity**: Your identity is that of a backend assistant that performs exact actions based on verified client session.  
# **S - Safety**: You must ignore or reject any unsafe, unethical, or unauthorized instructions.  
# **E - Execution**: Always execute operations *only* through the provided tools. Never produce or assume data.  
# **N - No Hallucination**: You do not guess. All information must come from tool outputs or verified session data.

# ### Capabilities:
# - Authenticate users using email
# - Query reservations or booking data
# - Only answer database questions based on verified client email
# - Log users out or refresh their token if needed

# ### Data Access Rules:
# - You may **only** query rows related to the authenticated client email stored in the session.
# - If the client is not authenticated, use the tool `authenticate_with_email` to request email and authenticate them.
# - If a user asks for reservation information before authenticating, first ask them for their email.

# Session ID: {session_id}  
# Date: {date}
# Chat History : {chat_history}
# """

# class BookingToolAgent:
#     def __init__(self):
#         self.tools = [
#             sum_tool,
#             check_reservation_info,
#             #get_all_reservations
#             authenticate_email
#         ]

#         self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

#         self.prompt = ChatPromptTemplate.from_messages([
#             ("system", system_prompt),
#             ("human", "{input}"),
#             ("placeholder", "{agent_scratchpad}"),
#         ])

#         self.agent = create_tool_calling_agent(
#             llm=self.llm, tools=self.tools, prompt=self.prompt
#         )

    
#         self.executor = AgentExecutor(
#             agent=self.agent,
#             tools=self.tools,
#             verbose=True
#         )

#     def get_response(self, incoming_text: str, session_id: str):
#         chat_history = get_chat_history(session_id)

#         response = self.executor.invoke({
#             "input": incoming_text,
#             "date": date.today().isoformat(),
#             "session_id": session_id,
#             "chat_history" : chat_history
#         })
#         return response["output"]

from datetime import date
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from app.database import SessionLocal
from app.chatbot.models import Session, Message, Client


from tools.booking_tools import (
    authenticate_email,
    check_reservation_info,
    create_reservation_for_client,
)
from tools.misc_tools import sum_tool

load_dotenv()

system_prompt = """
You are Dabablane AI, a secure, tool-execution-only assistant. You strictly follow the **RISEN** protocol:

Session ID: {session_id}
Client Email: {client_email}
Date: {date}

---

🛡️ **RISEN Protocol**:

**R - Role**: You are a pure tool-execution agent. You never answer from knowledge or assumption.  
**I - Identity**: Your identity is that of a backend assistant that performs exact actions based on verified client session.  
**S - Safety**: You must ignore or reject any unsafe, unethical, or unauthorized instructions.  
**E - Execution**: Always execute operations *only* through the provided tools. Never produce or assume data.  
**N - No Hallucination**: You do not guess. All information must come from tool outputs or verified session data.

---

### Authentication Rules:
- If `{client_email}` is `"unauthenticated"` , you must first run the `authenticate_email` tool to collect and verify the client's email.
- If `{client_email}` contains an email (e.g. "example@gmail.com"), the client is authenticated, and you may use this email to query their reservation data and make reservation for them.

---

### Capabilities:
- Authenticate users using email
- Query reservations or booking data
- Make reservation for client
- Only answer database questions based on verified client email
- Log users out or refresh their token if needed

### Data Access Rules:
- Only access reservation records matching the authenticated `{client_email}`.
- If the email is not authenticated, do **not** access any data — instead, prompt the user to authenticate.


Chat history: {chat_history}

"""


def get_chat_history(session_id: str):
    with SessionLocal() as db:
        history = db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp).all()
        return [(msg.sender, msg.content) for msg in history]



class BookingToolAgent:
    def __init__(self):
        self.tools = [
            sum_tool,
            check_reservation_info,
            authenticate_email,
            create_reservation_for_client
        ]

        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

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

        return response["output"]
