"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

import uvicorn
from fastapi import APIRouter, Depends, FastAPI
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth import router as auth_router
from api.config_api import router as config_router
from api.dashboard import router as dashboard_router
from api.logs_api import router as logs_router
from api.openai_proxy import openai_proxy_error_response
from api.openai_proxy import router as openai_proxy_router
from api.devtools import api_router as devtools_api_router
from api.devtools import ws_router as devtools_ws_router
from api.pipeline_api import router as pipeline_router
from api.stats_api import router as stats_router
from api.tokens import router as tokens_router
from api.ws_logs import router as ws_logs_router
from api.ws_pipeline import api_router as pipeline_devtools_api_router
from api.ws_pipeline import ws_router as ws_pipeline_router
from src.config.settings import load_settings
from src.integrations.openai_api import OpenAIChatClient, OpenAIRegistrationClient
from src.middleware.auth import OpenAIProxyException, require_admin_token
from src.services.health_checker import HealthChecker
from src.services.token_refresher import TokenRefresher, TokenRefresherSettings
from src.storage.account_store import AccountStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    account_store = AccountStore(settings.storage.db_path, settings.storage.encryption_key)
    openai_proxy = settings.network.openai_proxy or settings.network.http_proxy
    chat_client = OpenAIChatClient(
        base_url=settings.openai.base_url,
        timeout=settings.openai.timeout_seconds,
        stream_timeout=settings.openai.stream_timeout_seconds,
        proxy=openai_proxy,
    )
    checker = HealthChecker(
        account_store=account_store,
        chat_client=chat_client,
        interval=settings.proxy.health_check_interval_seconds,
        cooldown_seconds=settings.proxy.cooldown_seconds,
        failure_threshold=settings.proxy.failure_threshold,
    )
    tasks: list[asyncio.Task[None]] = []
    checker_task = asyncio.create_task(checker.run_forever())
    app.state.health_checker_task = checker_task
    tasks.append(checker_task)

    if settings.proxy.token_refresh_enabled:
        refresher = TokenRefresher(
            account_store=account_store,
            registration_client=OpenAIRegistrationClient(
                auth_url=settings.openai.auth_url,
                oauth_client_id=settings.openai.oauth_client_id,
                timeout=settings.openai.timeout_seconds,
                proxy=openai_proxy,
            ),
            settings=TokenRefresherSettings(
                oauth_client_id=settings.openai.oauth_client_id,
                oauth_client_secret=settings.openai.oauth_client_secret,
                token_url=settings.openai.token_url,
                refresh_interval=settings.proxy.token_refresh_interval_seconds,
                skew_seconds=settings.proxy.token_refresh_skew_seconds,
                timeout=settings.proxy.token_refresh_timeout_seconds,
                max_retries=settings.proxy.token_refresh_max_retries,
                backoff_seconds=settings.proxy.token_refresh_backoff_seconds,
            ),
        )
        refresher_task = asyncio.create_task(refresher.run_forever())
        app.state.token_refresher_task = refresher_task
        tasks.append(refresher_task)

    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="register-bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

admin_router = APIRouter(dependencies=[Depends(require_admin_token)])
admin_router.include_router(dashboard_router)
admin_router.include_router(tokens_router)
admin_router.include_router(config_router)
admin_router.include_router(logs_router)
admin_router.include_router(stats_router)
admin_router.include_router(pipeline_router)
admin_router.include_router(devtools_api_router)
admin_router.include_router(pipeline_devtools_api_router)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(openai_proxy_router)
app.include_router(ws_logs_router)
app.include_router(ws_pipeline_router)
app.include_router(devtools_ws_router)


@app.exception_handler(OpenAIProxyException)
async def handle_openai_proxy_exception(
    _request: Request, exc: OpenAIProxyException
) -> JSONResponse:
    return openai_proxy_error_response(exc)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
