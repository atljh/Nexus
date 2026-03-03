import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database.database import init_db, SessionLocal
from database.models import Task
from api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    print("[Backend] Database initialized")

    # Reset stale running tasks (lost after restart)
    db = SessionLocal()
    try:
        stale = db.query(Task).filter(Task.status == "running").all()
        if stale:
            for t in stale:
                t.status = "pending"
            db.commit()
            print(f"[Backend] Reset {len(stale)} stale running tasks to pending")
    finally:
        db.close()

    yield
    # Shutdown
    print("[Backend] Shutting down")


app = FastAPI(
    title="Nexus Backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for Electron - restricted to local origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",    # Vite dev server
        "http://127.0.0.1:5173",    # Vite dev server alternative
        "app://.",                   # Electron production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# API routes
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
