"""Browser-based email verification step using patchright.

After entering the verification code and the chatgpt.com signup flow completes,
this step initiates a SEPARATE PKCE OAuth flow using the browser's authenticated
session to obtain an authorization_code for our application.
"""

from __future__ import annotations

import asyncio
import base64
import random
import secrets
from hashlib import sha256
from urllib.parse import parse_qs, urlencode, urlparse

import structlog

from src.integrations.browser import BrowserManager
from src.pipeline.base import Step, StepResult
from src.pipeline.context import PipelineContext

logger = structlog.get_logger(__name__)


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    raw = secrets.token_urlsafe(72)
    code_verifier = raw[:96]
    digest = sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


class BrowserVerifyEmailStep(Step):
    """Verify email via browser, then acquire auth code via PKCE."""

    name = "browser_verify_email"
    description = "Enter verification code and acquire authorization code via PKCE"

    async def execute(self, context: PipelineContext) -> StepResult:
        settings = context.get("settings")
        if settings is None:
            return StepResult(success=False, error="Settings missing in context metadata")
        if not context.verification_code:
            return StepResult(success=False, error="verification_code missing in context")

        session_id = str(context.metadata.get("browser_session_id", ""))
        if not session_id:
            return StepResult(success=False, error="browser_session_id missing in metadata")

        manager: BrowserManager | None = context.metadata.get("_browser_manager")
        if manager is None:
            return StepResult(success=False, error="Browser manager not found in metadata")

        session = manager.get_session(session_id)
        if session is None:
            return StepResult(
                success=False, error=f"Browser session {session_id} expired or not found"
            )

        page = context.metadata.get("_active_page") or session.page
        code = context.verification_code

        try:
            # ============================================================
            # Phase 1: Enter verification code (complete chatgpt.com flow)
            # ============================================================

            # Pattern 1: Single input for the full code
            single_input = page.locator(
                'input[name="code"], '
                'input[type="text"][maxlength="6"], '
                'input[autocomplete="one-time-code"]'
            )
            # Pattern 2: Multiple single-digit inputs
            multi_inputs = page.locator(
                'input[type="text"][maxlength="1"], '
                'input[type="tel"][maxlength="1"]'
            )

            single_count = await single_input.count()
            multi_count = await multi_inputs.count()

            if single_count > 0:
                await single_input.first.fill(code)
                logger.info("verification_code_entered", mode="single_input")
            elif multi_count >= 6:
                for i, digit in enumerate(code[:6]):
                    inp = multi_inputs.nth(i)
                    await inp.fill(digit)
                    await asyncio.sleep(0.1 + secrets.randbelow(200) / 1000)
                logger.info("verification_code_entered", mode="multi_input", digits=len(code))
            else:
                fallback = page.locator("input:visible").first
                try:
                    await fallback.fill(code)
                    logger.info("verification_code_entered", mode="fallback")
                except Exception:
                    try:
                        await manager.take_screenshot(
                            session_id, "data/debug_code_input_not_found.png"
                        )
                    except Exception:
                        pass
                    return StepResult(
                        success=False, error="Verification code input not found"
                    )

            await asyncio.sleep(1.0)

            # Click submit/continue if auto-submit didn't trigger
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Continue")',
                'button:has-text("Verify")',
                'button:has-text("Submit")',
            ]
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible():
                        await btn.click()
                        logger.info("verify_submit_clicked", selector=sel)
                        break
                except Exception:
                    continue

            # Wait for chatgpt.com's verification flow to complete.
            # The page will navigate away from the verification page.
            url_before = page.url
            try:
                await page.wait_for_url(
                    lambda u: u != url_before, timeout=30000
                )
            except Exception:
                pass

            await asyncio.sleep(5)

            try:
                await page.screenshot(path="data/debug_after_verification.png")
            except Exception:
                pass

            current_url = page.url
            logger.info("verification_flow_completed", url=current_url)

            # ============================================================
            # Phase 1.5: Handle "about-you" page if present.
            # After email verification, OpenAI shows a page asking for
            # Full name + Birthday before the account is fully created.
            # ============================================================

            if "about-you" in current_url or "confirm-your-age" in current_url:
                logger.info("about_you_page_detected", url=current_url)

                # Generate random full name
                first_names = [
                    "James", "Emma", "Liam", "Olivia", "Noah", "Ava",
                    "Ethan", "Sophia", "Mason", "Isabella", "Lucas",
                    "Mia", "Logan", "Charlotte", "Alex", "Harper",
                    "Daniel", "Ella", "Jack", "Grace", "Ryan", "Lily",
                ]
                last_names = [
                    "Smith", "Johnson", "Williams", "Brown", "Jones",
                    "Garcia", "Miller", "Davis", "Wilson", "Anderson",
                    "Taylor", "Thomas", "Moore", "Jackson", "Martin",
                    "Lee", "Harris", "Clark", "Lewis", "Walker",
                ]
                random_name = f"{random.choice(first_names)} {random.choice(last_names)}"

                # Generate random birthday (18-35 years old), MM/DD/YYYY
                age = random.randint(18, 35)
                birth_year = 2026 - age
                birth_month = random.randint(1, 12)
                birth_day = random.randint(1, 28)  # safe for all months
                birthday_str = f"{birth_month:02d}/{birth_day:02d}/{birth_year}"

                # Fill Full name — use label-based locator first
                name_filled = False
                try:
                    name_input = page.get_by_label("Full name")
                    if await name_input.count() > 0:
                        await name_input.fill(random_name)
                        name_filled = True
                        logger.info("about_you_name_filled", name=random_name)
                except Exception:
                    pass
                if not name_filled:
                    try:
                        first_text = page.locator('input[type="text"]:visible').first
                        await first_text.fill(random_name)
                        name_filled = True
                        logger.info("about_you_name_filled_fallback", name=random_name)
                    except Exception:
                        logger.warning("about_you_name_input_not_found")

                await asyncio.sleep(0.5)

                # Fill Birthday — masked date input (MM/DD/YYYY segments).
                # Tab from name field to birthday, select all, type digits only.
                birthday_digits = birthday_str.replace("/", "")  # "01151995"
                try:
                    await page.keyboard.press("Tab")
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Control+a")
                    await asyncio.sleep(0.2)
                    await page.keyboard.type(birthday_digits, delay=100)
                    await asyncio.sleep(0.3)
                    logger.info("about_you_birthday_filled", birthday=birthday_str)
                except Exception:
                    logger.warning("about_you_birthday_keyboard_failed", exc_info=True)

                await asyncio.sleep(1)

                try:
                    await page.screenshot(path="data/debug_about_you_filled.png")
                except Exception:
                    pass

                # Click "Finish creating account"
                finish_selectors = [
                    'button:has-text("Finish creating account")',
                    'button:has-text("Finish")',
                    'button:has-text("Continue")',
                    'button[type="submit"]',
                ]
                for sel in finish_selectors:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible():
                            await btn.click()
                            logger.info("about_you_finish_clicked", selector=sel)
                            break
                    except Exception:
                        continue

                # Wait for navigation away from about-you page
                try:
                    await page.wait_for_url(
                        lambda u: "about-you" not in u and "confirm-your-age" not in u,
                        timeout=30000,
                    )
                except Exception:
                    pass

                await asyncio.sleep(5)
                current_url = page.url
                logger.info("about_you_completed", url=current_url)

                try:
                    await page.screenshot(path="data/debug_after_about_you.png")
                except Exception:
                    pass

            # ============================================================
            # Phase 2: Handle onboarding page and confirm registration.
            # After about-you, ChatGPT shows "What brings you to ChatGPT?"
            # onboarding page. Click Skip to dismiss it.
            # ============================================================

            current_url = page.url
            # Handle onboarding if present (chatgpt.com with questionnaire)
            try:
                skip_btn = page.locator(
                    'button:has-text("Skip"), '
                    'a:has-text("Skip")'
                )
                if await skip_btn.count() > 0:
                    await skip_btn.first.click()
                    logger.info("onboarding_skipped")
                    await asyncio.sleep(3)
            except Exception:
                pass

            try:
                await page.screenshot(path="data/debug_registration_complete.png")
            except Exception:
                pass

            final_url = page.url
            logger.info(
                "registration_complete",
                email=context.email,
                url=final_url,
            )

            return StepResult(
                success=True,
                data={
                    "registered": True,
                    "final_url": final_url,
                },
            )

        except Exception as exc:
            try:
                await page.screenshot(path="data/debug_verify_error.png")
            except Exception:
                pass
            return StepResult(success=False, error=f"browser_verify_failed: {exc}")

        finally:
            try:
                await manager.close_session(session_id)
            except Exception:
                logger.warning(
                    "browser_cleanup_error", session_id=session_id, exc_info=True
                )
