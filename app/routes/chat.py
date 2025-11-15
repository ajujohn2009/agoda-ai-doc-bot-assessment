"""
Chat-related API routes.
Handles conversation management and RAG question answering.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from ..schemas import AskBody
from ..services.conversation_service import (
    get_conversation_by_id,
    delete_conversation_by_id
)
from ..services.rag_service import handle_rag_query
from ..logging_config import logger

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """
    Retrieve all messages from a conversation.
    Returns messages in chronological order.
    """
    try:
        conversation_data = get_conversation_by_id(conversation_id)
        return JSONResponse(conversation_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error fetching conversation", exc_info=e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int):
    """Delete a conversation and all its messages."""
    try:
        delete_conversation_by_id(conversation_id)
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error("Error deleting conversation", exc_info=e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ask_stream")
async def ask_rag_stream(payload: AskBody):
    """
    Streaming RAG endpoint using Server-Sent Events (SSE).
    
    Workflow:
    1. Resolve model/provider
    2. Create/retrieve conversation
    3. Store user message
    4. Retrieve relevant document chunks
    5. Build context and stream LLM response
    6. Store assistant message
    """
    try:
        # handle_rag_query returns an async generator, don't await it
        return StreamingResponse(
            handle_rag_query(payload),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error("Error in RAG streaming", exc_info=e, question=payload.question)
        raise HTTPException(status_code=500, detail="Error processing query")