"""
Subdivision déterministe SRC — overflow de capacité uniquement.

Ne se déclenche PAS après timeout, erreur provider, parse failure,
ou troncature max_tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.ai.estimation import estimate_tokens
from app.file_utils import content_hash
from app.source_analysis.errors import SourceAnalysisError
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.constants import ESTIMATION_MODEL
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v2.constants import (
    CHILD_SUFFIXES,
    GRANULARITY_POLICY_VERSION,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SUBDIVISION_MAX_DEPTH,
    SUBDIVISION_MIN_OWNED_SRC,
    SUBDIVISION_POLICY_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)
from app.ai.thinking import thinking_fingerprint
from app.source_analysis_local_v2.schema import semantic_transport_v2_fingerprint
from app.source_analysis_thinking_contract.v2_config import V2_EFFORT, V2_THINKING_MODE
from app.source_analysis_local_v2.validator import v2_capacity_signaled


class LocalV2SubdivisionError(SourceAnalysisError):
    """Subdivision refusée — fail-closed."""


class LocalV2SubdivisionNotTriggered(SourceAnalysisError):
    """Demande de subdivision hors signal de capacité validé."""


@dataclass(frozen=True)
class ChildWindowSpec:
    child_id: str
    parent_id: str
    depth: int
    owned_src_refs: tuple[str, ...]
    estimated_content_tokens: int
    cache_identity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_id": self.child_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "owned_src_refs": list(self.owned_src_refs),
            "estimated_content_tokens": self.estimated_content_tokens,
            "cache_identity": self.cache_identity,
            "production_window_id": False,
        }


@dataclass(frozen=True)
class SubdivisionPlan:
    parent_id: str
    parent_owned_src_refs: tuple[str, ...]
    children: tuple[ChildWindowSpec, ...]
    depth: int
    trigger: str
    provider_retry: bool
    python_semantic_merge: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": SUBDIVISION_POLICY_VERSION,
            "parent_id": self.parent_id,
            "parent_owned_src_refs": list(self.parent_owned_src_refs),
            "children": [child.to_dict() for child in self.children],
            "depth": self.depth,
            "trigger": self.trigger,
            "provider_retry": self.provider_retry,
            "python_semantic_merge": self.python_semantic_merge,
            "coverage_complete": coverage_complete(self),
            "duplicates": 0,
            "missing": 0,
        }


def child_window_id(parent_id: str, suffix: str) -> str:
    if "." in parent_id and parent_id.rsplit(".", 1)[-1] in CHILD_SUFFIXES:
        return f"{parent_id}.{suffix}"
    return f"{parent_id}.{suffix}"


def child_depth(child_id: str) -> int:
    if "." not in child_id:
        return 0
    return child_id.count(".")


def child_cache_identity(
    *,
    parent_id: str,
    child_id: str,
    owned_src_refs: Sequence[str],
    owned_content_sha256: str,
    prompt_version: str = WINDOW_ANALYSIS_PROMPT_VERSION_V121,
    transport_version: str = SEMANTIC_TRANSPORT_VERSION_V2,
    policy_version: str = GRANULARITY_POLICY_VERSION,
    provider: str = "fake",
    model: str = "fake-model",
    max_output_tokens: int = 32000,
    schema_sha256: str | None = None,
    thinking_mode: str | None = None,
    effort: str | None = None,
) -> str:
    schema = schema_sha256 or semantic_transport_v2_fingerprint()
    payload = "\n".join(
        [
            parent_id,
            child_id,
            ",".join(owned_src_refs),
            owned_content_sha256,
            prompt_version,
            transport_version,
            policy_version,
            provider,
            model,
            str(max_output_tokens),
            schema,
            thinking_fingerprint(
                thinking_mode if thinking_mode is not None else V2_THINKING_MODE,
                effort if thinking_mode is not None else V2_EFFORT,
            ),
        ]
    )
    return content_hash(payload)


def _content_tokens(transcript: TranscriptInput, refs: Sequence[str]) -> int:
    lookup = {segment.src_id: segment for segment in transcript.segments}
    texts = []
    for ref in refs:
        segment = lookup.get(ref)
        if segment is None:
            raise LocalV2SubdivisionError(f"SRC {ref} absent du transcript")
        texts.append(segment.text)
    estimate = estimate_tokens("\n".join(texts), model=ESTIMATION_MODEL)
    return int(estimate.tokens)


def _owned_content_hash(transcript: TranscriptInput, refs: Sequence[str]) -> str:
    from app.source_analysis_hybrid.contracts import segments_content_hash

    lookup = {segment.src_id: segment for segment in transcript.segments}
    segments = []
    for ref in refs:
        segment = lookup.get(ref)
        if segment is None:
            raise LocalV2SubdivisionError(f"SRC {ref} absent du transcript")
        segments.append(segment)
    return segments_content_hash(segments)


def _best_split(token_weights: Sequence[int]) -> int:
    """Index de coupe : left = refs[:cut], right = refs[cut:]. 1..n-1."""
    total = sum(token_weights)
    best_cut = 1
    best_delta = None
    running = 0
    for cut in range(1, len(token_weights)):
        running += token_weights[cut - 1]
        delta = abs(running - (total - running))
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_cut = cut
    return best_cut


def coverage_complete(plan: SubdivisionPlan) -> bool:
    owned = list(plan.parent_owned_src_refs)
    child_refs = [ref for child in plan.children for ref in child.owned_src_refs]
    return child_refs == owned and len(child_refs) == len(set(child_refs))


def plan_subdivision(
    window: WindowInput,
    transcript: TranscriptInput,
    transport: Mapping[str, Any],
    *,
    parent_depth: int = 0,
    trigger_validated: bool,
    parse_ok: bool,
    provider_ok: bool,
    truncated: bool = False,
) -> SubdivisionPlan:
    """
    Produit un plan. N'appelle pas le provider.

    trigger_validated doit être True seulement après un transport V2
    parsé ET validé qui signale analysis_capacity_exceeded.
    """
    if not parse_ok:
        raise LocalV2SubdivisionNotTriggered(
            "parse failure — subdivision interdite"
        )
    if not provider_ok:
        raise LocalV2SubdivisionNotTriggered(
            "provider failure — subdivision interdite"
        )
    if truncated:
        raise LocalV2SubdivisionNotTriggered(
            "max_tokens truncation — subdivision interdite"
        )
    if not trigger_validated or not v2_capacity_signaled(transport):
        raise LocalV2SubdivisionNotTriggered(
            "capacité non validée — subdivision interdite"
        )
    next_depth = parent_depth + 1
    if next_depth > SUBDIVISION_MAX_DEPTH:
        raise LocalV2SubdivisionError(
            f"profondeur max {SUBDIVISION_MAX_DEPTH} atteinte "
            f"({window.window_id})"
        )
    owned = tuple(window.owned_src_refs)
    if len(owned) < SUBDIVISION_MIN_OWNED_SRC:
        raise LocalV2SubdivisionError(
            f"unité minimale : {window.window_id} n'a que {len(owned)} SRC "
            "et signale encore un overflow — fail-closed"
        )
    weights = [_content_tokens(transcript, (ref,)) for ref in owned]
    cut = _best_split(weights)
    left_refs = owned[:cut]
    right_refs = owned[cut:]
    if not left_refs or not right_refs:
        raise LocalV2SubdivisionError("coupe vide — fail-closed")
    if set(left_refs) & set(right_refs):
        raise LocalV2SubdivisionError("chevauchement SRC — fail-closed")
    children = []
    for suffix, refs in zip(CHILD_SUFFIXES, (left_refs, right_refs)):
        child_id = child_window_id(window.window_id, suffix)
        children.append(
            ChildWindowSpec(
                child_id=child_id,
                parent_id=window.window_id,
                depth=next_depth,
                owned_src_refs=refs,
                estimated_content_tokens=_content_tokens(transcript, refs),
                cache_identity=child_cache_identity(
                    parent_id=window.window_id,
                    child_id=child_id,
                    owned_src_refs=refs,
                    owned_content_sha256=_owned_content_hash(transcript, refs),
                ),
            )
        )
    plan = SubdivisionPlan(
        parent_id=window.window_id,
        parent_owned_src_refs=owned,
        children=tuple(children),
        depth=next_depth,
        trigger="analysis_capacity_exceeded",
        provider_retry=False,
        python_semantic_merge=False,
    )
    if not coverage_complete(plan):
        raise LocalV2SubdivisionError("couverture parent ≠ union enfants")
    return plan


def max_calls_under_depth(initial_windows: int, *, max_depth: int = SUBDIVISION_MAX_DEPTH) -> int:
    """Borne supérieure si chaque fenêtre overflow jusqu'à max_depth (binaire)."""
    total = 0
    level = initial_windows
    for _ in range(max_depth + 1):
        total += level
        level *= 2
    return total


def subdivision_policy_facts() -> dict[str, Any]:
    return {
        "policy_version": SUBDIVISION_POLICY_VERSION,
        "trigger": "valid parsed V2 transport with analysis_capacity_exceeded",
        "does_not_trigger_on": [
            "timeout",
            "provider envelope error",
            "structured parse failure",
            "max_tokens truncation",
        ],
        "algorithm": (
            "split owned SRC on present boundaries, balanced by "
            "owned-content token estimate, no overlap, no missing"
        ),
        "child_id_scheme": "WIN001.A / WIN001.B — not a production WindowInput id",
        "collides_with_top_level_win": False,
        "max_depth": SUBDIVISION_MAX_DEPTH,
        "minimum_unit_owned_src": SUBDIVISION_MIN_OWNED_SRC,
        "minimum_unit_fail_closed": True,
        "provider_retry": False,
        "python_semantic_merge": False,
        "ai_semantic_merge": True,
        "child_results_are_local_intermediates": True,
        "child_consolidation": (
            "Prefer reuse of regional/global consolidation after children "
            "are READY. Python may concatenate/account structurally only. "
            "This phase generates the plan offline and does not execute "
            "child provider calls."
        ),
        "max_calls_one_window_full_depth": max_calls_under_depth(1),
        "real_authorization": False,
    }


__all__ = [
    "ChildWindowSpec",
    "LocalV2SubdivisionError",
    "LocalV2SubdivisionNotTriggered",
    "SubdivisionPlan",
    "child_cache_identity",
    "child_depth",
    "child_window_id",
    "coverage_complete",
    "max_calls_under_depth",
    "plan_subdivision",
    "subdivision_policy_facts",
]
