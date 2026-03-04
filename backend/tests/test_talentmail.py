"""Tests for TalentMail client behavior with mocked HTTP layer."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from src.integrations.talentmail import TalentMailClient


class TalentMailClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_stores_token(self) -> None:
        client = TalentMailClient("http://localhost/api", "u", "p")
        response = MagicMock()
        response.json.return_value = {"access_token": "token-1"}
        response.raise_for_status.return_value = None
        client._client.post = AsyncMock(return_value=response)

        token = await client.login()

        self.assertEqual(token, "token-1")
        self.assertEqual(client._token, "token-1")

    async def test_create_temp_email_uses_auth(self) -> None:
        client = TalentMailClient("http://localhost/api", "u", "p")
        client.login = AsyncMock(return_value="token-1")
        response = MagicMock()
        response.json.return_value = {"data": {"id": "m1", "email": "a@test.com"}}
        response.raise_for_status.return_value = None
        client._client.post = AsyncMock(return_value=response)

        data = await client.create_temp_email(prefix="abc")

        self.assertEqual(data["id"], "m1")
        self.assertEqual(data["email"], "a@test.com")

    async def test_wait_for_code_returns_first_code(self) -> None:
        client = TalentMailClient("http://localhost/api", "u", "p")
        client.get_inbox = AsyncMock(
            side_effect=[
                [{"subject": "Welcome"}],
                [{"subject": "Your code is 123456"}],
            ]
        )

        code = await client.wait_for_code("mailbox-1", timeout=10, poll_interval=0)

        self.assertEqual(code, "123456")


if __name__ == "__main__":
    unittest.main()
