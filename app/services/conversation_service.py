"""
Conversation management service.
Handles CRUD operations for conversations and messages.
"""
import json
from typing import Dict, List, Any
from sqlalchemy import text
from ..db import engine
from ..logging_config import logger


def create_conversation() -> int:
    """
    Create a new conversation.
    
    Returns:
        int: The ID of the newly created conversation
    """
    with engine.begin() as conn:
        result = conn.execute(
            text("INSERT INTO conversations DEFAULT VALUES RETURNING id")
        )
        conversation_id = result.scalar_one()
        logger.info("Created new conversation", conversation_id=conversation_id)
        return conversation_id


def store_message(
    conversation_id: int,
    role: str,
    content: str,
    model_provider: str = None,
    model_name: str = None,
    sources: List[Dict] = None
) -> Any:
    """
    Store a message in the conversation.
    
    Args:
        conversation_id: The conversation ID
        role: "user" or "assistant"
        content: The message content
        model_provider: Optional provider name (e.g., "openai", "ollama")
        model_name: Optional model name (e.g., "gpt-4o-mini")
        sources: Optional list of source documents used
        
    Returns:
        The created_at timestamp of the message
    """
    sources_json = json.dumps(sources) if sources is not None else None
    
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO conversation_messages 
                (conversation_id, role, content, model_provider, model_name, sources)
                VALUES (:cid, :role, :content, :provider, :model, :sources)
                RETURNING created_at
            """),
            {
                "cid": conversation_id,
                "role": role,
                "content": content,
                "provider": model_provider,
                "model": model_name,
                "sources": sources_json,
            },
        )
        timestamp = result.scalar_one()
        logger.debug("Stored message", conversation_id=conversation_id, role=role)
        return timestamp


def get_conversation_by_id(conversation_id: int) -> Dict[str, Any]:
    """
    Retrieve all messages from a conversation.
    
    Args:
        conversation_id: The conversation ID
        
    Returns:
        Dictionary with conversation_id and messages list
        
    Raises:
        ValueError: If conversation not found
    """
    with engine.begin() as conn:
        # Check if conversation exists
        conv_check = conn.execute(
            text("SELECT id FROM conversations WHERE id = :cid"),
            {"cid": conversation_id}
        ).first()
        
        if not conv_check:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Get all messages
        messages = conn.execute(
            text("""
                SELECT id, role, content, created_at, model_provider, model_name, sources
                FROM conversation_messages
                WHERE conversation_id = :cid
                ORDER BY created_at ASC
            """),
            {"cid": conversation_id}
        ).mappings().all()
    
    # Serialize messages
    serializable_messages = []
    for msg in messages:
        msg_dict = dict(msg)
        
        # Convert datetime to ISO format
        if msg_dict.get('created_at'):
            msg_dict['created_at'] = msg_dict['created_at'].isoformat()
        
        # Parse sources JSON
        if msg_dict.get('sources'):
            try:
                msg_dict['sources'] = (
                    json.loads(msg_dict['sources']) 
                    if isinstance(msg_dict['sources'], str) 
                    else msg_dict['sources']
                )
            except (json.JSONDecodeError, TypeError):
                msg_dict['sources'] = []
        else:
            msg_dict['sources'] = None
            
        serializable_messages.append(msg_dict)
    
    return {
        "conversation_id": conversation_id,
        "messages": serializable_messages
    }


def delete_conversation_by_id(conversation_id: int) -> None:
    """
    Delete a conversation and all its messages.
    
    Args:
        conversation_id: The conversation ID to delete
    """
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM conversations WHERE id = :cid"),
            {"cid": conversation_id}
        )
    logger.info("Deleted conversation", conversation_id=conversation_id)
