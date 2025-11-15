from typing import List, Dict
from fastapi import APIRouter, HTTPException
from sqlalchemy import text as sa_text

from .db import engine, SessionLocal

router = APIRouter(prefix="/api", tags=["documents"])

@router.get("/documents")
def list_documents() -> List[Dict]:
    """
    Returns all documents with chunk counts.
    """
    with engine.begin() as conn:
        rows = conn.execute(sa_text("""
            SELECT d.id,
                   d.filename,
                   d.mime_type,
                   d.size_bytes,
                   d.uploaded_at,
                   COALESCE(COUNT(c.id), 0) AS num_chunks
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            GROUP BY d.id
            ORDER BY d.uploaded_at DESC
        """)).mappings().all()
    return [dict(r) for r in rows]


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    """
    Deletes a document and all its chunks (ON DELETE CASCADE).
    """
    with SessionLocal() as db, db.begin():
        # verify document exists
        res = db.execute(sa_text("SELECT 1 FROM documents WHERE id = :id"), {"id": doc_id}).first()
        if not res:
            raise HTTPException(status_code=404, detail="Document not found")

        # delete document → chunks will cascade
        db.execute(sa_text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})

    return {"ok": True, "deleted": doc_id}
