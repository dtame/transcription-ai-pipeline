"""Sélection offline représentative WIN002–WIN007. 0 réseau. Préfère WIN004."""

from __future__ import annotations

import re
from statistics import median
from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_local_v3.prompt import estimate_v131_request_tokens
from app.source_analysis_small_window_hierarchy.planner import plan_windows_v21_small
from app.source_analysis_small_window_readiness.constants import A7_EXPECTED_WINDOWS
from app.source_analysis_v3_second_window.constants import (
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    CANDIDATE_WINDOW_IDS,
    FALLBACK_ORDER,
    MODE,
    PHASE,
    PREFERRED_WINDOW_ID,
    SCHEMA_VERSION,
)
from app.source_analysis_v3_second_window.guard import SecondWindowError

_FRENCH_MARKERS = (
    "le",
    "la",
    "les",
    "des",
    "une",
    "est",
    "pas",
    "nous",
    "vous",
    "dans",
    "pour",
    "avec",
    "que",
    "qui",
    "c'est",
    "n'est",
)
_ENGLISH_MARKERS = (
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "have",
    "not",
    "you",
    "god",
    "faith",
    "because",
)
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ']+")


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(median(values))


def _language_distribution(text: str) -> dict[str, Any]:
    tokens = [token.lower() for token in _WORD_RE.findall(text)]
    total = len(tokens)
    french = sum(1 for token in tokens if token in _FRENCH_MARKERS)
    english = sum(1 for token in tokens if token in _ENGLISH_MARKERS)
    return {
        "token_count": total,
        "french_marker_count": french,
        "english_marker_count": english,
        "french_marker_share": round(french / total, 6) if total else 0.0,
        "english_marker_share": round(english / total, 6) if total else 0.0,
        "primary_guess": (
            "fr"
            if french > english * 1.5 and french > 20
            else "en"
            if english or total
            else "unknown"
        ),
    }


def _structural_anomalies(
    window: WindowInput,
    transcript: TranscriptInput,
    owned_text: str,
) -> list[str]:
    anomalies: list[str] = []
    if window.word_count <= 0 or not owned_text.strip():
        anomalies.append("empty_or_zero_word_window")
    owned = set(window.owned_src_refs)
    present = [
        segment
        for segment in transcript.segments
        if segment.src_id in owned
    ]
    empty = sum(1 for segment in present if not str(segment.text or "").strip())
    if present and empty / len(present) > 0.20:
        anomalies.append("high_empty_src_share")
    if window.owned_src_count <= 0:
        anomalies.append("zero_owned_src")
    if window.context_src_count != 0:
        anomalies.append("unexpected_context_src")
    if not window.owned_src_refs:
        anomalies.append("missing_owned_src_refs")
    return anomalies


def inspect_window(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    position: int,
    total_windows: int,
) -> dict[str, Any]:
    content = materialize_window_content(transcript, window)
    estimate = estimate_v131_request_tokens(transcript, window, content=content)
    local = int(estimate["total_tokens"])
    owned_text = " ".join(
        segment.text
        for segment in transcript.segments
        if segment.src_id in set(window.owned_src_refs)
    )
    language = _language_distribution(owned_text)
    density = (
        round(float(window.word_count) / float(window.owned_src_count), 6)
        if window.owned_src_count
        else 0.0
    )
    relative = position / total_windows if total_windows else 0.0
    plan_row = next(
        (
            item
            for item in A7_EXPECTED_WINDOWS
            if item["window_id"] == window.window_id
        ),
        None,
    )
    anomalies = _structural_anomalies(window, transcript, owned_text)
    if window.window_id == "WIN007":
        anomalies.append("terminal_window")
    size_band = "normal"
    return {
        "window_id": window.window_id,
        "src_range": f"{window.first_owned_src_ref} → {window.last_owned_src_ref}",
        "first_owned_src_ref": window.first_owned_src_ref,
        "last_owned_src_ref": window.last_owned_src_ref,
        "owned_src_count": window.owned_src_count,
        "word_count": window.word_count,
        "local_token_estimate": local,
        "planner_estimate_tokens": window.planner_estimate_tokens,
        "relative_position": position,
        "total_windows": total_windows,
        "relative_fraction": round(relative, 6),
        "region": (
            "beginning"
            if relative <= 0.34
            else "end"
            if relative >= 0.76
            else "middle"
        ),
        "language_distribution": language,
        "source_density_words_per_src": density,
        "structural_anomalies": anomalies,
        "representative_of_normal_size": True,
        "size_band": size_band,
        "plan_row": plan_row,
        "input_hash": window.input_hash,
        "owned_content_sha256": window.owned_content_sha256,
        "context_src_count": window.context_src_count,
        "within_35000": local <= CANDIDATE_HARD_MAX_INPUT_TOKENS,
        "independent_of_win001": window.window_id != "WIN001",
    }


def atypical_reasons(
    row: Mapping[str, Any],
    cohort: list[Mapping[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    peers = [
        item
        for item in cohort
        if item.get("window_id") != row.get("window_id")
    ]
    word_med = _median([float(item["word_count"]) for item in peers] or [1.0])
    owned_med = _median([float(item["owned_src_count"]) for item in peers] or [1.0])
    local_med = _median(
        [float(item["local_token_estimate"]) for item in peers] or [1.0]
    )
    density_med = _median(
        [float(item["source_density_words_per_src"]) for item in peers] or [1.0]
    )
    words = float(row["word_count"])
    owned = float(row["owned_src_count"])
    local = float(row["local_token_estimate"])
    density = float(row["source_density_words_per_src"])
    if word_med and abs(words - word_med) / word_med > 0.25:
        reasons.append("word_count_substantially_off_median")
    if owned_med and abs(owned - owned_med) / owned_med > 0.25:
        reasons.append("owned_src_count_substantially_off_median")
    if local_med and abs(local - local_med) / local_med > 0.25:
        reasons.append("local_estimate_substantially_off_median")
    if density_med and abs(density - density_med) / density_med > 0.35:
        reasons.append("abnormal_source_density")
    if local > CANDIDATE_HARD_MAX_INPUT_TOKENS:
        reasons.append("local_estimate_exceeds_35000")
    language = row.get("language_distribution") or {}
    peer_primary = [
        (item.get("language_distribution") or {}).get("primary_guess")
        for item in peers
    ]
    if (
        language.get("primary_guess")
        and peer_primary
        and language.get("primary_guess") != "en"
        and peer_primary.count("en") >= max(1, len(peer_primary) - 1)
        and language.get("french_marker_share", 0) > 0.08
    ):
        reasons.append("unusual_language_composition")
    material = [
        item
        for item in (row.get("structural_anomalies") or [])
        if item != "terminal_window"
    ]
    reasons.extend(material)
    return reasons


def select_representative_window(
    transcript: TranscriptInput,
) -> dict[str, Any]:
    plan = plan_windows_v21_small(transcript)
    by_id = {item.window_id: item for item in plan.windows}
    missing = [window_id for window_id in CANDIDATE_WINDOW_IDS if window_id not in by_id]
    if missing:
        raise SecondWindowError(
            "Candidate windows missing from v2.1-small plan: "
            + ", ".join(missing)
        )
    total = len(plan.windows)
    inspections: list[dict[str, Any]] = []
    for index, window in enumerate(plan.windows, start=1):
        if window.window_id not in CANDIDATE_WINDOW_IDS:
            continue
        row = inspect_window(
            window, transcript, position=index, total_windows=total
        )
        inspections.append(row)
    if not inspections:
        raise SecondWindowError("No independent candidate windows available.")
    for row in inspections:
        reasons = atypical_reasons(row, inspections)
        row["atypical_reasons"] = reasons
        row["materially_atypical"] = bool(reasons)
        row["representative_of_normal_size"] = not any(
            reason.startswith("word_count")
            or reason.startswith("owned_src")
            or reason.startswith("local_estimate")
            for reason in reasons
        )

    preferred = next(
        item for item in inspections if item["window_id"] == PREFERRED_WINDOW_ID
    )
    selected = preferred
    selection_reason = (
        "WIN004 is the preferred independent middle-region window of the "
        "7-window v2.1-small plan. Offline metrics are within the normal "
        "cohort range. Semantic difference from WIN001 is expected and "
        "is not a rejection criterion."
    )
    if preferred["materially_atypical"]:
        selected = None
        for window_id in FALLBACK_ORDER:
            candidate = next(
                item for item in inspections if item["window_id"] == window_id
            )
            if not candidate["materially_atypical"]:
                selected = candidate
                selection_reason = (
                    f"WIN004 is materially atypical "
                    f"({', '.join(preferred['atypical_reasons'])}). "
                    f"Deterministic fallback selected {window_id}."
                )
                break
        if selected is None:
            raise SecondWindowError(
                "No representative independent middle-region window can be "
                "safely selected. BLOCKED_PRECALL."
            )
    if selected["window_id"] == "WIN001":
        raise SecondWindowError("Selection resolved to WIN001 — forbidden.")
    if not selected["within_35000"]:
        raise SecondWindowError(
            f"{selected['window_id']} local estimate exceeds 35000. "
            "BLOCKED_PRECALL."
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "preferred_window_id": PREFERRED_WINDOW_ID,
        "fallback_order": list(FALLBACK_ORDER),
        "candidate_windows": inspections,
        "selected_window_id": selected["window_id"],
        "selection_reason": selection_reason,
        "win004_used": selected["window_id"] == PREFERRED_WINDOW_ID,
        "win004_atypical_reasons": preferred["atypical_reasons"],
        "selected": selected,
        "provider_quality_guess_used": False,
        "semantic_difference_from_win001_is_desirable": True,
        "win001_rejected": True,
        "provider_calls": 0,
    }


__all__ = [
    "atypical_reasons",
    "inspect_window",
    "select_representative_window",
]
