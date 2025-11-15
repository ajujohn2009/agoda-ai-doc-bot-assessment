"""
Model service for LLM provider management.
Handles model resolution and listing available models.
"""
from typing import Tuple, Dict, List
from ..openai_client import MODEL as DEFAULT_OPENAI_MODEL

# Model registry
AVAILABLE_MODELS = {
    "openai": ["gpt-4o-mini"],
    "ollama": ["qwen2.5:7b"],
}


def get_available_models() -> Dict[str, List[str]]:
    """
    Get all available models grouped by provider.
    
    Returns:
        Dictionary with provider names as keys and model lists as values
    """
    return AVAILABLE_MODELS


def resolve_model(model_string: str = None) -> Tuple[str, str]:
    """
    Resolve a model string to provider and model name.
    
    Args:
        model_string: Format "provider:model_name" (e.g., "openai:gpt-4o-mini")
                     or None for default
    
    Returns:
        Tuple of (provider, model_name)
        
    Examples:
        >>> resolve_model("openai:gpt-4o-mini")
        ("openai", "gpt-4o-mini")
        
        >>> resolve_model("ollama:qwen2.5:7b")
        ("ollama", "qwen2.5:7b")
        
        >>> resolve_model(None)
        ("openai", "gpt-4o-mini")  # defaults
    """
    if not model_string:
        return "openai", DEFAULT_OPENAI_MODEL
    
    if model_string.startswith("openai:"):
        provider = "openai"
        model_name = model_string.replace("openai:", "")
    elif model_string.startswith("ollama:"):
        provider = "ollama"
        model_name = model_string.replace("ollama:", "")
    else:
        # Fallback to default if format is unexpected
        return "openai", DEFAULT_OPENAI_MODEL
    
    return provider, model_name


def validate_model(provider: str, model_name: str) -> bool:
    """
    Check if a model is available in the registry.
    
    Args:
        provider: The provider name (e.g., "openai", "ollama")
        model_name: The model name
        
    Returns:
        True if model is available, False otherwise
    """
    return (
        provider in AVAILABLE_MODELS 
        and model_name in AVAILABLE_MODELS[provider]
    )
