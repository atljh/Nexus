import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_configured = False


def _resolve_log_dir() -> Path:
    override = os.getenv("NEXUS_LOG_DIR")
    if override:
        return Path(override).expanduser()

    db_path_env = os.getenv("NEXUS_DB_PATH")
    if db_path_env:
        return Path(db_path_env).expanduser().parent / "logs"

    return Path.home() / "Nexus" / "logs"


def setup_logging(log_dir: Optional[Path] = None) -> Path:
    """Attach a rotating file handler to the root logger.

    Writes everything at DEBUG level to ~/Nexus/logs/nexus.log (10 MB × 5 files).
    Console handlers managed by uvicorn are left untouched so stdout noise
    stays at INFO while the file captures the full diagnostic trail.
    """
    global _configured

    directory = Path(log_dir) if log_dir else _resolve_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / "nexus.log"

    if _configured:
        return log_file

    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    handler.set_name("nexus_file")

    root = logging.getLogger()
    if root.level > logging.DEBUG or root.level == logging.NOTSET:
        root.setLevel(logging.DEBUG)

    for existing in root.handlers:
        if existing.get_name() == "nexus_file":
            root.removeHandler(existing)
    root.addHandler(handler)

    # Throttle third-party libraries that emit megabytes of DEBUG per task.
    for noisy in ("telethon", "httpx", "httpcore", "urllib3", "asyncio", "aiosqlite"):
        logging.getLogger(noisy).setLevel(logging.INFO)

    _configured = True
    logging.getLogger(__name__).info(
        "File logging enabled: %s (rotating 10MB × 5)", log_file
    )
    return log_file
