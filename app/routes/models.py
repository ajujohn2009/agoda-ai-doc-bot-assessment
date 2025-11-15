"""
Model-related API routes.
Handles listing available LLM models.
"""
from fastapi import APIRouter
from ..services.model_service import get_available_models

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
async def list_available_models():
    """
    Return all supported LLM models grouped by provider.
    
    Example response:
    {
        "openai": ["gpt-4o-mini"],
        "ollama": ["qwen2.5:7b"]
    }
    """
    return get_available_models()
