"""OpenAI registration API client placeholder."""

from __future__ import annotations

import base64
import json
import secrets
import re
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

    def _json_or_text(self, response: httpx.Response) -> dict[str, Any]:
        if not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError:
            return {"raw": response.text[:400]}
        if isinstance(payload, dict):
            return payload
        return {"raw": str(payload)[:400]}

    def _registration_headers(self) -> dict[str, str]:
        # Keep headers close to browser traffic to reduce upstream anti-bot false negatives.
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://auth.openai.com",
            "Referer": "https://auth.openai.com/",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        }

    def _http_error_message(self, prefix: str, response: httpx.Response, body: dict[str, Any]) -> str:
        nested_error = body.get("error")
        if isinstance(nested_error, dict):
            code = str(nested_error.get("code") or "")
            message = str(nested_error.get("message") or "")
            parts = [part for part in [code, message] if part]
            if parts:
                return f"{prefix}: HTTP {response.status_code} ({' | '.join(parts)})"
        text = str(body.get("message") or body.get("error_description") or body.get("raw") or "").strip()
        if text:
            return f"{prefix}: HTTP {response.status_code} ({text})"
        return f"{prefix}: HTTP {response.status_code}"

    def _pkce_pair(self) -> tuple[str, str]:
        raw = secrets.token_urlsafe(72)
        code_verifier = raw[:96]
        digest = sha256(code_verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        return code_verifier, challenge

    async def probe_authorize_challenge(self, auth_url: str, authorize_url: str = "") -> dict[str, Any]:
        """Probe authorize endpoint and detect anti-bot challenge pages."""

        base = auth_url.rstrip("/")
        code_verifier, code_challenge = self._pkce_pair()
        params = {
            "client_id": self.oauth_client_id,
            "response_type": "code",
            "redirect_uri": "https://platform.openai.com/auth/callback",
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "signup",
            "state": secrets.token_urlsafe(24),
            "nonce": secrets.token_urlsafe(24),
        }
        clean_authorize_url = authorize_url.strip()
        probe_url = clean_authorize_url or f"{base}/oauth/authorize"

        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.get(
                probe_url,
                params=params,
                headers=self._registration_headers(),
                follow_redirects=True,
            )

        text = response.text.lower()
        markers = [
            key
            for key in [
                "just a moment",
                "cloudflare",
                "challenge",
                "captcha",
                "turnstile",
                "bot",
                "access denied",
                "forbidden",
            ]
            if key in text
        ]
        challenge_detected = bool(markers) or response.status_code >= 400
        return {
            "status_code": response.status_code,
            "final_url": str(response.url),
            "content_type": str(response.headers.get("content-type") or ""),
            "challenge_detected": challenge_detected,
            "markers": markers,
            "body_snippet": response.text[:600],
            "set_cookie_count": len(response.headers.get_list("set-cookie")),
            "requested_url": probe_url,
            "pkce_preview": code_verifier[:8],
        }

    async def init_auth_session(self, auth_url: str, authorize_url: str = "") -> dict[str, str]:
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
        candidate_urls: list[str] = []
        clean_authorize_url = authorize_url.strip()
        if clean_authorize_url:
            candidate_urls.append(clean_authorize_url)
        if base:
            candidate_urls.append(f"{base}/oauth/authorize")
            candidate_urls.append(f"{base}/authorize")
        # de-duplicate while keeping order
        candidate_urls = list(dict.fromkeys(candidate_urls))

        response: httpx.Response | None = None
        tried_errors: list[str] = []
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            for url in candidate_urls:
                resp = await client.get(
                    url,
                    params=params,
                    headers=self._registration_headers(),
                    follow_redirects=True,
                )
                if resp.status_code < 400:
                    response = resp
                    break
                tried_errors.append(f"{url} -> HTTP {resp.status_code}")

        if response is None:
            detail = "; ".join(tried_errors) if tried_errors else "no authorize endpoint available"
            raise RuntimeError(f"init_auth_session_failed: {detail}")

        csrf_token = ""
        login_hint = ""

        # 1) Try direct cookie jar on final response.
        csrf_token = str(response.cookies.get("csrf_token") or "").strip()

        # 2) Try cookie jars in redirect history.
        if not csrf_token:
            for hist in reversed(response.history):
                csrf_token = str(hist.cookies.get("csrf_token") or "").strip()
                if csrf_token:
                    break

        # 3) Parse Set-Cookie headers from final response.
        if not csrf_token:
            for header in response.headers.get_list("set-cookie"):
                for part in header.split(";"):
                    text = part.strip()
                    if text.startswith("csrf_token="):
                        csrf_token = text.split("=", 1)[1]
                        break
                if csrf_token:
                    break

        if not csrf_token:
            parsed_url = urlparse(str(response.url))
            query = parse_qs(parsed_url.query)
            csrf_token = str(query.get("csrf_token", [""])[0])
            login_hint = str(query.get("login_hint", [""])[0])

        if not csrf_token:
            body = response.text
            # Support common hidden-input variants.
            patterns = [
                r'name="csrf_token"\s+value="([^"]+)"',
                r"name='csrf_token'\s+value='([^']+)'",
                r'name="csrfToken"\s+value="([^"]+)"',
                r'name="csrf-token"\s+value="([^"]+)"',
            ]
            for pattern in patterns:
                match = re.search(pattern, body)
                if match:
                    csrf_token = match.group(1).strip()
                    break

        if not csrf_token:
            body_text = response.text.lower()
            markers: list[str] = []
            for item in ["captcha", "cloudflare", "turnstile", "forbidden", "access denied", "bot"]:
                if item in body_text:
                    markers.append(item)
            marker_text = f" markers={','.join(markers)}" if markers else ""
            raise RuntimeError(
                f"init_auth_session_failed: csrf_token not found (url={response.url}{marker_text})"
            )

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

        data = self._json_or_text(response)
        if response.status_code >= 400:
            raise RuntimeError(self._http_error_message("check_email_available_failed", response, data))

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
        headers = self._registration_headers()
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.post(f"{base}/u/signup", headers=headers, json=payload)

        data = self._json_or_text(response)
        if response.status_code >= 400:
            raise RuntimeError(self._http_error_message("submit_registration_failed", response, data))
        if not data:
            raise RuntimeError("submit_registration_failed: empty response body")
        return {
            "success": bool(data.get("success", True)),
            "requires_verification": bool(data.get("requires_verification", True)),
            "error": str(data.get("error") or data.get("message") or ""),
        }

    async def verify_email(self, email: str, code: str, csrf_token: str, auth_url: str | None = None) -> dict[str, Any]:
        base = (auth_url or self.auth_url).rstrip("/")
        payload = {
            "email": email,
            "code": code,
            "csrf_token": csrf_token,
        }
        headers = self._registration_headers()
        async with httpx.AsyncClient(**self._client_kwargs(timeout=self.timeout)) as client:
            response = await client.post(f"{base}/u/signup/verify", headers=headers, json=payload)

        data = self._json_or_text(response)
        if response.status_code >= 400:
            raise RuntimeError(self._http_error_message("verify_email_failed", response, data))
        if not data:
            raise RuntimeError("verify_email_failed: empty response body")
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
