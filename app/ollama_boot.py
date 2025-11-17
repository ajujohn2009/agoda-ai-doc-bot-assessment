# app/ollama_boot.py
import os
import time
import asyncio
import aiohttp

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
DEFAULT_MODELS = [m.strip() for m in os.getenv("OLLAMA_DEFAULT_MODELS", "qwen2.5:7b").split(",")]

async def _ollama_up(timeout_sec: int = 60) -> bool:
    """Wait until Ollama /api/tags is reachable (up to timeout_sec)."""
    deadline = time.time() + timeout_sec
    async with aiohttp.ClientSession() as session:
        while time.time() < deadline:
            try:
                async with session.get(f"{OLLAMA_URL}/api/tags", timeout=aiohttp.ClientTimeout(total=3)) as r:
                    if r.ok:
                        return True
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(1.0)
    return False

async def _has_model(name: str) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_URL}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as r:
                r.raise_for_status()
                data = await r.json()
                tags = data.get("models", [])
                return any((m.get("name") or "").startswith(name) for m in tags)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False

async def _pull_model(name: str):
    """
    Ask Ollama to pull the model. Use non-streaming to avoid fiddly timeouts.
    Blocks until Ollama reports success (for the pull request itself).
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{OLLAMA_URL}/api/pull",
            json={"name": name, "stream": False},
            timeout=aiohttp.ClientTimeout(total=600)  # 10 min
        ) as r:
            r.raise_for_status()

async def ensure_ollama_models():
    """Async function to ensure Ollama models are available."""
    # 1) Ensure Ollama is reachable (don't crash app if not)
    if not await _ollama_up(timeout_sec=90):
        print("[ollama_boot] Ollama not reachable; skipping model pre-pull.")
        return

    # 2) Ensure each requested model is present
    for model in DEFAULT_MODELS:
        if await _has_model(model):
            continue
        print(f"[ollama_boot] Pulling missing model: {model}")
        try:
            await _pull_model(model)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"[ollama_boot] Failed to pull {model}: {e}")
            # Don't raise — let the API start; first use can still trigger auto-pull by Ollama.


async def print_ollama_download_progress():
    """
    Monitor and print Ollama download progress in real-time.
    
    Usage:
        # Start monitoring in background task
        import asyncio
        asyncio.create_task(print_ollama_download_progress())
    """
    print("[ollama_progress] 📊 Starting download monitor...")
    
    last_status = {}
    consecutive_empty = 0
    max_consecutive_empty = 10  # Stop after 10 consecutive empty responses
    
    async with aiohttp.ClientSession() as session:
        while consecutive_empty < max_consecutive_empty:
            try:
                # Check for running processes (downloads, etc.)
                async with session.get(f"{OLLAMA_URL}/api/ps", timeout=aiohttp.ClientTimeout(total=3)) as r:
                    if r.ok:
                        data = await r.json()
                        models = data.get("models", [])
                        
                        if not models:
                            consecutive_empty += 1
                            await asyncio.sleep(2)
                            continue
                        
                        # Reset counter if we found something
                        consecutive_empty = 0
                        
                        # Print status for each model
                        for model_info in models:
                            model_name = model_info.get("name", "unknown")
                            size_vram = model_info.get("size_vram", 0)
                            
                            # Convert to MB for readability
                            size_mb = size_vram / (1024 * 1024)
                            
                            status_key = f"{model_name}"
                            current_status = f"Loading: {size_mb:.1f} MB"
                            
                            # Only print if status changed
                            if last_status.get(status_key) != current_status:
                                print(f"[ollama_progress] {model_name}: {current_status}")
                                last_status[status_key] = current_status
                                
                    else:
                        consecutive_empty += 1
                        
            except (aiohttp.ClientError, asyncio.TimeoutError):
                # Ollama might not be ready yet
                consecutive_empty += 1
                
            await asyncio.sleep(2)  # Check every 2 seconds
    
    print("[ollama_progress] ✅ Monitoring complete")