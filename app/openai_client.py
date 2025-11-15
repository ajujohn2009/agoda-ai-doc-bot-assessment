import os
from dotenv import load_dotenv

load_dotenv()  # loads .env in local dev; no effect in Docker if env vars provided

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not _OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set. Put it in env or .env (server-side only).")

from openai import OpenAI
client = OpenAI(api_key=_OPENAI_API_KEY)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
