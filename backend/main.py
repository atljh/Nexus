import asyncio
import os
import sys
import traceback
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from datetime import datetime, timezone

from database.database import init_db, SessionLocal
from api.router import api_router
from utils.logging_config import setup_logging
from utils.task_recovery import reconcile_stale_active_tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log_file = setup_logging()
    print(f"[Backend] File logging: {log_file}")

    await init_db()
    print("[Backend] Database initialized")

    # Reset stale running/paused tasks (queue is in-memory and cannot survive restart)
    db = SessionLocal()
    try:
        recovered = reconcile_stale_active_tasks(db, now=datetime.now(timezone.utc))
        if recovered:
            print(f"[Backend] Reconciled {recovered} stale active tasks")
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

# Middleware to catch errors at ASGI level (before FastAPI handlers)
# This ensures errors during multipart parsing are logged and get CORS headers
@app.middleware("http")
async def catch_all_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        print(f"[Backend ERROR] {request.method} {request.url}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        return JSONResponse(status_code=500, content={"detail": str(exc)})


# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# API routes
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    reload_enabled = os.getenv("NEXUS_BACKEND_RELOAD", "0") == "1"
    # On Windows, reload=True spawns a subprocess that silently swallows
    # exceptions (e.g. multipart parsing errors), so we disable it.
    is_windows = sys.platform == "win32"
    if reload_enabled and not is_windows:
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
