from sqlalchemy import Column, String, Text, Integer, ForeignKey, BigInteger, TIMESTAMP, text
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    filename = Column(Text, nullable=False)
    mime_type = Column(Text)
    size_bytes = Column(BigInteger)
    uploaded_at = Column(TIMESTAMP(timezone=True), server_default=text("NOW()"))

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
