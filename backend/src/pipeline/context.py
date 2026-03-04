"""Immutable pipeline context model."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class PipelineContext:
    """Execution context passed between steps."""

    email: str | None = None
    password: str | None = None
    phone: str | None = None
    mailbox_id: str | None = None
    verification_code: str | None = None
    access_token: str | None = None
    account_info: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> "PipelineContext":
        """Return a new context with updated key/value."""

        if hasattr(self, key):
            return replace(self, **{key: value})
        new_metadata = {**self.metadata, key: value}
        return replace(self, metadata=new_metadata)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from known fields first, then metadata."""

        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """Serialize context into dict."""

        return {
            "email": self.email,
            "password": self.password,
            "phone": self.phone,
            "mailbox_id": self.mailbox_id,
            "verification_code": self.verification_code,
            "access_token": self.access_token,
            "account_info": dict(self.account_info),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineContext":
        """Build context from dict payload."""

        payload = dict(data)
        payload.setdefault("account_info", {})
        payload.setdefault("metadata", {})
        return cls(**payload)
