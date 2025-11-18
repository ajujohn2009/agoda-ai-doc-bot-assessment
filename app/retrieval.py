from typing import List, Dict
from sqlalchemy import text as sa_text
from .db import engine
from time import perf_counter
from .embedding import embed_texts
from .logging_config import logger

def search_similar(query: str, top_k: int = 5) -> List[Dict]:
    """
        Search for similar chunks in the database.

        Parameters:
        query (str): The query string to search for.
        top_k (int): The number of top similar chunks to return. Defaults to 5.

        Returns:
        List[Dict]: A list of dictionaries containing the similar chunks.
    """
    qv = embed_texts([query])[0]
    t = perf_counter()
    
    with engine.begin() as conn:
        rows = conn.execute(
            sa_text("""
                SELECT
                    c.id,
                    c.document_id,
                    d.filename,
                    c.chunk_index,
                    c.content,
                    1 - (c.embedding <=> (:qv)::vector) AS score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                ORDER BY c.embedding <-> (:qv)::vector
                LIMIT :k
            """),
            {"qv": qv, "k": top_k},
        ).mappings().all()
    logger.info('''Search for similar chunks in %.2f ms''', (perf_counter() - t) * 1000)
    return [dict(r) for r in rows]
