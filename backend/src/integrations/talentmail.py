"""TalentMail async API client."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog


class TalentMailClient:
    """Client wrapper for TalentMail mailbox pool APIs."""

    def __init__(self, base_url: str, email: str, password: str, proxy: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self._token: str | None = None
        self._logger = structlog.get_logger(self.__class__.__name__)
        self._client = httpx.AsyncClient(
            timeout=30.0,
            trust_env=False,
            follow_redirects=True,
            **(dict(proxy=proxy) if proxy else {}),
        )

    @property
    def _headers(self) -> dict[str, str]:
        token = self._token or ""
        return {"Authorization": f"Bearer {token}"}

    def _build_url(self, path: str) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        if self.base_url.endswith("/api") and clean_path.startswith("/api/"):
            return f"{self.base_url}{clean_path[4:]}"
        return f"{self.base_url}{clean_path}"

    async def login(self) -> str:
        """Authenticate and return access token."""

        response = await self._client.post(
            self._build_url("/api/auth/login"),
            data={"username": self.email, "password": self.password},
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ValueError("TalentMail login response missing access_token")
        self._token = str(token)
        self._logger.info("talentmail_login_success")
        return self._token

    async def create_temp_email(self, prefix: str | None = None, purpose: str = "openai_register") -> dict[str, Any]:
        """Create mailbox from pool."""

        await self._ensure_authenticated()
        payload: dict[str, Any] = {"purpose": purpose}
        if prefix:
            payload["prefix"] = prefix
        response = await self._client.post(
            self._build_url("/api/pool/"),
            json=payload,
            headers=self._headers,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", data)

    async def get_inbox(self, mailbox_id: str, page: int = 1, limit: int = 20) -> list[dict[str, Any]]:
        """List inbox emails for mailbox id."""

        await self._ensure_authenticated()
        response = await self._client.get(
            self._build_url(f"/api/pool/{mailbox_id}/emails"),
            params={"page": page, "limit": limit},
            headers=self._headers,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            # Pool API returns {"items": [...], "total": N}
            # or wrapped as {"data": {"items": [...], "total": N}}
            data = payload.get("data", payload)
            if isinstance(data, dict):
                return data.get("items", [])
            if isinstance(data, list):
                return data
        return payload if isinstance(payload, list) else []

    async def wait_for_code(self, mailbox_id: str, timeout: int = 300, poll_interval: int = 5) -> str:
        """Poll inbox until a verification code is found."""

        elapsed = 0
        while elapsed < timeout:
            emails = await self.get_inbox(mailbox_id)
            for email in emails:
                code = self._extract_code(email)
                if code:
                    self._logger.info("talentmail_code_found", mailbox_id=mailbox_id)
                    return code
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Timed out waiting verification code for mailbox: {mailbox_id}")

    async def delete_temp_email(self, mailbox_id: str) -> bool:
        """Delete mailbox from pool."""

        await self._ensure_authenticated()
        response = await self._client.delete(
            self._build_url(f"/api/pool/{mailbox_id}"),
            headers=self._headers,
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    async def get_pool_stats(self) -> dict[str, Any]:
        """Get mailbox pool statistics."""

        await self._ensure_authenticated()
        response = await self._client.get(
            self._build_url("/api/pool/stats/"),
            headers=self._headers,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", payload)

    async def _ensure_authenticated(self) -> None:
        """Login automatically when token is unavailable."""

        if not self._token:
            await self.login()

    def _extract_code(self, email_data: dict[str, Any]) -> str | None:
        """Extract the first 6-digit verification code from email content."""

        # Pool API may return verification_code directly
        direct_code = email_data.get("verification_code")
        if direct_code and re.match(r"^\d{6}$", str(direct_code)):
            return str(direct_code)

        text_parts = [
            str(email_data.get("subject", "")),
            str(email_data.get("text", "")),
            str(email_data.get("body", "")),
            str(email_data.get("body_text", "")),
            str(email_data.get("body_html", "")),
            str(email_data.get("html", "")),
        ]
        combined = "\n".join(text_parts)
        match = re.search(r"\b(\d{6})\b", combined)
        return match.group(1) if match else None

    async def aclose(self) -> None:
        """Close underlying HTTP client."""

        await self._client.aclose()

    async def __aenter__(self) -> "TalentMailClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()
