"""
Document management API routes.
Handles document upload, listing, and deletion.
"""
import os
import uuid
import shutil
import tempfile
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy import text as sa_text

from ..db import SessionLocal, engine
from ..text_extraction import read_any, simple_chunks
from ..embedding import embed_texts
from ..logging_config import logger

router = APIRouter(prefix="/api", tags=["documents"])


# ==================== Document Upload ====================

@router.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """
    Upload one or more documents.
    
    Supported formats: PDF, DOCX, TXT
    
    Process:
    1. Save uploaded files to temp directory
    2. Extract text from each file
    3. Split text into chunks
    4. Generate embeddings for chunks
    5. Store in database with vector embeddings
    
    Returns:
        List of uploaded documents with chunk counts
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    inserted = []
    
    with SessionLocal() as db, db.begin():
        for f in files:
            logger.info("Processing file", filename=f.filename, content_type=f.content_type)
            
            # Save to temp & read text
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                shutil.copyfileobj(f.file, tmp)
                tmp_path = tmp.name

            try:
                doc_text, kind = read_any(tmp_path, f.content_type or "", f.filename)
            except Exception as e:
                logger.error("Error extracting text", filename=f.filename, error=str(e))
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to extract text from {f.filename}: {str(e)}"
                )
            finally:
                # Clean up temp file
                try:
                    os.remove(tmp_path)
                except:
                    pass

            if not doc_text.strip():
                logger.warning("Empty document", filename=f.filename)
                # Skip empty docs (no extractable text)
                continue

            # Create document record
            doc_id = str(uuid.uuid4())
            db.execute(
                sa_text("""
                    INSERT INTO documents(id, filename, mime_type, size_bytes)
                    VALUES(:id, :fn, :mt, :sz)
                """),
                {
                    "id": doc_id, 
                    "fn": f.filename, 
                    "mt": f.content_type or "", 
                    "sz": getattr(f, "size", 0) or 0
                },
            )

            # Chunk → embed → insert
            parts = list(simple_chunks(doc_text))
            logger.info("Created chunks", filename=f.filename, chunk_count=len(parts))
            
            vecs = embed_texts(parts)

            for i, (chunk, vec) in enumerate(zip(parts, vecs)):
                db.execute(
                    sa_text("""
                        INSERT INTO chunks(id, document_id, chunk_index, content, embedding)
                        VALUES(:id, :doc, :idx, :content, :emb)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "doc": doc_id,
                        "idx": i,
                        "content": chunk,
                        "emb": vec,
                    },
                )

            inserted.append({
                "document_id": doc_id, 
                "filename": f.filename, 
                "chunks": len(parts)
            })
            
            logger.info("Document uploaded successfully", 
                       filename=f.filename, 
                       doc_id=doc_id, 
                       chunks=len(parts))

    return {"ok": True, "inserted": inserted}


# ==================== Document Listing ====================

@router.get("/documents")
async def list_documents():
    """
    Returns all documents with chunk counts.
    
    Returns:
        List of documents with metadata and chunk statistics
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
    
    documents = [dict(r) for r in rows]
    logger.info("Listed documents", count=len(documents))
    
    return documents


# ==================== Document Deletion ====================

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    Deletes a document and all its chunks (ON DELETE CASCADE).
    
    Args:
        doc_id: The document UUID
        
    Returns:
        Success confirmation with deleted document ID
    """
    with SessionLocal() as db, db.begin():
        # Verify document exists
        res = db.execute(
            sa_text("SELECT 1 FROM documents WHERE id = :id"), 
            {"id": doc_id}
        ).first()
        
        if not res:
            logger.warning("Document not found for deletion", doc_id=doc_id)
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete document → chunks will cascade
        db.execute(
            sa_text("DELETE FROM documents WHERE id = :id"), 
            {"id": doc_id}
        )
        
        logger.info("Document deleted", doc_id=doc_id)

    return {"ok": True, "deleted": doc_id}