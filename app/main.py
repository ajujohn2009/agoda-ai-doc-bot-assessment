
from __future__ import annotations
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

app = FastAPI(title="Agoda Assesment", version="0.1.0")


@app.get("/api/health")
async def health():
    return JSONResponse({"status": "ok"})

# Serve the static frontend
app.mount("/", StaticFiles(directory="web", html=True), name="web")
