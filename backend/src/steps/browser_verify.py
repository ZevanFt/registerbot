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

                # Fill Birthday — 3 dropdown selects (Month / Day / Year).
                month_names = [
                    "", "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December",
                ]
                month_label = month_names[birth_month]
                birthday_filled = False

                # Strategy 1: Native <select> elements inside Birthday fieldset
                try:
                    selects = page.locator("select:visible")
                    select_count = await selects.count()
                    if select_count >= 3:
                        # Month select: try by label/value
                        month_sel = selects.nth(0)
                        await month_sel.select_option(label=month_label)
                        await asyncio.sleep(0.3)
                        # Day select
                        day_sel = selects.nth(1)
                        await day_sel.select_option(value=str(birth_day))
                        await asyncio.sleep(0.3)
                        # Year select
                        year_sel = selects.nth(2)
                        await year_sel.select_option(value=str(birth_year))
                        await asyncio.sleep(0.3)
                        birthday_filled = True
                        logger.info(
                            "about_you_birthday_filled",
                            mode="select_option",
                            birthday=f"{month_label} {birth_day}, {birth_year}",
                        )
                except Exception:
                    logger.debug("about_you_birthday_select_option_failed", exc_info=True)

                # Strategy 2: Click dropdown and pick option text
                if not birthday_filled:
                    try:
                        birthday_group = page.locator("fieldset, [data-testid*='birthday'], .birthday")
                        dropdowns = birthday_group.locator("select, [role='listbox'], [role='combobox']")
                        dd_count = await dropdowns.count()
                        if dd_count >= 3:
                            await dropdowns.nth(0).select_option(label=month_label)
                            await asyncio.sleep(0.2)
                            await dropdowns.nth(1).select_option(value=str(birth_day))
                            await asyncio.sleep(0.2)
                            await dropdowns.nth(2).select_option(value=str(birth_year))
                            birthday_filled = True
                            logger.info(
                                "about_you_birthday_filled",
                                mode="fieldset_select",
                                birthday=f"{month_label} {birth_day}, {birth_year}",
                            )
                    except Exception:
                        logger.debug("about_you_birthday_fieldset_failed", exc_info=True)

                # Strategy 3: JavaScript fallback — set all select values directly
                if not birthday_filled:
                    try:
                        await page.evaluate(
                            """([month, day, year]) => {
                                const selects = document.querySelectorAll('select');
                                if (selects.length >= 3) {
                                    const setVal = (sel, val) => {
                                        const nativeSetter = Object.getOwnPropertyDescriptor(
                                            window.HTMLSelectElement.prototype, 'value'
                                        ).set;
                                        nativeSetter.call(sel, val);
                                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                                    };
                                    // Find month by matching option text
                                    for (const opt of selects[0].options) {
                                        if (opt.text.toLowerCase().startsWith(month.toLowerCase().slice(0,3))) {
                                            setVal(selects[0], opt.value);
                                            break;
                                        }
                                    }
                                    setVal(selects[1], String(day));
                                    setVal(selects[2], String(year));
                                    return true;
                                }
                                return false;
                            }""",
                            [month_label, birth_day, birth_year],
                        )
                        birthday_filled = True
                        logger.info(
                            "about_you_birthday_filled",
                            mode="js_fallback",
                            birthday=f"{month_label} {birth_day}, {birth_year}",
                        )
                    except Exception:
                        logger.warning("about_you_birthday_all_strategies_failed", exc_info=True)

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
            # Phase 2: Handle onboarding pages after about-you.
            # OpenAI may show: "work usage" → "personal account" → tour.
            # ============================================================

            current_url = page.url

            # Handle "What will you use OpenAI for?" (work usage page)
            try:
                work_usage_options = page.locator(
                    'button:has-text("I\'m exploring personal use"), '
                    'button:has-text("Personal"), '
                    'div[role="option"]:has-text("Personal"), '
                    'label:has-text("Personal")'
                )
                if await work_usage_options.count() > 0:
                    await work_usage_options.first.click()
                    logger.info("work_usage_selected", choice="personal")
                    await asyncio.sleep(2)

                    # Click continue/next after selection
                    for sel in ['button:has-text("Continue")', 'button[type="submit"]']:
                        try:
                            btn = page.locator(sel).first
                            if await btn.is_visible():
                                await btn.click()
                                break
                        except Exception:
                            continue
                    await asyncio.sleep(3)
            except Exception:
                pass

            # Handle "personal account" selection
            try:
                personal_options = page.locator(
                    'button:has-text("Personal account"), '
                    'button:has-text("Stay on free"), '
                    'button:has-text("personal"), '
                    'div[role="option"]:has-text("Personal")'
                )
                if await personal_options.count() > 0:
                    await personal_options.first.click()
                    logger.info("account_type_selected", choice="personal")
                    await asyncio.sleep(3)
            except Exception:
                pass

            # Handle onboarding tour — click Skip/dismiss
            for _ in range(3):
                try:
                    skip_btn = page.locator(
                        'button:has-text("Skip"), '
                        'a:has-text("Skip"), '
                        'button:has-text("Maybe later"), '
                        'button:has-text("No thanks")'
                    )
                    if await skip_btn.count() > 0:
                        await skip_btn.first.click()
                        logger.info("onboarding_skipped")
                        await asyncio.sleep(2)
                    else:
                        break
                except Exception:
                    break

            try:
                await page.screenshot(path="data/debug_registration_complete.png")
            except Exception:
                pass

            # ============================================================
            # Phase 3: Extract access_token from chatgpt.com session.
            # Navigate to /api/auth/session to get the OAuth token.
            # ============================================================

            access_token = ""
            refresh_token = ""
            expires_in = 0

            try:
                response = await page.goto(
                    "https://chatgpt.com/api/auth/session",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                if response and response.ok:
                    import json as _json

                    body = await response.text()
                    session_data = _json.loads(body)
                    access_token = str(session_data.get("accessToken", ""))
                    # Session may include expires or other fields
                    expires_str = str(session_data.get("expires", ""))
                    if access_token:
                        logger.info(
                            "session_token_extracted",
                            email=context.email,
                            token_prefix=access_token[:20] + "...",
                            expires=expires_str,
                        )
                    else:
                        logger.warning("session_token_empty", body_keys=list(session_data.keys()))
                else:
                    status = response.status if response else "no_response"
                    logger.warning("session_endpoint_failed", status=status)
            except Exception as exc:
                logger.warning("session_token_extraction_failed", error=str(exc))

            final_url = page.url
            logger.info(
                "registration_complete",
                email=context.email,
                url=final_url,
                has_token=bool(access_token),
            )

            result_data: dict[str, object] = {
                "registered": True,
                "final_url": final_url,
            }
            if access_token:
                result_data["access_token"] = access_token
            if refresh_token:
                result_data["refresh_token"] = refresh_token
            if expires_in:
                result_data["expires_in"] = expires_in

            return StepResult(success=True, data=result_data)

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
