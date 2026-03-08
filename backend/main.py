import asyncio
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from datetime import datetime, timezone

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
            now = datetime.now(timezone.utc)
            for t in stale:
                done = t.completed_actions + t.failed_actions
                if done >= t.total_actions:
                    # All actions were processed before crash — mark completed
                    t.status = "completed"
                    t.completed_at = now
                elif done > 0:
                    # Partially done — mark cancelled (can't resume connections)
                    t.status = "cancelled"
                    t.completed_at = now
                    t.last_error = "Interrupted by app restart"
                else:
                    # Not started yet — back to pending
                    t.status = "pending"
            db.commit()
            print(f"[Backend] Reset {len(stale)} stale running tasks")
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
    reload_enabled = os.getenv("NEXUS_BACKEND_RELOAD", "0") == "1"
    if reload_enabled:
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info"
        )
    else:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            reload=False,
            log_level="info"
        )
