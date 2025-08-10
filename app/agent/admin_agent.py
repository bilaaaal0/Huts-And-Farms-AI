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

# Import your booking tools
from tools.booking import confirm_booking_payment, reject_booking_payment

system_prompt = """
You are *ADMIN BOT*, you will receive a verification message from *HutFarm-Booking AI*, you will wait until admin verifies payment details, then you will send a message to the user that their booking is confirmed or cancelled
with the reason of cancellation.

✅ To CONFIRM: Reply `confirm <booking_id>`
❌ To REJECT: Reply `reject <booking_id> [reason]`

When admin says "confirm <booking_id>", you MUST use the confirm_booking_payment tool.
When admin says "reject <booking_id> [reason]", you MUST use the reject_booking_payment tool.

The tools will return a response containing customer_phone and message - you must return this data so the webhook can send it to the customer.

Chat History:
{chat_history}
"""

class AdminAgent:
    def __init__(self):
        # ✅ Add the booking tools
        self.tools = [confirm_booking_payment, reject_booking_payment]

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

        self.prompt = ChatPromptTemplate(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
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
    
    def convert_messages_to_langchain_format(self, messages: List[Message]) -> List:
        """Convert database Message objects to LangChain message format"""
        langchain_messages = []
        
        for msg in messages:
            # Assuming your Message model has 'content' and 'sender_type' or similar fields
            # Adjust these field names based on your actual Message model structure
            
            if hasattr(msg, 'sender') and msg.sender == 'user':
                langchain_messages.append(HumanMessage(content=msg.content))
            elif hasattr(msg, 'sender') and msg.sender == 'admin':
                langchain_messages.append(HumanMessage(content=msg.content))
            else:
                # Default to AI message if it's from the bot
                langchain_messages.append(AIMessage(content=msg.content))
                
        return langchain_messages
        
    def get_response(self, incoming_text: str, session_id: str):
        db = SessionLocal()
        try:
            session = db.query(Session).filter_by(id=session_id).first()
            user_id = session.user.user_id
            # --- Get chat history and convert to LangChain format ---
            chat_history_objects = db.query(Message).filter_by(user_id=user_id).order_by(Message.timestamp.asc()).all()
            chat_history = self.convert_messages_to_langchain_format(chat_history_objects)
            
            print(f"Chat history converted: {len(chat_history)} messages")
            
            print(f"📥 Admin input: {incoming_text}")
            
            # Run agent with context
            response = self.executor.invoke({
                "input": incoming_text,
                "chat_history": chat_history,
            })
            
            print(f"🤖 Agent response: {response}")
            
            # ✅ Check if the response contains tool results
            agent_output = response.get("output", "")
            
            # Parse the response to extract booking confirmation data
            # The tools return structured data that we need to pass back to webhook
            if "confirm_booking_payment" in str(response) or "reject_booking_payment" in str(response):
                # Look for tool results in the agent's intermediate steps
                if hasattr(response, 'intermediate_steps') and response.intermediate_steps:
                    for step in response.intermediate_steps:
                        if len(step) > 1 and isinstance(step[1], dict):
                            tool_result = step[1]
                            if tool_result.get("success") and "customer_phone" in tool_result:
                                return tool_result
            
            return agent_output
            
        except Exception as e:
            print(f"❌ Error in AdminAgent: {e}")
            return {"error": f"Error processing admin request: {str(e)}"}
        finally:
            db.close()