"""
Pydantic schemas for request/response validation.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class ChatTurn(BaseModel):
    """Represents a single turn in a conversation."""
    role: Role
    content: str


class AskBody(BaseModel):
    """Request body for asking questions."""
    question: str = Field(..., min_length=1, description="The question to ask")
    history: Optional[List[ChatTurn]] = Field(None, description="Previous conversation turns")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")
    min_score: float = Field(0.15, ge=0.0, le=1.0, description="Minimum similarity score")
    model: Optional[str] = Field(None, description="Model identifier: 'openai:gpt-4o-mini' or 'ollama:qwen2.5:7b'")
    chat_id: Optional[int] = Field(None, description="Existing conversation ID or None for new conversation")


class Source(BaseModel):
    """Represents a source document used in RAG."""
    filename: str
    score: float
