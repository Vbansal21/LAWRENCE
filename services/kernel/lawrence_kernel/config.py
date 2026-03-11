from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RoutingConfig(BaseModel):
    web_parallel_default: bool = True
    fast_latency_budget_ms: int = 1500
    slow_latency_budget_ms: int = 15000
    facet_timeouts_ms: dict[str, int] = Field(default_factory=dict)


class PolicyConfig(BaseModel):
    telemetry_enabled: bool = False
    require_confirmation_for_actions: bool = True
    allow_cloud_default: bool = False


class RetentionConfig(BaseModel):
    raw_ttl_minutes: int = 30
    distillation_write_interval_seconds: int = 10


class ProviderConfig(BaseModel):
    order: list[str] = Field(default_factory=lambda: ["llamacpp", "lmstudio", "gemini", "openai_compatible"])
    local_first: bool = True
    endpoints: dict[str, str] = Field(
        default_factory=lambda: {
            "lmstudio": "http://127.0.0.1:1234",
            "llamacpp": "http://127.0.0.1:8080",
            "gemini": "https://generativelanguage.googleapis.com",
            "openai_compatible": "https://api.openai.com",
        }
    )
    models: dict[str, str] = Field(
        default_factory=lambda: {
            "lmstudio": "local-model",
            "llamacpp": "local-model",
            "gemini": "gemini-1.5-flash",
            "openai_compatible": "gpt-4o-mini",
        }
    )
    timeout_seconds: float = 8.0


class IntegrationConfig(BaseModel):
    n8n_base_url: str = "http://127.0.0.1:5678"
    n8n_webhook_path: str = "/webhook/lawrence"
    workflow_paths: dict[str, str] = Field(
        default_factory=lambda: {
            "web-search": "/webhook/wf-02-web-search/webhook%2520web%2520search/lawrence/web-search",
            "zettel-ingest": "/webhook/wf-03-zettel-ingest-link/webhook%2520zettel%2520ingest/lawrence/zettel-ingest",
        }
    )


class WebConfig(BaseModel):
    provider: str = "n8n"
    max_results: int = 5


class AppConfig(BaseModel):
    name: str = "LAWRENCE"
    environment: str = "development"


class RuntimeConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    providers: ProviderConfig = Field(default_factory=ProviderConfig)
    integrations: IntegrationConfig = Field(default_factory=IntegrationConfig)
    web: WebConfig = Field(default_factory=WebConfig)


_DEFAULT_PATH = Path("config/default.yaml")


def load_config(path: Path | None = None) -> RuntimeConfig:
    cfg_path = path or _DEFAULT_PATH
    if not cfg_path.exists():
        return RuntimeConfig()
    raw: dict[str, Any] = yaml.safe_load(cfg_path.read_text()) or {}
    return RuntimeConfig(**raw)
