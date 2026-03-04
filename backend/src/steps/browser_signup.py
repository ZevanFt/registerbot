"""Browser-based signup step via patchright.

Strategy:
1. Navigate to chat.openai.com to pass Cloudflare.
2. Click "Sign up for free" — modal dialog appears.
3. Fill email + Continue → password field appears → fill password + Continue.
4. Wait for email verification page.
5. Store browser session in metadata for BrowserVerifyEmailStep.

NOTE: We do NOT inject our own PKCE params here. chatgpt.com uses its own
OAuth flow with its own client_id. After the full signup + email verification
completes, BrowserVerifyEmailStep will initiate a separate PKCE flow using
the authenticated session to obtain tokens for our application.
"""

from __future__ import annotations

import asyncio
import secrets

import structlog

from src.integrations.browser import BrowserManager
from src.pipeline.base import Step, StepResult
from src.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)

CHAT_OPENAI_URL = "https://chat.openai.com"


class BrowserSignupStep(Step):
    """Submit OpenAI registration via chatgpt.com modal."""

    name = "browser_signup"
    description = "Register OpenAI account via chatgpt.com browser automation"

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")
        if not context.email:
            return StepResult(success=False, error="email missing in context")
        if not context.password:
            return StepResult(success=False, error="password missing in context")

        manager = BrowserManager(
            headless=False,
            browser_timeout=settings.registration.browser_timeout,
            typing_delay_ms=settings.registration.typing_delay_ms,
            navigation_timeout=settings.registration.navigation_timeout,
        )
        proxy = settings.network.openai_proxy or settings.network.http_proxy
        session_id = ""
        try:
            session_id = await manager.create_session(proxy=proxy)
            session = manager.get_session(session_id)
            if session is None:
                return StepResult(success=False, error="Failed to create browser session")
            page = session.page

            # ---- Step 1: Navigate to chat.openai.com ----
            logger.info("browser_navigating", url=CHAT_OPENAI_URL, proxy=proxy)
            await page.goto(CHAT_OPENAI_URL, wait_until="domcontentloaded")
            await asyncio.sleep(8)

            page_title = await page.title()
            logger.info("browser_page_loaded", url=page.url, title=page_title)
            try:
                await manager.take_screenshot(session_id, "data/debug_chatgpt_loaded.png")
            except Exception:
                pass

            # ---- Step 2: Click "Sign up" button ----
            signup_btn = page.locator(
                'button:has-text("Sign up"), '
                'a:has-text("Sign up"), '
                'button:has-text("Get started"), '
                'a:has-text("Get started")'
            )
            btn_count = await signup_btn.count()
            if btn_count == 0:
                try:
                    await manager.take_screenshot(session_id, "data/debug_no_signup_btn.png")
                except Exception:
                    pass
                return StepResult(
                    success=False,
                    error=f"Sign up button not found (title={page_title})",
                )

            await signup_btn.first.click()
            logger.info("browser_signup_clicked")
            await asyncio.sleep(3 + secrets.randbelow(2000) / 1000)

            # ---- Step 3: Fill email in modal ----
            email_selector = 'input[name="email"], input[type="email"], input[id="email"]'
            try:
                await page.wait_for_selector(email_selector, state="visible", timeout=15000)
            except Exception:
                try:
                    await manager.take_screenshot(session_id, "data/debug_no_email_field.png")
                except Exception:
                    pass
                return StepResult(
                    success=False,
                    error="Email input not found after clicking Sign up",
                )

            await asyncio.sleep(0.5 + secrets.randbelow(500) / 1000)
            await page.fill(email_selector, context.email)
            logger.info("browser_email_filled", email=context.email)
            await asyncio.sleep(0.5 + secrets.randbelow(500) / 1000)

            try:
                await manager.take_screenshot(session_id, "data/debug_email_filled.png")
            except Exception:
                pass

            # ---- Step 4: Click Continue ----
            continue_selectors = [
                'button[type="submit"]',
                'button:has-text("Continue")',
                'button:has-text("continue")',
                'button:has-text("Submit")',
            ]
            clicked = False
            for sel in continue_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible():
                        await btn.click()
                        clicked = True
                        logger.info("browser_continue_clicked", selector=sel)
                        break
                except Exception:
                    continue
            if not clicked:
                return StepResult(
                    success=False, error="Continue button not found after email input"
                )

            await asyncio.sleep(3 + secrets.randbelow(2000) / 1000)

            # ---- Step 5: Wait for password field ----
            # After clicking Continue on chatgpt.com's modal, the page may
            # navigate to auth.openai.com/create-account/password or show the
            # password field inline. We check on whichever page we end up on.
            password_selector = (
                'input[name="password"], input[type="password"], input[id="password"]'
            )

            # The page might navigate away from chatgpt.com to auth.openai.com
            active_page = page
            try:
                await active_page.wait_for_selector(
                    password_selector, state="visible", timeout=20000
                )
            except Exception:
                # Maybe the page navigated and we need to check the current URL
                current_url = active_page.url
                logger.info("password_field_wait_failed", url=current_url)

                # If we're on a create-account page that asks for email again,
                # it means the flow redirected. Fill email and continue.
                if "create-account" in current_url:
                    logger.info("on_create_account_page_refilling_email")
                    try:
                        email_input = active_page.locator(email_selector).first
                        if await email_input.is_visible():
                            await email_input.fill(context.email)
                            await asyncio.sleep(0.5)
                            for sel in continue_selectors:
                                try:
                                    btn = active_page.locator(sel).first
                                    if await btn.is_visible():
                                        await btn.click()
                                        break
                                except Exception:
                                    continue
                            await asyncio.sleep(3)
                            # Now try password field again
                            await active_page.wait_for_selector(
                                password_selector, state="visible", timeout=20000
                            )
                    except Exception:
                        pass

                # Final check
                try:
                    pwd_visible = await active_page.locator(password_selector).first.is_visible()
                except Exception:
                    pwd_visible = False

                if not pwd_visible:
                    body_text = ""
                    try:
                        body_text = (await active_page.inner_text("body") or "")[:500]
                    except Exception:
                        pass

                    if "already" in body_text.lower() or "exist" in body_text.lower():
                        await manager.close_session(session_id)
                        return StepResult(
                            success=False, error="email_exists: email already registered"
                        )

                    try:
                        await manager.take_screenshot(
                            session_id, "data/debug_no_password.png"
                        )
                    except Exception:
                        pass
                    logger.error(
                        "browser_password_timeout",
                        url=active_page.url,
                        body=body_text[:200],
                    )
                    return StepResult(success=False, error="Password field not found")

            logger.info("browser_password_field_found", url=active_page.url)

            # ---- Step 6: Fill password (with Turnstile wait) ----
            await asyncio.sleep(1.0 + secrets.randbelow(1000) / 1000)
            await active_page.fill(password_selector, context.password)
            logger.info("browser_password_filled")

            # Wait for Turnstile to complete (if present).
            # Turnstile adds a hidden input with the response token.
            turnstile_selector = (
                'input[name="cf-turnstile-response"], '
                'iframe[src*="turnstile"], '
                'div.cf-turnstile'
            )
            try:
                turnstile = active_page.locator(turnstile_selector).first
                if await turnstile.count() > 0:
                    logger.info("turnstile_detected_waiting")
                    # Wait up to 15s for Turnstile to solve
                    for _ in range(30):
                        try:
                            token_input = active_page.locator(
                                'input[name="cf-turnstile-response"]'
                            ).first
                            token_val = await token_input.input_value()
                            if token_val:
                                logger.info("turnstile_solved")
                                break
                        except Exception:
                            pass
                        await asyncio.sleep(0.5)
                else:
                    logger.info("no_turnstile_detected")
            except Exception:
                pass

            await asyncio.sleep(2.0 + secrets.randbelow(1000) / 1000)

            try:
                await manager.take_screenshot(
                    session_id, "data/debug_before_password_submit.png"
                )
            except Exception:
                pass

            # ---- Step 7: Click Continue/Submit for password ----
            clicked = False
            for sel in continue_selectors:
                try:
                    btn = active_page.locator(sel).first
                    if await btn.is_visible():
                        await btn.click()
                        clicked = True
                        logger.info("browser_password_submitted", selector=sel)
                        break
                except Exception:
                    continue
            if not clicked:
                return StepResult(
                    success=False, error="Submit button not found after password input"
                )

            # Wait for transition — retry on "Operation timed out" errors
            for attempt in range(3):
                url_before = active_page.url
                try:
                    await active_page.wait_for_url(
                        lambda u: u != url_before, timeout=30000
                    )
                except Exception:
                    pass

                await asyncio.sleep(3)

                # Check for "Operation timed out" / error page with Try again
                body_text = ""
                try:
                    body_text = (await active_page.inner_text("body") or "")[:500]
                except Exception:
                    pass

                if "timed out" in body_text.lower() or "try again" in body_text.lower():
                    logger.warning(
                        "browser_operation_timed_out",
                        attempt=attempt + 1,
                        url=active_page.url,
                    )
                    try:
                        await manager.take_screenshot(
                            session_id,
                            f"data/debug_timeout_retry_{attempt}.png",
                        )
                    except Exception:
                        pass
                    # Click "Try again" button
                    try:
                        retry_btn = active_page.locator(
                            'button:has-text("Try again"), a:has-text("Try again")'
                        ).first
                        if await retry_btn.is_visible():
                            await retry_btn.click()
                            logger.info("browser_try_again_clicked", attempt=attempt + 1)
                            await asyncio.sleep(5)
                            continue
                    except Exception:
                        pass
                break

            try:
                await manager.take_screenshot(session_id, "data/debug_after_password.png")
            except Exception:
                pass

            current_url = active_page.url
            logger.info(
                "browser_signup_submitted",
                email=context.email,
                url=current_url,
            )

            # Verify we reached the email verification page
            if "email-verification" not in current_url and "verify" not in current_url:
                body_text = ""
                try:
                    body_text = (await active_page.inner_text("body") or "")[:500]
                except Exception:
                    pass
                if "already" in body_text.lower() or "exist" in body_text.lower():
                    await manager.close_session(session_id)
                    return StepResult(
                        success=False, error="email_exists: email already registered"
                    )
                if "timed out" in body_text.lower():
                    await manager.close_session(session_id)
                    return StepResult(
                        success=False,
                        error="auth_server_timeout: OpenAI auth server operation timed out after retries",
                    )
                logger.warning(
                    "browser_unexpected_url",
                    expected="email-verification",
                    got=current_url,
                    body=body_text[:200],
                )

            # Store session for downstream steps.
            # No code_verifier here — BrowserVerifyEmailStep will handle PKCE
            # after verification completes using the authenticated session.
            new_metadata = {
                **context.metadata,
                "browser_session_id": session_id,
                "_browser_manager": manager,
                "_active_page": active_page,
            }
            return StepResult(success=True, data={"metadata": new_metadata})

        except Exception as exc:
            if session_id:
                try:
                    await manager.take_screenshot(session_id, "data/debug_signup_error.png")
                except Exception:
                    pass
                await manager.close_session(session_id)
            return StepResult(success=False, error=f"browser_signup_failed: {exc}")
