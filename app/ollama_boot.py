# app/ollama_boot.py
import os
import time
import json
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
DEFAULT_MODELS = [m.strip() for m in os.getenv("OLLAMA_DEFAULT_MODELS", "qwen2.5:7b").split(",")]

def _ollama_up(timeout_sec: int = 60) -> bool:
    """Wait until Ollama /api/tags is reachable (up to timeout_sec)."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            if r.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(1.0)
    return False

def _has_model(name: str) -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        tags = r.json().get("models", [])
        return any((m.get("name") or "").startswith(name) for m in tags)
    except requests.RequestException:
        return False

def _pull_model(name: str):
    """
    Ask Ollama to pull the model. Use non-streaming to avoid fiddly timeouts.
    Blocks until Ollama reports success (for the pull request itself).
    """
    r = requests.post(
        f"{OLLAMA_URL}/api/pull",
        json={"name": name, "stream": False},
        timeout=600  # 10 min; adjust if you expect cold pulls to take longer
    )
    r.raise_for_status()
    # Response is a single JSON obj like {"status":"success", ...} when stream=False.
    # We don't need to parse fields here; if it didn't raise, it's fine.

def ensure_ollama_models():
    # 1) Ensure Ollama is reachable (don’t crash app if not)
    if not _ollama_up(timeout_sec=90):
        print("[ollama_boot] Ollama not reachable; skipping model pre-pull.")
        return

    # 2) Ensure each requested model is present
    for model in DEFAULT_MODELS:
        if _has_model(model):
            continue
        print(f"[ollama_boot] Pulling missing model: {model}")
        try:
            _pull_model(model)
        except requests.RequestException as e:
            print(f"[ollama_boot] Failed to pull {model}: {e}")
            # Don't raise — let the API start; first use can still trigger auto-pull by Ollama.
