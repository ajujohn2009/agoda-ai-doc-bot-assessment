"""
Main FastAPI application entry point.
Responsibilities: App setup, router registration, startup/shutdown hooks.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import chat, models
from .documents import router as docs_router
from .upload import router as upload_router
from .db.migrations import run_sql_migrations
from .ollama_boot import ensure_ollama_models
from .embedding import preload_model
from .logging_config import logger

# -------------------------------------------------
# App setup
# -------------------------------------------------

app = FastAPI(title="Docs Chat", version="0.5.0")

# Register routers
app.include_router(chat.router)
app.include_router(upload_router)
app.include_router(docs_router)
app.include_router(models.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database and Ollama models on startup."""
    try:
        logger.info("Running database migrations...")
        run_sql_migrations()
        logger.info("Database migrations completed")

        logger.info("Preloading embedding model...")
        preload_model()
        logger.info("Embedding model ready")
        
        logger.info("Ensuring Ollama models are available...")
        await ensure_ollama_models()
        logger.info("Ollama models ready")
        
    except Exception as e:
        logger.error("Startup initialization error", exc_info=e)
        # Continue anyway - app might still be usable


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Application shutting down")


# Static files last (so they don't swallow /api/* routes)
app.mount("/", StaticFiles(directory="web", html=True), name="web")
