"""
Safety tests for Task model serialization.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import Task


def test_task_to_dict_masks_ai_api_key():
    task = Task(
        task_type="comments",
        status="pending",
        config={
            "ai_enabled": True,
            "ai_model": "gpt-4o-mini",
            "ai_api_key": "sk-secret-value",
            "channels": ["@test"],
        },
        total_actions=1,
        completed_actions=0,
        failed_actions=0,
        min_delay=30.0,
        max_delay=60.0,
        max_concurrent=1,
    )

    payload = task.to_dict()

    assert payload["config"]["ai_enabled"] is True
    assert payload["config"]["ai_model"] == "gpt-4o-mini"
    assert payload["config"]["channels"] == ["@test"]
    assert payload["config"]["ai_api_key"] == "***"
