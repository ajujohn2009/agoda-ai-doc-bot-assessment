import os
from typing import List
import numpy as np

# Default: local sentence-transformers to avoid extra API usage
_EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_EMBED_MODEL)
    return _model

def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    if isinstance(vecs, np.ndarray):
        return vecs.tolist()
    return [v for v in vecs]
