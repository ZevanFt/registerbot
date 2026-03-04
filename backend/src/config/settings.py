"""Application settings loader backed by pydantic-settings and YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class TalentMailSettings(BaseModel):
    """TalentMail API settings."""

    base_url: str = "http://localhost/api"
    email: str = ""
    password: str = ""


class OpenAISettings(BaseModel):
    """OpenAI registration endpoint settings."""

    register_url: str = "https://chat.openai.com"
    auth_url: str = "https://auth.openai.com"
    authorize_url: str = "https://auth.openai.com/oauth/authorize"
    register_callback_url: str = "http://localhost:1455/auth/callback"
    turnstile_sitekey: str = ""
    default_password: str = ""
    base_url: str = "https://api.openai.com"
    token_url: str = "https://auth.openai.com/oauth/token"
    oauth_client_id: str = "app_EMoamEEZ73f0CkXaXp7hrann"
    oauth_client_secret: str = ""
    timeout_seconds: float = 120.0
    stream_timeout_seconds: float = 300.0


class RegistrationSettings(BaseModel):
    """Registration automation behavior settings."""

    skip_phone_verification: bool = True
    skip_upgrade_plus: bool = True
    profile_name: str = "API User"
    max_concurrent_registrations: int = 1
    headless: bool = True
    browser_timeout: int = 30
    typing_delay_ms: int = 150
    navigation_timeout: int = 60


class ProxySettings(BaseModel):
    """Proxy runtime behavior settings."""

    cooldown_seconds: int = 60
    failure_threshold: int = 3
    health_check_interval_seconds: int = 30
    token_refresh_enabled: bool = True
    token_refresh_interval_seconds: int = 30
    token_refresh_skew_seconds: int = 300
    token_refresh_timeout_seconds: float = 15.0
    token_refresh_max_retries: int = 3
    token_refresh_backoff_seconds: int = 60


class NetworkSettings(BaseModel):
    """Outbound network proxy settings."""

    http_proxy: str = ""
    openai_proxy: str = ""
    talentmail_proxy: str = ""


class StorageSettings(BaseModel):
    """Persistence settings."""

    db_path: str = "data/accounts.db"
    tokens_db_path: str = "data/tokens.db"
    stats_db_path: str = "data/stats.db"
    encryption_key: str = ""


class LoggingSettings(BaseModel):
    """Logging settings."""

    level: str = "INFO"
    format: str = "json"


class AdminSettings(BaseModel):
    """Admin panel authentication settings."""

    username: str = "admin"
    password: str = "admin123"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 24


class YamlSettingsSource(PydanticBaseSettingsSource):
    """YAML-based settings source for BaseSettings."""

    def __init__(self, settings_cls: type[BaseSettings], yaml_path: Path) -> None:
        super().__init__(settings_cls)
        self._yaml_path = yaml_path

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if not self._yaml_path.exists():
            return {}
        with self._yaml_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        if not isinstance(payload, dict):
            raise ValueError("config/settings.yaml must be a mapping")
        return payload


class Settings(BaseSettings):
    """Top-level application settings."""

    talentmail: TalentMailSettings = Field(default_factory=TalentMailSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    registration: RegistrationSettings = Field(default_factory=RegistrationSettings)
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    admin: AdminSettings = Field(default_factory=AdminSettings)

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="REGISTER_BOT_",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_source = YamlSettingsSource(settings_cls, Path("config/settings.yaml"))
        return init_settings, env_settings, yaml_source, dotenv_settings, file_secret_settings


def load_settings() -> Settings:
    """Load and validate application settings."""

    return Settings()


def save_settings(settings_dict: dict) -> None:
    """Persist settings payload to YAML file."""

    path = Path("config/settings.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(settings_dict, handle, allow_unicode=True, default_flow_style=False)
