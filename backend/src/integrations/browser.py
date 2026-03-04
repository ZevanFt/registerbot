"""Patchright browser manager for registration automation.

Uses patchright (anti-detection Playwright fork) in headed mode.
Cloud servers must run Xvfb to provide a virtual display.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from patchright.async_api import BrowserContext, Page, Playwright, async_playwright

logger = structlog.get_logger(__name__)


@dataclass
class BrowserSession:
    """Active browser session."""

    session_id: str
    context: BrowserContext
    page: Page
    created_at: float = field(default_factory=time.time)


class BrowserManager:
    """Manage patchright browser lifecycle for registration.

    Important: headless mode is detected by Cloudflare/Sentinel,
    so we always launch in headed mode. Use Xvfb on headless servers.
    """

    def __init__(
        self,
        headless: bool = False,
        browser_timeout: int = 30,
        typing_delay_ms: int = 150,
        navigation_timeout: int = 60,
    ) -> None:
        # Always use headed mode — headless is blocked by CF/Sentinel
        self.headless = False
        self.browser_timeout = browser_timeout
        self.typing_delay_ms = typing_delay_ms
        self.navigation_timeout = navigation_timeout
        self._playwright: Playwright | None = None
        self._sessions: dict[str, BrowserSession] = {}

    async def _ensure_playwright(self) -> Playwright:
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        return self._playwright

    async def create_session(self, proxy: str = "") -> str:
        """Create a new browser session, return session_id."""
        pw = await self._ensure_playwright()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": launch_args,
        }
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}

        browser = await pw.chromium.launch(**launch_kwargs)

        context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1280, "height": 720},
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }

        context = await browser.new_context(**context_kwargs)
        context.set_default_timeout(self.browser_timeout * 1000)
        context.set_default_navigation_timeout(self.navigation_timeout * 1000)

        page = await context.new_page()

        session_id = secrets.token_hex(16)
        self._sessions[session_id] = BrowserSession(
            session_id=session_id,
            context=context,
            page=page,
        )
        logger.info("browser_session_created", session_id=session_id)
        return session_id

    def get_session(self, session_id: str) -> BrowserSession | None:
        """Get an active browser session by ID."""
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close and cleanup a browser session."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        try:
            browser = session.context.browser
            await session.context.close()
            if browser:
                await browser.close()
        except Exception:
            logger.warning("browser_session_close_error", session_id=session_id, exc_info=True)
        logger.info("browser_session_closed", session_id=session_id)

    async def close_all(self) -> None:
        """Close all active sessions and stop playwright."""
        for sid in list(self._sessions.keys()):
            await self.close_session(sid)
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def take_screenshot(self, session_id: str, path: str = "") -> bytes:
        """Take a screenshot for debugging."""
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        kwargs: dict[str, Any] = {"full_page": True}
        if path:
            kwargs["path"] = path
        return await session.page.screenshot(**kwargs)
