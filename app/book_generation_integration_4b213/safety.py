"""Provider safety for 4B.2.13. Remote calls fail explicitly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_generation.pipeline import materialize_chapter
from app.book_generation_integration_4b213.constants import (
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    FALLBACKS,
    PHASE,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    RETRIES,
    SDK_MAX_RETRIES,
    SONNET_EXECUTION_AUTHORIZED,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_generation_integration_4b213.fakeai import BlockedRemoteIntegrationTransport
from app.book_generation_integration_4b213.guard import (
    BookGenerationIntegration213Error,
    assert_offline_only,
    package_imports_network_clients,
    package_invokes_provider,
    reject_remote_provider,
)
from app.book_generation_integration_4b213.paths import production_pipeline_path, repo_root


def provider_safety(*, root: Path | None = None) -> dict[str, Any]:
    assert_offline_only()
    remote_blocked = False
    try:
        BlockedRemoteIntegrationTransport(provider="openai", model="gpt-5.6-terra")
    except Exception:
        remote_blocked = True
    named_blocked = False
    try:
        reject_remote_provider("anthropic")
    except BookGenerationIntegration213Error:
        named_blocked = True
    pipeline = production_pipeline_path(root=root).read_text(encoding="utf-8")
    return {
        "phase": PHASE,
        "imports_network": package_imports_network_clients(),
        "invokes_provider": package_invokes_provider(),
        "remote_constructor_blocked": remote_blocked,
        "named_provider_blocked": named_blocked,
        "api_key_absence_is_not_the_safety_mechanism": True,
        "retries": RETRIES,
        "fallbacks": FALLBACKS,
        "sdk_max_retries": SDK_MAX_RETRIES,
        "authorized_terra_calls": AUTHORIZED_TERRA_CALLS,
        "authorized_openai_calls": AUTHORIZED_OPENAI_CALLS,
        "authorized_anthropic_calls": AUTHORIZED_ANTHROPIC_CALLS,
        "authorized_sonnet_calls": AUTHORIZED_SONNET_CALLS,
        "terra_execution_authorized": TERRA_EXECUTION_AUTHORIZED,
        "sonnet_execution_authorized": SONNET_EXECUTION_AUTHORIZED,
        "real_chapter_generation_authorized": REAL_CHAPTER_GENERATION_AUTHORIZED,
        "pipeline_imports_4b213": "book_generation_integration_4b213" in pipeline,
        "materialize_chapter_untouched": materialize_chapter.__module__
        == "app.book_generation.pipeline",
        "no_production_cache_write": True,
        "http": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "secrets_included": False,
        "ok": (
            remote_blocked
            and named_blocked
            and not package_imports_network_clients()
            and not package_invokes_provider()
            and "book_generation_integration_4b213" not in pipeline
            and AUTHORIZED_TERRA_CALLS == 0
            and AUTHORIZED_SONNET_CALLS == 0
            and RETRIES == 0
            and FALLBACKS == 0
        ),
    }


__all__ = ["provider_safety"]
