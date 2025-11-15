"""
Utility helper functions.
"""
from typing import List, Dict


def dedupe_sources(chunks: List[Dict]) -> List[Dict]:
    """
    Deduplicate source documents from retrieved chunks.
    
    For each unique filename, keeps the highest scoring chunk and includes
    a preview of the content that was used.
    Returns sources sorted by score (descending).
    
    Args:
        chunks: List of chunks with 'filename', 'score', and 'content' keys
        
    Returns:
        List of deduplicated sources with filename, score, and content preview
        
    Example:
        >>> chunks = [
        ...     {"filename": "doc1.txt", "score": 0.8, "content": "Long text..."},
        ...     {"filename": "doc1.txt", "score": 0.6, "content": "Other text..."},
        ...     {"filename": "doc2.txt", "score": 0.7, "content": "More text..."}
        ... ]
        >>> dedupe_sources(chunks)
        [
            {"filename": "doc1.txt", "score": 0.8, "preview": "Long text..."},
            {"filename": "doc2.txt", "score": 0.7, "preview": "More text..."}
        ]
    """
    source_map = {}
    
    for chunk in chunks:
        filename = chunk["filename"]
        score = float(chunk["score"])
        content = chunk.get("content", "")
        
        # Keep highest score for each filename along with its content
        if filename not in source_map or score > source_map[filename]["score"]:
            source_map[filename] = {
                "score": score,
                "content": content
            }
    
    # Convert to list and sort by score (descending)
    sources = []
    for fname, data in sorted(source_map.items(), key=lambda x: x[1]["score"], reverse=True):
        # Create preview (first 200 chars)
        preview = data["content"][:200].strip()
        if len(data["content"]) > 200:
            preview += "..."
        
        sources.append({
            "filename": fname,
            "score": round(data["score"], 3),
            "preview": preview
        })
    
    return sources