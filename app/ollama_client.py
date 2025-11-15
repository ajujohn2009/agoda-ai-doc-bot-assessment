import aiohttp
import json

OLLAMA_URL = "http://ollama:11434"

async def stream_ollama_chat(model: str, messages: list):
    """
    Stream chat completion tokens from Ollama.
    Yields: {"type":"delta", "text": "..."}
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        ) as resp:
            async for line in resp.content:
                try:
                    data = json.loads(line.decode().strip())
                    if "message" in data and "content" in data["message"]:
                        yield {"type": "delta", "text": data["message"]["content"]}
                except Exception:
                    continue
