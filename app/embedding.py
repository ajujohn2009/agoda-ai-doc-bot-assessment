import os
from typing import List
import numpy as np
import warnings

# Default: local sentence-transformers to avoid extra API usage
_EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_model = None

def preload_model():
    """Preload the embedding model on startup to avoid first-request delay."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"Loading embedding model: {_EMBED_MODEL}...")
        
        # Load model with explicit tokenizer settings to avoid FutureWarning
        _model = SentenceTransformer(
            _EMBED_MODEL,
            tokenizer_kwargs={'clean_up_tokenization_spaces': False}
        )
        
        # Warm up with a test embedding
        _model.encode(["test"], normalize_embeddings=True, show_progress_bar=False)
        print(f"Embedding model loaded: {_EMBED_MODEL}")
    return _model

def get_model():
    global _model
    if _model is None:
        preload_model()
    return _model

def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    if isinstance(vecs, np.ndarray):
        return vecs.tolist()
    return [v for v in vecs]