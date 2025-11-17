from typing import List, Dict
from sqlalchemy import text as sa_text
from .db import engine
from time import perf_counter
from .embedding import embed_texts
from .logging_config import logger
def search_similar(query: str, top_k: int = 5) -> List[Dict]:
    qv = embed_texts([query])[0]  # list[float], len should match your column dim (e.g., 384)
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
    # print(rows)
    logger.info('''Search for similar chunks in %.2f ms''', (perf_counter() - t) * 1000)
    return [dict(r) for r in rows]
