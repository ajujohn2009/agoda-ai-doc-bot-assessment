"""
RAG (Retrieval-Augmented Generation) service.
Handles document retrieval, context building, and streaming responses.
"""
import json
import time
from typing import AsyncGenerator, List, Dict, Optional

from ..schemas import AskBody
from ..services.conversation_service import create_conversation, store_message
from ..services.model_service import resolve_model
from ..retrieval import search_similar
from ..utils.helpers import dedupe_sources as _dedupe_sources
from ..openai_client import client as openai_client
from ..logging_config import logger


async def handle_rag_query(payload: AskBody) -> AsyncGenerator[str, None]:
    """
    Main RAG query handler that orchestrates the entire flow.
    
    Args:
        payload: The request payload containing question and parameters
        
    Yields:
        SSE-formatted strings for streaming to client
    """
    start_time = time.time()
    question = payload.question.strip()
    
    # 1. Resolve model/provider
    provider, model_name = resolve_model(payload.model)
    logger.info("Processing query", question=question, provider=provider, model=model_name)
    
    # 2. Ensure conversation exists
    chat_id = payload.chat_id
    if chat_id is None:
        chat_id = create_conversation()
    
    # 3. Store user message
    store_message(chat_id, "user", question)
    
    # 4. Retrieve relevant chunks
    chunks = search_similar(question, top_k=payload.top_k)
    logger.info("Retrieved chunks", count=len(chunks))
    
    strong_chunks = [c for c in chunks if float(c["score"]) >= payload.min_score]
    if not strong_chunks and chunks:
        # If nothing meets threshold, take top 2
        strong_chunks = chunks[:2]
    
    # 5. Handle case with no relevant documents
    if not strong_chunks:
        async for event in _stream_not_found_response(
            chat_id, 
            provider, 
            model_name,
            history=payload.history
        ):
            yield event
        
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        logger.info("Query completed (no documents found)", time_ms=elapsed_ms)
        return
    
    # 6. Build context and stream response
    # Sort and take top chunks for context
    sorted_chunks = sorted(strong_chunks, key=lambda c: c["score"], reverse=True)[:5]
    
    # Filter to only show sources from relevant chunks (score >= 0.30)
    # This prevents showing completely irrelevant documents in sources
    relevant_chunks = [c for c in sorted_chunks if float(c["score"]) >= 0.30]
    
    # If no chunks meet threshold, don't show sources at all
    # Better to say "I don't have information" than show irrelevant sources
    if not relevant_chunks:
        logger.info("No chunks met relevance threshold", 
                   min_threshold=0.30,
                   best_score=sorted_chunks[0]["score"] if sorted_chunks else None)
    
    # Debug logging
    logger.info(
        "Selected chunks for context",
        total_strong_chunks=len(strong_chunks),
        used_chunks=len(sorted_chunks),
        chunk_files=[c.get("filename") for c in sorted_chunks],
        relevant_for_sources=len(relevant_chunks)
    )
    
    # Only show sources from highly relevant chunks
    sources = _dedupe_sources(relevant_chunks)
    logger.info("Deduplicated sources", sources=sources)
    
    context = _build_context(sorted_chunks)
    
    async for event in _stream_rag_response(
        question=question,
        context=context,
        sources=sources,
        chat_id=chat_id,
        provider=provider,
        model_name=model_name,
        history=payload.history  # Pass conversation history
    ):
        yield event
    
    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    logger.info("Query completed", time_ms=elapsed_ms)


def _build_context(chunks: List[Dict]) -> str:
    """
    Build context string from document chunks.
    
    Args:
        chunks: List of document chunks with content and scores (already sorted and limited)
        
    Returns:
        Formatted context string
    """
    # Build numbered context from provided chunks
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        content = chunk["content"][:800]  # Limit to 800 chars per chunk
        context_parts.append(f"[{i}] {content}")
    
    return "\n\n---\n\n".join(context_parts)


async def _stream_not_found_response(
    chat_id: int,
    provider: str,
    model_name: str,
    history: Optional[List[Dict]] = None
) -> AsyncGenerator[str, None]:
    """
    Stream a 'not found' response when no relevant documents exist.
    
    Args:
        chat_id: The conversation ID
        provider: The LLM provider
        model_name: The model name
        history: Optional conversation history
        
    Yields:
        SSE-formatted event strings
    """
    no_info_message = (
        "I don't have information about that in the uploaded documents. "
        "Try asking a more specific question, or upload relevant documents first."
    )
    
    # Send empty sources
    meta_event = {"type": "meta", "sources": []}
    yield f"data: {json.dumps(meta_event)}\n\n"
    
    # Store assistant message
    timestamp = store_message(
        chat_id, 
        "assistant", 
        no_info_message,
        model_provider=provider,
        model_name=model_name,
        sources=[]
    )
    
    # Send final event
    final_event = {
        "type": "final",
        "text": no_info_message,
        "grounded": False,
        "sources": [],
        "model_provider": provider,
        "model_name": model_name,
        "conversation_id": chat_id,
        "timestamp": timestamp.isoformat() if timestamp else None,
    }
    yield f"data: {json.dumps(final_event)}\n\n"
    yield 'data: {"type":"done"}\n\n'


async def _stream_rag_response(
    question: str,
    context: str,
    sources: List[Dict],
    chat_id: int,
    provider: str,
    model_name: str,
    history: Optional[List[Dict]] = None
) -> AsyncGenerator[str, None]:
    """
    Stream a RAG response with context from retrieved documents.
    
    Args:
        question: The user's question
        context: The built context from retrieved chunks
        sources: List of source documents
        chat_id: The conversation ID
        provider: The LLM provider
        model_name: The model name
        history: Optional conversation history (list of {role, content} dicts)
        
    Yields:
        SSE-formatted event strings
    """
    # Send sources metadata first
    meta_event = {"type": "meta", "sources": sources}
    yield f"data: {json.dumps(meta_event)}\n\n"
    
    # Build messages for LLM
    system_prompt = (
        "You are a helpful document assistant. You help users understand their uploaded documents.\n\n"
        
        "HOW TO RESPOND:\n\n"
        
        "1. GREETINGS & GENERAL QUESTIONS:\n"
        "   - Be friendly and helpful for: greetings, how are you, what can you do, etc.\n"
        "   - Example: \"Hello! I'm your document assistant. I can help you understand "
        "and extract information from your uploaded documents.\"\n\n"
        
        "2. FACTUAL/INFORMATION QUESTIONS:\n"
        "   - Use ONLY information from the PROVIDED CONTEXT below\n"
        "   - For questions about facts, names, dates, rules: answer ONLY if explicitly in the CONTEXT\n"
        "   - For analysis/opinion questions (who is best, what do you think): analyze the data in the CONTEXT\n"
        "   - Example: If asked 'who is the best captain' and CONTEXT has captain statistics, "
        "analyze the stats and provide an informed answer based on the data\n"
        "   - If the CONTEXT has relevant data, USE IT even for opinion questions\n"
        "   - ONLY say 'I don't have information' if the CONTEXT is completely unrelated to the question\n\n"
        
        "3. FOLLOW-UP QUESTIONS:\n"
        "   - Use conversation history to understand context\n"
        "   - If user says 'tell me more', refer to previous discussion\n\n"
        
        "IMPORTANT: If the CONTEXT contains relevant information, always use it to answer, "
        "even if the question requires some interpretation or analysis of the data.\n"
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history if provided
    if history:
        for turn in history:
            messages.append({
                "role": turn.role,      # Access as object attribute, not dict
                "content": turn.content  # Access as object attribute, not dict
            })
    
    # Add current question with context
    messages.append({
        "role": "user", 
        "content": f"QUESTION: {question}\n\nCONTEXT:\n{context}"
    })
    
    logger.info("Sending to LLM", 
                question=question,
                context_length=len(context),
                context_preview=context[:200] + "..." if len(context) > 200 else context,
                history_turns=len(history) if history else 0,
                sources_count=len(sources))
    
    # Stream response from LLM
    full_response = ""
    
    if provider == "openai":
        async for delta in _stream_openai(model_name, messages):
            full_response += delta
            yield f'data: {json.dumps({"type": "delta", "text": delta})}\n\n'
            
    elif provider == "ollama":
        async for delta in _stream_ollama(model_name, messages):
            full_response += delta
            yield f'data: {json.dumps({"type": "delta", "text": delta})}\n\n'
    
    # Store assistant message
    timestamp = store_message(
        chat_id,
        "assistant",
        full_response.strip(),
        model_provider=provider,
        model_name=model_name,
        sources=sources
    )
    
    # Send final event
    final_event = {
        "type": "final",
        "text": full_response.strip(),
        "grounded": True,
        "sources": sources,
        "model_provider": provider,
        "model_name": model_name,
        "conversation_id": chat_id,
        "timestamp": timestamp.isoformat() if timestamp else None,
    }
    yield f"data: {json.dumps(final_event)}\n\n"
    yield 'data: {"type":"done"}\n\n'


async def _stream_openai(model_name: str, messages: List[Dict]) -> AsyncGenerator[str, None]:
    """
    Stream responses from OpenAI API.
    
    Args:
        model_name: The OpenAI model to use
        messages: The conversation messages
        
    Yields:
        Text deltas from the streaming response
    """
    stream_response = openai_client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0.2,
        stream=True,
    )
    
    for chunk in stream_response:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta


async def _stream_ollama(model_name: str, messages: List[Dict]) -> AsyncGenerator[str, None]:
    """
    Stream responses from Ollama API.
    
    Args:
        model_name: The Ollama model to use
        messages: The conversation messages
        
    Yields:
        Text deltas from the streaming response
    """
    from ..ollama_client import stream_ollama_chat
    
    async for delta_event in stream_ollama_chat(model_name, messages):
        if delta_event.get("type") == "delta":
            yield delta_event["text"]