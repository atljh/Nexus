#!/usr/bin/env python3
"""
Task flow smoke test against an isolated temporary database.

Checks API lifecycle for likes/comments tasks:
- create
- start
- terminal transition
- restart
- cancel
- delete
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_ENTRY = PROJECT_DIR / "backend" / ".venv" / "bin" / "python"
BACKEND_MAIN = PROJECT_DIR / "backend" / "main.py"
BASE_URL = "http://127.0.0.1:8000"


def _http(method: str, path: str, data: dict[str, Any] | None = None) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        parsed = None
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw}
        return e.code, parsed


def _wait_health(timeout_sec: int = 30) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            code, _ = _http("GET", "/health")
            if code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _wait_task_terminal(task_id: int, timeout_sec: int = 45) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        code, payload = _http("GET", f"/api/tasks/{task_id}")
        if code != 200:
            raise RuntimeError(f"Failed to fetch task {task_id}: {code} {payload}")
        assert isinstance(payload, dict)
        last = payload
        if payload.get("status") not in {"pending", "running", "paused"}:
            return payload
        time.sleep(1)
    raise TimeoutError(f"Task {task_id} did not reach terminal state: {last}")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _set_account_valid(db_path: Path, account_id: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE accounts
            SET status = 'valid', api_id = NULL, api_hash = NULL
            WHERE id = ?
            """,
            (account_id,),
        )
        conn.commit()


def run() -> None:
    # Guard: avoid running against an already running local backend.
    if _wait_health(timeout_sec=1):
        raise RuntimeError("Port 8000 already in use by a running backend. Stop it first.")

    with tempfile.TemporaryDirectory(prefix="nexus-task-flow-") as tmpdir:
        db_path = Path(tmpdir) / "nexus-test.db"

        env = os.environ.copy()
        env["NEXUS_DB_PATH"] = str(db_path)
        env["NEXUS_BACKEND_RELOAD"] = "0"

        proc = subprocess.Popen(
            [str(BACKEND_ENTRY), str(BACKEND_MAIN)],
            cwd=str(PROJECT_DIR / "backend"),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            _assert(_wait_health(timeout_sec=30), "Backend did not become healthy")

            # Create a test account and mark as valid in isolated DB.
            code, account = _http(
                "POST",
                "/api/accounts",
                {"phone": "+10000000001", "session_string": "test-session"},
            )
            _assert(code == 200 and isinstance(account, dict), f"Account create failed: {code} {account}")
            account_id = int(account["id"])
            _set_account_valid(db_path, account_id)

            # Likes task lifecycle.
            code, likes = _http(
                "POST",
                "/api/tasks/likes",
                {
                    "config": {
                        "channel": "@test_channel",
                        "post_id": 1,
                        "reactions": ["👍"],
                        "emoji_mode": "single",
                    },
                    "account_ids": [account_id],
                    "total_actions": 1,
                    "min_delay": 1,
                    "max_delay": 1,
                    "max_concurrent": 1,
                },
            )
            _assert(code == 200 and isinstance(likes, dict), f"Likes create failed: {code} {likes}")
            likes_id = int(likes["id"])

            code, started = _http("POST", f"/api/tasks/{likes_id}/start", {})
            _assert(code == 200 and isinstance(started, dict), f"Likes start failed: {code} {started}")

            terminal = _wait_task_terminal(likes_id)
            _assert(terminal["status"] in {"completed", "failed", "cancelled"}, f"Unexpected likes terminal: {terminal}")

            code, logs = _http("GET", f"/api/tasks/{likes_id}/logs")
            _assert(code == 200 and isinstance(logs, list), f"Likes logs failed: {code} {logs}")

            code, restarted = _http("POST", f"/api/tasks/{likes_id}/restart", {})
            _assert(code == 200 and isinstance(restarted, dict), f"Likes restart failed: {code} {restarted}")
            _assert(restarted["status"] == "pending", f"Likes restart status mismatch: {restarted}")

            code, cancelled = _http("POST", f"/api/tasks/{likes_id}/cancel", {})
            _assert(code == 200 and isinstance(cancelled, dict), f"Likes cancel failed: {code} {cancelled}")
            _assert(cancelled["status"] == "cancelled", f"Likes cancel status mismatch: {cancelled}")

            code, _ = _http("DELETE", f"/api/tasks/{likes_id}")
            _assert(code == 200, f"Likes delete failed: {code}")

            # Comments task lifecycle.
            code, comments = _http(
                "POST",
                "/api/tasks/comments",
                {
                    "config": {
                        "channels": ["@test_channel"],
                        "templates": ["test comment"],
                        "rotation_mode": "random",
                        "comments_per_account": 1,
                        "mode": "single",
                    },
                    "account_ids": [account_id],
                    "total_actions": 1,
                    "min_delay": 1,
                    "max_delay": 1,
                },
            )
            _assert(code == 200 and isinstance(comments, dict), f"Comments create failed: {code} {comments}")
            comments_id = int(comments["id"])

            code, _ = _http("POST", f"/api/tasks/{comments_id}/start", {})
            _assert(code == 200, f"Comments start failed: {code}")

            terminal = _wait_task_terminal(comments_id)
            _assert(terminal["status"] in {"completed", "failed", "cancelled"}, f"Unexpected comments terminal: {terminal}")

            code, channels = _http("GET", f"/api/tasks/{comments_id}/channels")
            _assert(code == 200 and isinstance(channels, list), f"Comments channels failed: {code} {channels}")

            code, restarted = _http("POST", f"/api/tasks/{comments_id}/restart", {})
            _assert(code == 200 and isinstance(restarted, dict), f"Comments restart failed: {code} {restarted}")
            _assert(restarted["status"] == "pending", f"Comments restart status mismatch: {restarted}")

            code, cancelled = _http("POST", f"/api/tasks/{comments_id}/cancel", {})
            _assert(code == 200 and isinstance(cancelled, dict), f"Comments cancel failed: {code} {cancelled}")
            _assert(cancelled["status"] == "cancelled", f"Comments cancel status mismatch: {cancelled}")

            code, _ = _http("DELETE", f"/api/tasks/{comments_id}")
            _assert(code == 200, f"Comments delete failed: {code}")

            # Cleanup account
            code, _ = _http("DELETE", f"/api/accounts/{account_id}")
            _assert(code == 200, f"Account delete failed: {code}")

            print("Task flow smoke passed.")
        finally:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

            if proc.stdout:
                tail = proc.stdout.read()
                if tail:
                    print("--- backend output ---")
                    print("\n".join(tail.splitlines()[-40:]))


if __name__ == "__main__":
    run()
