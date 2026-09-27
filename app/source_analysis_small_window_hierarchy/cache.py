"""
Cache identity for windows / regional groups / global consolidation.

A WIN001 label is never sufficient. Route change invalidates consolidation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence

from app.file_utils import content_hash
from app.source_analysis.consolidation_models import ConsolidationInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_small_window_hierarchy.constants import (
    CANDIDATE_PLANNER_VERSION,
    REGIONAL_CONTRACT_VERSION,
    WINDOW_CONTENT_BINDING,
)
from app.source_analysis_small_window_hierarchy.regional import RegionalSemanticResult


def document_window_content_binding() -> dict[str, str]:
    return {
        "approach": WINDOW_CONTENT_BINDING,
        "window_input_hash_fields": (
            "planner_version, window_id, owned SRC ids, context SRC ids, "
            "owned_content_sha256, context_content_sha256"
        ),
        "analysis_signature_includes_window_input_hash": "yes",
        "win001_label_sufficient": "no",
        "planner_version_only_sufficient": "no",
        "old_3_window_win001_can_collide_with_small_win001": "no",
    }


def window_content_binding_digest(window: WindowInput) -> str:
    """Explicit extra binding — content + ownership, not the label."""
    payload = {
        "owned_content_sha256": window.owned_content_sha256,
        "owned_src_ids_sha256": window.owned_src_ids_sha256,
        "context_content_sha256": window.context_content_sha256,
        "context_src_ids_sha256": window.context_src_ids_sha256,
        "owned_src_refs": list(window.owned_src_refs),
        "context_src_refs": list(window.context_src_refs),
        "planner_version": window.planner_version,
        "window_input_hash": window.input_hash,
    }
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


@dataclass(frozen=True)
class RegionalCacheIdentity:
    group_id: str
    member_window_ids: tuple[str, ...]
    member_window_input_hashes: tuple[str, ...]
    member_window_result_hashes: tuple[str, ...]
    member_window_signatures: tuple[str, ...]
    regional_input_hash: str
    contract_version: str
    prompt_version: str
    provider: str
    model: str
    max_output_tokens: int | None

    def digest(self) -> str:
        payload = {
            "contract_version": self.contract_version,
            "group_id": self.group_id,
            "max_output_tokens": self.max_output_tokens,
            "member_window_ids": list(self.member_window_ids),
            "member_window_input_hashes": list(self.member_window_input_hashes),
            "member_window_result_hashes": list(self.member_window_result_hashes),
            "member_window_signatures": list(self.member_window_signatures),
            "model": self.model,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "regional_input_hash": self.regional_input_hash,
        }
        return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


@dataclass(frozen=True)
class GlobalCacheIdentity:
    route: str
    input_hash: str
    source_result_hashes: tuple[str, ...]
    prompt_version: str
    provider: str
    model: str
    max_output_tokens: int | None

    def digest(self) -> str:
        payload = {
            "input_hash": self.input_hash,
            "max_output_tokens": self.max_output_tokens,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "route": self.route,
            "source_result_hashes": list(self.source_result_hashes),
        }
        return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def regional_cache_identity(
    group_id: str,
    windows: Sequence[WindowInput],
    results: Sequence,
    regional_input: ConsolidationInput,
    *,
    provider: str,
    model: str,
    max_output_tokens: int | None,
    prompt_version: str = REGIONAL_CONTRACT_VERSION,
) -> RegionalCacheIdentity:
    by_id = {result.window_id: result for result in results}
    ordered = [by_id[window.window_id] for window in windows]
    return RegionalCacheIdentity(
        group_id=group_id,
        member_window_ids=tuple(window.window_id for window in windows),
        member_window_input_hashes=tuple(window.input_hash for window in windows),
        member_window_result_hashes=tuple(item.result_sha256() for item in ordered),
        member_window_signatures=tuple(
            item.window_analysis_signature for item in ordered
        ),
        regional_input_hash=regional_input.input_hash,
        contract_version=REGIONAL_CONTRACT_VERSION,
        prompt_version=prompt_version,
        provider=provider,
        model=model,
        max_output_tokens=max_output_tokens,
    )


def global_cache_identity(
    route: str,
    consolidation_input: ConsolidationInput,
    *,
    source_hashes: Sequence[str],
    provider: str,
    model: str,
    max_output_tokens: int | None,
    prompt_version: str,
) -> GlobalCacheIdentity:
    return GlobalCacheIdentity(
        route=route,
        input_hash=consolidation_input.input_hash,
        source_result_hashes=tuple(source_hashes),
        prompt_version=prompt_version,
        provider=provider,
        model=model,
        max_output_tokens=max_output_tokens,
    )


def identities_differ_for_same_label(
    left: WindowInput,
    right: WindowInput,
) -> bool:
    """True when WIN001 labels match but content/ownership do not."""
    if left.window_id != right.window_id:
        return True
    return (
        left.input_hash != right.input_hash
        or left.owned_content_sha256 != right.owned_content_sha256
        or left.planner_version != right.planner_version
        or window_content_binding_digest(left)
        != window_content_binding_digest(right)
    )


__all__ = [
    "CANDIDATE_PLANNER_VERSION",
    "GlobalCacheIdentity",
    "RegionalCacheIdentity",
    "document_window_content_binding",
    "global_cache_identity",
    "identities_differ_for_same_label",
    "regional_cache_identity",
    "window_content_binding_digest",
]
