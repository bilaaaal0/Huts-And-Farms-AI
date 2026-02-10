"""
Memory Manager for LangGraph State-Based Chat Memory

This module prepares optimal memory context for the booking agent:
- Loads existing summary and recent messages
- Decides when to trigger summarization
- Manages memory lifecycle

NOT using LangChain memory classes - explicit state management.
"""

from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc

from app.database import SessionLocal
from app.models import Session, Message
from app.repositories.session_repository import SessionRepository
from app.agents.memory.summarizer import generate_summary
from app.agents.memory.state_detector import should_summarize


@dataclass
class MemoryContext:
    """
    Memory context returned to the agent.
    
    This is NOT database truth - it's working memory for one invocation.
    """
    summary: Optional[str]
    recent_messages: List[Dict[str, str]]  # [{"role": "user", "content": "..."}]
    session_state: Dict[str, any]  # Facts from Session table


def prepare_memory(
    session_id: str,
    incoming_text: str,
    db: Optional[DBSession] = None
) -> MemoryContext:
    """
    Prepare optimal memory context for agent invocation.
    
    This function runs BEFORE every agent call and decides:
    - What summary to use
    - What messages to keep
    - When to trigger summarization
    
    Args:
        session_id: Session ID
        incoming_text: New user message
        db: Database session (optional, creates new if None)
        
    Returns:
        MemoryContext with summary, recent messages, and session state
        
    Flow:
        1. Load existing summary + last 6 messages
        2. Append incoming message
        3. Check if summarization needed (deterministic)
        4. Summarize if needed
        5. Trim to last 4 messages
        6. Persist summary
        7. Return memory payload
    """
    should_close_db = db is None
    if db is None:
        db = SessionLocal()
    
    try:
        # STEP 1: Load existing memory
        session_repo = SessionRepository()
        session = session_repo.get_by_id(db, session_id)
        
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        user_id = session.user.user_id
        
        # Load existing summary
        existing_summary = session.conversation_summary
        
        # Load last 6 raw messages (enough to summarize, not too many)
        recent_messages = _load_recent_messages(db, user_id, limit=6)
        
        # STEP 2: The incoming message is already saved to DB and included in recent_messages
        # We need to exclude it from summarization since it's the current message being processed
        
        # STEP 3: Decide if summarization is needed (DETERMINISTIC)
        needs_summary = should_summarize(
            message_count=len(recent_messages),
            session=session,
            recent_messages=recent_messages
        )
        
        # STEP 4: Summarize if needed
        if needs_summary:
            print(f"🧠 Triggering summarization for session {session_id}")
            
            # Exclude the last message (incoming message) from summary
            # Only summarize the conversation history BEFORE the current message
            messages_to_summarize = recent_messages[:-1] if len(recent_messages) > 0 else []
            
            new_summary = generate_summary(
                previous_summary=existing_summary,
                recent_messages=messages_to_summarize,
                session_state=_extract_session_state(session),
                generation_count=session.summary_generation_count or 0
            )
            
            # STEP 6: Persist summary and update counters
            session.conversation_summary = new_summary
            session.summary_updated_at = datetime.utcnow()
            session.summary_generation_count = (session.summary_generation_count or 0) + 1
            session.needs_summarization = False  # Clear the flag
            db.commit()
            
            existing_summary = new_summary
            
            # STEP 5: Trim messages after summarization
            recent_messages = recent_messages[-4:]  # Keep only last 4
        else:
            # Keep last 4 even without summarization
            recent_messages = recent_messages[-4:]
        
        # STEP 7: Return memory payload
        return MemoryContext(
            summary=existing_summary,
            recent_messages=recent_messages,
            session_state=_extract_session_state(session)
        )
        
    finally:
        if should_close_db:
            db.close()


def _load_recent_messages(db: DBSession, user_id: str, limit: int = 6) -> List[Dict[str, str]]:
    """
    Load recent messages from database.
    
    Args:
        db: Database session
        user_id: User ID
        limit: Number of messages to load
        
    Returns:
        List of message dicts with role and content
    """
    messages = (
        db.query(Message)
        .filter(Message.user_id == user_id)
        .order_by(desc(Message.timestamp))
        .limit(limit)
        .all()
    )
    
    # Reverse to get chronological order (oldest first)
    formatted = []
    for msg in reversed(messages):
        role = "user" if msg.sender == "user" else "assistant"
        formatted.append({
            "role": role,
            "content": msg.content
        })
    
    return formatted


def _extract_session_state(session: Session) -> Dict[str, any]:
    """
    Extract session state facts for context.
    
    This is the SOURCE OF TRUTH - updated only by tools.
    
    Args:
        session: Session object
        
    Returns:
        Dict of session facts
    """
    return {
        "property_type": session.property_type,
        "booking_date": session.booking_date.isoformat() if session.booking_date else None,
        "shift_type": session.shift_type,
        "property_id": str(session.property_id) if session.property_id else None,
        "booking_id": session.booking_id,
        "min_price": float(session.min_price) if session.min_price else None,
        "max_price": float(session.max_price) if session.max_price else None,
        "max_occupancy": session.max_occupancy,
        "source": "Bot"  # Always Bot for booking agent interactions
    }


def clear_memory(session_id: str, db: Optional[DBSession] = None) -> bool:
    """
    Clear conversation memory for a session.
    
    This clears the summary but keeps session state facts.
    
    Args:
        session_id: Session ID
        db: Database session (optional)
        
    Returns:
        True if successful
    """
    should_close_db = db is None
    if db is None:
        db = SessionLocal()
    
    try:
        session_repo = SessionRepository()
        session = session_repo.get_by_id(db, session_id)
        
        if session:
            session.conversation_summary = None
            session.summary_updated_at = None
            db.commit()
            return True
        
        return False
        
    finally:
        if should_close_db:
            db.close()
