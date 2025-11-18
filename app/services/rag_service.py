"""
RAG (Retrieval-Augmented Generation) service.
Handles document retrieval, context building, and streaming responses.
"""
import json
import time
from typing import AsyncGenerator, List, Dict, Optional
from time import perf_counter
from ..schemas import AskBody
from ..services.conversation_service import create_conversation, store_message
from ..services.model_service import resolve_model
from ..retrieval import search_similar
from ..utils.helpers import dedupe_sources as _dedupe_sources
from ..openai_client import client as openai_client
from ..logging_config import logger
from ..db import engine
from sqlalchemy import text


def _has_any_documents() -> bool:
    """Check if there are any documents in the database."""
    with engine.begin() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        return result > 0


async def _classify_question_intent(question: str, provider: str, model_name: str) -> str:
    """
    Use the LLM to classify the question intent.
    Returns: 'greeting', 'help', or 'factual'
    
    This is smarter than hardcoded patterns as it understands context and nuance.
    Works with any language - classifies intent regardless of language.
    """
    classification_prompt = f"""Classify the following user question into ONE category (the question may be in any language):

Categories:
- "greeting": ONLY simple greetings and casual conversation (hello, hi, namaste, salaam, etc.)
- "help": ONLY questions about THIS SYSTEM's capabilities (what can you do, how does this work, etc.)
- "factual": ALL questions seeking information, facts, data, or knowledge about ANY topic

Examples:
- "hello" → greeting
- "namaste" → greeting
- "kaise ho?" (how are you in Hindi) → greeting
- "what can you do?" → help
- "What do you know about X?" → factual (seeking information)
- "X के बारे में क्या जानकारी है?" (what info about X in Hindi) → factual
- "Who is X?" → factual (seeking information)
- "Tell me about X" → factual (seeking information)
- "What are the rules?" → factual (seeking information)

Question: "{question}"

IMPORTANT: If the question is asking about ANY person, place, thing, or topic (not about the system itself), classify it as "factual".
The question can be in any language, but classify the INTENT.

Respond with ONLY ONE WORD: greeting, help, or factual

Classification:"""

    try:
        # Use a quick, single-turn completion for classification
        messages = [{"role": "user", "content": classification_prompt}]
        
        response_text = ""
        if provider == "openai":
            async for delta in _stream_openai(model_name, messages):
                response_text += delta
        else:  # ollama
            async for delta in _stream_ollama(model_name, messages):
                response_text += delta
        
        # Extract classification
        intent = response_text.strip().lower()
        
        # Validate response
        if intent in ['greeting', 'help', 'factual']:
            logger.info("Question classified", question=question[:50], intent=intent)
            return intent
        else:
            # Default to factual if unexpected response
            logger.warning("Unexpected classification", response=intent, defaulting_to="factual")
            return 'factual'
            
    except Exception as e:
        logger.error("Intent classification failed", error=str(e))
        # On error, treat as factual (safer - will search documents)
        return 'factual'


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
    
    # 4. Classify question intent using LLM
    intent = await _classify_question_intent(question, provider, model_name)
    is_greeting_or_help = (intent in ['greeting', 'help'])
    
    # 5. Handle no documents case
    if not _has_any_documents() and not is_greeting_or_help:
        async for event in _stream_no_documents_response(
            chat_id,
            provider,
            model_name,
            history=payload.history
        ):
            yield event
        
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        logger.info("Query completed (no documents uploaded)", time_ms=elapsed_ms)
        return
    
    # 6. Handle greeting/help questions directly
    if is_greeting_or_help:
        # For greetings/help, answer directly without searching documents
        async for event in _stream_greeting_response(
            question,
            chat_id,
            provider,
            model_name,
            history=payload.history
        ):
            yield event
        
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        logger.info("Query completed (greeting/help)", time_ms=elapsed_ms)
        return
    
    # 7. Search for relevant document chunks
    chunks = search_similar(question, top_k=payload.top_k)
    logger.info("Retrieved chunks", count=len(chunks))
    
    strong_chunks = [c for c in chunks if float(c["score"]) >= payload.min_score]
    if not strong_chunks and chunks:
        # If nothing meets threshold, take top 2
        strong_chunks = chunks[:2]

    
    # 8. Handle case with no relevant documents
    if not strong_chunks:
        async for event in _stream_not_found_response(
            chat_id, 
            provider, 
            model_name,
            history=payload.history
        ):
            yield event
        
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        logger.info("Query completed (no relevant documents found)", time_ms=elapsed_ms)
        return
    
    # 9. Build context and stream response
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


async def _stream_greeting_response(
    question: str,
    chat_id: int,
    provider: str,
    model_name: str,
    history: Optional[List[Dict]] = None
) -> AsyncGenerator[str, None]:
    """
    Stream a friendly response for greetings and help questions.
    Uses the LLM to respond naturally without document context.
    
    Args:
        question: The user's question
        chat_id: The conversation ID
        provider: The LLM provider
        model_name: The model name
        history: Optional conversation history
        
    Yields:
        SSE-formatted event strings
    """
    # Send empty sources (no documents needed for greetings)
    meta_event = {"type": "meta", "sources": []}
    yield f"data: {json.dumps(meta_event)}\n\n"
    
    # Build messages for LLM (same prompt as regular RAG but without context)
    system_prompt = (
        "You are a helpful document assistant. You help users understand their uploaded documents.\n\n"
        
        "LANGUAGE REQUIREMENT:\n"
        "- You MUST respond in English ONLY\n"
        "- Even if the user greets you in another language (Hindi, Spanish, etc.), respond in English\n"
        "- Example: User says 'Namaste' → You respond 'Hello! How can I help you?'\n\n"
        
        "The user is asking a greeting or general help question. Respond warmly and explain your capabilities:\n"
        "- You can answer questions about uploaded documents (PDF, DOCX, TXT)\n"
        "- You analyze document content and provide accurate answers\n"
        "- You cite sources from the documents\n"
        "- Users should upload documents first, then ask questions about them\n\n"
        
        "Be friendly and concise. Don't mention technical details.\n"
        "ALWAYS respond in English, regardless of the user's language."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history if provided
    if history:
        for turn in history:
            messages.append({
                "role": turn.role,
                "content": turn.content
            })
    
    # Add current question
    messages.append({
        "role": "user",
        "content": question
    })
    
    logger.info("Answering greeting/help question", question=question)
    
    # Stream response from LLM
    full_response = ""
    
    if provider == "openai":
        async for delta in _stream_openai(model_name, messages):
            full_response += delta
            yield f'data: {json.dumps({"type": "delta", "text": delta})}\n\n'
    else:  # ollama
        async for delta in _stream_ollama(model_name, messages):
            full_response += delta
            yield f'data: {json.dumps({"type": "delta", "text": delta})}\n\n'
    
    # Store assistant message
    timestamp = store_message(
        chat_id,
        "assistant",
        full_response,
        model_provider=provider,
        model_name=model_name,
        sources=[]
    )
    
    # Send final event
    final_event = {
        "type": "final",
        "text": full_response,
        "grounded": False,  # Not grounded in documents
        "sources": [],
        "model_provider": provider,
        "model_name": model_name,
        "conversation_id": chat_id,
        "timestamp": timestamp.isoformat() if timestamp else None,
    }
    yield f"data: {json.dumps(final_event)}\n\n"
    yield 'data: {"type":"done"}\n\n'


async def _stream_no_documents_response(
    chat_id: int,
    provider: str,
    model_name: str,
    history: Optional[List[Dict]] = None
) -> AsyncGenerator[str, None]:
    """
    Stream a response when no documents have been uploaded yet.
    
    Args:
        chat_id: The conversation ID
        provider: The LLM provider
        model_name: The model name
        history: Optional conversation history
        
    Yields:
        SSE-formatted event strings
    """
    no_docs_message = (
        "Please upload documents first before asking questions. "
        "Go to the 'Documents' tab to upload PDF, DOCX, or TXT files."
    )
    
    # Send empty sources
    meta_event = {"type": "meta", "sources": []}
    yield f"data: {json.dumps(meta_event)}\n\n"
    
    # Store assistant message
    timestamp = store_message(
        chat_id, 
        "assistant", 
        no_docs_message,
        model_provider=provider,
        model_name=model_name,
        sources=[]
    )
    
    # Send final event
    final_event = {
        "type": "final",
        "text": no_docs_message,
        "grounded": False,
        "sources": [],
        "model_provider": provider,
        "model_name": model_name,
        "conversation_id": chat_id,
        "timestamp": timestamp.isoformat() if timestamp else None,
    }
    yield f"data: {json.dumps(final_event)}\n\n"
    yield 'data: {"type":"done"}\n\n'


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
        """
            You are a strict Document Grounding Assistant.

            Your job is to answer ONLY using the information found in the CONTEXT provided below.

            You MUST follow these rules:

            1. Use ONLY the text from the CONTEXT. 
            - Do NOT add examples, do NOT guess, do NOT include general knowledge.
            - If the user asks something that is not explicitly in the CONTEXT, answer:
                "I don't have information about that in the uploaded documents."

            2. When answering:
            - First QUOTE the exact sentence(s) from the CONTEXT that support your answer.
            - Then give a SHORT summary in your own words.
            This prevents hallucination.

            3. If the CONTEXT contains partial information:
            - Only summarize what IS present.
            - Do NOT expand the answer with assumptions.

            4. If the answer requires a list:
            - Only list items that appear EXACTLY in the CONTEXT.
            - Never invent items (e.g., Visa, PayPal, etc.) unless they appear verbatim.

            5. Respond ONLY in English.

            6. If the CONTEXT is irrelevant to the question:
            - Say: "I don't have information about that in the uploaded documents."

            7. Never use ANY external knowledge, even if the answer is obvious.

            Your format MUST be:

            <your summary>

            If no evidence exists, return:
            "I don't have information about that in the uploaded documents."
        """
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    t = perf_counter()
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
    logger.info("Received response from LLM in %.2f seconds", perf_counter() - t)
    logger.info("model used -> %s", model_name)
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
    logger.info("Sent request to OpenAI API")
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
    logger.info("Sent request to Ollama model")
    async for delta_event in stream_ollama_chat(model_name, messages):
        if delta_event.get("type") == "delta":
            yield delta_event["text"]