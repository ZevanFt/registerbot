"""OpenAI registration API client placeholder."""

from __future__ import annotations

import base64
import json
import secrets
from hashlib import sha256
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from src.middleware.auth import build_openai_error


class OpenAIRegistrationClient:
    """Client for OpenAI registration and OAuth APIs."""

    def __init__(
        self,
        auth_url: str = "https://auth0.openai.com",
        oauth_client_id: str = "",
        timeout: float = 30.0,
        proxy: str = "",
    ) -> None:
        self.auth_url = auth_url.rstrip("/")
        self.oauth_client_id = oauth_client_id
        self.timeout = timeout
        self.proxy = proxy

    def _client_kwargs(self, timeout: float | httpx.Timeout | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"trust_env": False}
        if timeout is not None:
            kwargs["timeout"] = timeout
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return kwargs

    def _pkce_pair(self) -> tuple[str, str]:
        raw = secrets.token_urlsafe(72)
        code_verifier = raw[:96]
        digest = sha256(code_verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        return code_verifier, challenge

    async def init_auth_session(self, auth_url: str) -> dict[str, str]:
        base = auth_url.rstrip("/")
        code_verifier, code_challenge = self._pkce_pair()
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        params = {
            "client_id": self.oauth_client_id,
            "response_type": "code",
            "redirect_uri": "https://platform.openai.com/auth/callback",
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "signup",
            "state": state,
            "nonce": nonce,
        }
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.get(f"{base}/authorize", params=params)
        if response.status_code >= 400:
            raise RuntimeError(f"init_auth_session_failed: HTTP {response.status_code}")

        csrf_token = ""
        login_hint = ""
        header_cookie = response.headers.get("set-cookie", "")
        for part in header_cookie.split(";"):
            text = part.strip()
            if text.startswith("csrf_token="):
                csrf_token = text.split("=", 1)[1]
                break
        if not csrf_token:
            parsed_url = urlparse(str(response.url))
            query = parse_qs(parsed_url.query)
            csrf_token = str(query.get("csrf_token", [""])[0])
            login_hint = str(query.get("login_hint", [""])[0])

        if not csrf_token:
            body = response.text
            marker = 'name="csrf_token"'
            idx = body.find(marker)
            if idx >= 0:
                value_pos = body.find('value="', idx)
                if value_pos >= 0:
                    value_start = value_pos + len('value="')
                    value_end = body.find('"', value_start)
                    if value_end > value_start:
                        csrf_token = body[value_start:value_end]

        if not csrf_token:
            raise RuntimeError("init_auth_session_failed: csrf_token not found")

        return {
            "csrf_token": csrf_token,
            "state": state,
            "code_verifier": code_verifier,
            "code_challenge": code_challenge,
            "login_hint": login_hint,
        }

    async def check_email_available(
        self,
        email: str,
        csrf_token: str,
        turnstile_token: str = "",
        auth_url: str | None = None,
    ) -> bool:
        base = (auth_url or self.auth_url).rstrip("/")
        payload = {
            "email": email,
            "csrf_token": csrf_token,
            "turnstile_token": turnstile_token,
        }
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.post(f"{base}/u/signup/identifier", headers=headers, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"check_email_available_failed: HTTP {response.status_code}")
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            raise RuntimeError("check_email_available_failed: invalid response body")

        if "available" in data:
            return bool(data.get("available"))
        if "exists" in data:
            return not bool(data.get("exists"))
        return bool(data.get("success", True))

    async def submit_registration(
        self,
        email: str,
        password: str,
        csrf_token: str,
        turnstile_token: str = "",
        auth_url: str | None = None,
    ) -> dict[str, Any]:
        base = (auth_url or self.auth_url).rstrip("/")
        payload = {
            "email": email,
            "password": password,
            "csrf_token": csrf_token,
            "turnstile_token": turnstile_token,
        }
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.post(f"{base}/u/signup", headers=headers, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"submit_registration_failed: HTTP {response.status_code}")
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            raise RuntimeError("submit_registration_failed: invalid response body")
        return {
            "success": bool(data.get("success", True)),
            "requires_verification": bool(data.get("requires_verification", True)),
        }

    async def verify_email(self, email: str, code: str, csrf_token: str, auth_url: str | None = None) -> dict[str, Any]:
        base = (auth_url or self.auth_url).rstrip("/")
        payload = {
            "email": email,
            "code": code,
            "csrf_token": csrf_token,
        }
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.post(f"{base}/u/signup/verify", headers=headers, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"verify_email_failed: HTTP {response.status_code}")
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            raise RuntimeError("verify_email_failed: invalid response body")
        return {
            "verified": bool(data.get("verified", True)),
            "authorization_code": str(data.get("authorization_code", data.get("code", ""))),
        }

    async def exchange_code_for_tokens(
        self,
        authorization_code: str,
        code_verifier: str,
        redirect_uri: str,
        auth_url: str | None = None,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        base = (auth_url or self.auth_url).rstrip("/")
        resolved_client_id = client_id or self.oauth_client_id
        payload = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "client_id": resolved_client_id,
        }
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.post(f"{base}/oauth/token", headers=headers, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"exchange_code_for_tokens_failed: HTTP {response.status_code}")
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            raise RuntimeError("exchange_code_for_tokens_failed: invalid response body")
        if "access_token" not in data or "expires_in" not in data:
            raise RuntimeError("exchange_code_for_tokens_failed: missing access_token or expires_in")
        return {
            "access_token": str(data.get("access_token", "")),
            "refresh_token": str(data.get("refresh_token", "")),
            "expires_in": int(data.get("expires_in", 0)),
        }

    async def create_session(self, access_token: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.post(
                "https://api.openai.com/dashboard/onboarding/session",
                headers=headers,
                json={},
            )
        if response.status_code >= 400:
            raise RuntimeError(f"create_session_failed: HTTP {response.status_code}")
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            raise RuntimeError("create_session_failed: invalid response body")
        return data

    async def set_profile(self, access_token: str, name: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {"name": name}
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.patch("https://api.openai.com/dashboard/user", headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"set_profile_failed: HTTP {response.status_code}")
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            raise RuntimeError("set_profile_failed: invalid response body")
        return data

    async def refresh_access_token(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str = "",
        token_url: str = "https://auth0.openai.com/oauth/token",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
        if client_secret:
            payload["client_secret"] = client_secret

        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            response = await client.post(
                token_url,
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            try:
                body = response.json()
            except ValueError:
                body = {}

            if response.status_code >= 400:
                error = str(body.get("error", "token_refresh_failed")) if isinstance(body, dict) else "token_refresh_failed"
                description = (
                    str(body.get("error_description", f"HTTP {response.status_code}"))
                    if isinstance(body, dict)
                    else f"HTTP {response.status_code}"
                )
                raise RuntimeError(f"{error}: {description}")

            if not isinstance(body, dict):
                raise RuntimeError("token_refresh_failed: invalid response body")
            if "access_token" not in body or "expires_in" not in body:
                raise RuntimeError("token_refresh_failed: missing access_token or expires_in")
            return body


class OpenAIChatClient:
    """OpenAI chat/completions compatible upstream client."""

    def __init__(self, base_url: str, timeout: float = 120.0, stream_timeout: float = 300.0, proxy: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.stream_timeout = stream_timeout
        self.proxy = proxy

    def _client_kwargs(self, timeout: float | httpx.Timeout) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"timeout": timeout, "trust_env": False}
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return kwargs

    async def list_models(self, api_key: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.get(f"{self.base_url}/v1/models", headers=headers)
            response.raise_for_status()
            return response.json()

    async def chat_completions(self, api_key: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            try:
                body = response.json()
            except ValueError:
                body = {}
            return response.status_code, body

    async def chat_completions_stream(
        self,
        api_key: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        headers = {"Authorization": f"Bearer {api_key}"}
        timeout = httpx.Timeout(self.stream_timeout, connect=self.timeout)
        try:
            async with httpx.AsyncClient(**self._client_kwargs(timeout=timeout)) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        raw = await response.aread()
                        message = f"Upstream service returned {response.status_code}"
                        try:
                            parsed = json.loads(raw.decode("utf-8"))
                            if isinstance(parsed, dict):
                                upstream_error = parsed.get("error", {})
                                if isinstance(upstream_error, dict):
                                    message = str(upstream_error.get("message", message))
                        except (ValueError, UnicodeDecodeError):
                            pass
                        error = build_openai_error(
                            message=message,
                            error_type="upstream_error",
                            code=str(response.status_code),
                        )
                        yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n".encode("utf-8")
                        yield b"data: [DONE]\n\n"
                        return
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk
        except Exception as exc:
            error = build_openai_error(
                message=f"Streaming request failed: {exc}",
                error_type="api_error",
                code="stream_error",
            )
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"
