"""Tests for telegram.client.validate_session helper."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import telegram.client as client_module


def test_validate_session_forwards_system_lang_code(monkeypatch):
    captured = {}

    class DummyBaseClient:
        def __init__(self, *args, **kwargs):
            captured["system_lang_code"] = kwargs.get("system_lang_code")
            self._me = SimpleNamespace(
                id=1,
                username="user",
                first_name="First",
                last_name="Last",
                phone="+10000000000",
                restricted=False,
                restriction_reason=None,
                deleted=False,
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def check_auth(self):
            return None

        async def get_me(self):
            return self._me

    monkeypatch.setattr(client_module, "BaseClient", DummyBaseClient)

    is_valid, user_info, error = asyncio.run(
        client_module.validate_session(
            "session-string",
            system_lang_code="uk-UA",
        )
    )

    assert is_valid is True
    assert error is None
    assert user_info["telegram_id"] == 1
    assert captured["system_lang_code"] == "uk-UA"
