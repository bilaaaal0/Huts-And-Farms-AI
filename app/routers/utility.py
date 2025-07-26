from datetime import datetime, timedelta
from app.database import SessionLocal
from app.chatbot.models import Message
import tiktoken
from typing import Tuple


try:
   
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception as e:
    print(f"⚠️ Failed to load tiktoken, falling back to simple estimation: {e}")
    tokenizer = None


def count_tokens(text: str) -> int:
    """
    Count tokens using tiktoken library for accurate token counting.
    Falls back to simple estimation if tiktoken fails.
    
    Args:
        text: The text to count tokens for
        
    Returns:
        int: Number of tokens in the text
    """
    if tokenizer:
        try:
            return len(tokenizer.encode(text))
        except Exception as e:
            print(f"⚠️ Tiktoken encoding failed: {e}")
    
    # Fallback to simple estimation (1 token ≈ 4 characters)
    return max(1, len(text) // 4)


def is_hourly_messages_limit_exceeded(session_id: str, max_per_hour: int = 5) -> bool:
    """
    Check if user has exceeded hourly message limit.
    
    Args:
        session_id: The session ID to check
        max_per_hour: Maximum messages allowed per hour
    
    Returns:
        bool: True if limit exceeded, False otherwise
    """
    now = datetime.utcnow()
    window_size = now - timedelta(hours=1)
    
    with SessionLocal() as db:
        count = db.query(Message).filter(
            Message.session_id == session_id,
            Message.sender == "user",
            Message.timestamp >= window_size
        ).count()
        
        return count >= max_per_hour


def is_hourly_token_limit_exceeded(
    session_id: str, 
    current_message: str, 
    max_tokens_per_hour: int = 500
) -> bool:
    """
    Check if user has exceeded hourly token limit using accurate token counting.
    
    Args:
        session_id: The session ID to check
        current_message: The current message to add to token count
        max_tokens_per_hour: Maximum tokens allowed per hour (default: 10,000)
    
    Returns:
        Tuple[bool, int]: (is_exceeded, current_total_tokens)
    """
    now = datetime.utcnow()
    window_size = now - timedelta(hours=1)
    
    with SessionLocal() as db:
        # Get all user messages in the last hour
        recent_messages = db.query(Message).filter(
            Message.session_id == session_id,
            Message.sender == "user",
            Message.timestamp >= window_size
        ).all()
        
        # Calculate total tokens from recent messages using accurate counting
        total_tokens = sum(count_tokens(msg.content) for msg in recent_messages)
        
        # Add tokens from current message
        current_tokens = count_tokens(current_message)
        total_tokens += current_tokens
        
        return total_tokens >= max_tokens_per_hour


