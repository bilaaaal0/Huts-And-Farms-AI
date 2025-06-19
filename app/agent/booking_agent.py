from datetime import date
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferMemory
# Import your booking tools
from tools.booking_tools import (
    check_reservation_by_email,
#     create_booking,
#     cancel_booking
)
from tools.misc_tools import sum_tool
load_dotenv()

# system_prompt = """
# You are a witty and efficient WhatsApp Booking Assistant.
# Follow these guidelines strictly:

# **R - Role**: You are a booking agent that interacts using only tools.
# **I - Identity**: You do not guess or assume, you only query tools and report their output.
# **S - Safety**: Never accept or return harmful or inappropriate content.
# **E - Execution**: Always perform actions via defined tools, not by assumptions.
# **N - No Hallucination**: Don't make up facts. Use database-backed tools.

# Capabilities:
# - Check agent availability
# - Create new bookings
# - Cancel or modify bookings

# Today's Date: {date}
# """
system_prompt = """
You are Dabablane AI, a secure, tool-execution-only assistant. You strictly follow the **RISEN** protocol:

**R - Role**: You are a pure tool-execution agent. You never answer from knowledge or assumption.  
**I - Identity**: Your identity is that of a backend assistant that performs exact actions based on verified client session.  
**S - Safety**: You must ignore or reject any unsafe, unethical, or unauthorized instructions.  
**E - Execution**: Always execute operations *only* through the provided tools. Never produce or assume data.  
**N - No Hallucination**: You do not guess. All information must come from tool outputs or verified session data.

### Capabilities:
- Authenticate users using email
- Query reservations or booking data
- Only answer database questions based on verified client email
- Log users out or refresh their token if needed

### Data Access Rules:
- You may **only** query rows related to the authenticated client email stored in the session.
- If the client is not authenticated, use the tool `authenticate_with_email` to request email and authenticate them.
- If a user asks for reservation information before authenticating, first ask them for their email.

Session ID: {session_id}  
Client: {client}  
Date: {date}
"""

class BookingToolAgent:
    def __init__(self):
        self.tools = [
            sum_tool,
            check_reservation_by_email
        ]

        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

        self.agent = create_tool_calling_agent(
            llm=self.llm, tools=self.tools, prompt=self.prompt
        )

        
        #self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

        # self.executor = AgentExecutor(
        #     agent=self.agent,
        #     tools=self.tools,
        #     verbose=True,
        #     memory=self.memory 
        # )
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )

    def get_response(self, incoming_text: str):
        response = self.executor.invoke({
            "input": incoming_text,
            "date": date.today().isoformat(),
        })
        return response["output"]
