import os, uuid, shutil, tempfile
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy import text as sa_text

from .db import SessionLocal
from .text_extraction import read_any, simple_chunks
from .embedding import embed_texts

router = APIRouter(prefix="/api", tags=["documents"])

#Upload File Limit
MAX_FILES_PER_UPLOAD = 5
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 5 MB per file

@router.post("/documents/upload")
async def upload(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    #Check number of files
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {MAX_FILES_PER_UPLOAD} files per upload."
        )

    inserted = []
    with SessionLocal() as db, db.begin():
        for f in files:
            #Check file size before reading
            try:
                f.file.seek(0, os.SEEK_END)
                size_bytes = f.file.tell()
                f.file.seek(0)  # reset for later reading
            except Exception:
                size_bytes = 0 ## forcing to throw error

            if size_bytes > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"File '{f.filename}' is too large. "
                        f"Max size is {MAX_FILE_SIZE_BYTES // (1024*1024)} MB."
                    ),
                )

            # save to temp & read text
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                shutil.copyfileobj(f.file, tmp)
                tmp_path = tmp.name

            try:
                doc_text, kind = read_any(tmp_path, f.content_type or "", f.filename)
            finally:
                try:
                    os.remove(tmp_path)
                except:
                    pass

            if not doc_text.strip():
                # skip empty docs (no extractable text)
                continue

            doc_id = str(uuid.uuid4())
            db.execute(
                sa_text("""
                    INSERT INTO documents(id, filename, mime_type, size_bytes)
                    VALUES(:id, :fn, :mt, :sz)
                """),
                {"id": doc_id, "fn": f.filename, "mt": f.content_type or "", "sz": getattr(f, "size", 0) or 0},
            )

            # chunk → embed → insert
            parts = list(simple_chunks(doc_text))
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

            inserted.append({"document_id": doc_id, "filename": f.filename, "chunks": len(parts)})

    return {"ok": True, "inserted": inserted}
