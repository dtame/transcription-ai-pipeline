"""Portes pré-publication A.49. Lecture A.48. 0 régénération sémantique."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from app.source_analysis.models import SourceMap, scan_editorial_structure
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import validate_published_payload, validate_source_map
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    a46_intent_text,
    verify_a46_identity,
)
from app.source_analysis_v31_global_a47_contract_forensics.replay import load_a46_inventory
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    A46_INTENT_LENGTH,
    A48_STATUS_PRESERVED,
    EXPECTED_IDEA,
    GLOBAL_INTENT_MAX_CHARS,
    PROJECT_NAME,
)
from app.source_analysis_v31_global_a49_source_map_publication.identity import (
    bytes_identity,
)
from app.source_analysis_v31_global_a49_source_map_publication.paths import (
    a48_candidate_path,
    a48_publication_path,
    a48_semantic_path,
    a48_technical_path,
)
from app.source_analysis_v31_global_reuse_output.reconstruct import local_idea_text


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_a48_publication_eligible(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> str:
    payload = _load_json(a48_publication_path(project_name, sortie_dir=sortie_dir))
    value = payload.get("PUBLICATION_ELIGIBLE") or payload.get("publication_eligible")
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    text = str(value or "").strip().upper()
    return text if text in {"YES", "NO"} else "MISSING"


def read_a48_semantic_status(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> str:
    payload = _load_json(a48_semantic_path(project_name, sortie_dir=sortie_dir))
    return str(payload.get("status") or "").upper() or "MISSING"


def locate_validated_candidate(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    path = a48_candidate_path(project_name, sortie_dir=sortie_dir)
    if not path.is_file():
        raise FileNotFoundError(
            "Candidat A.48 introuvable — publication bloquée : " + str(path)
        )
    return path


def _intent_from_payload(payload: Mapping[str, Any]) -> str:
    header = payload.get("source_analysis") or {}
    if not isinstance(header, Mapping):
        return ""
    author_intent = header.get("author_intent") or {}
    if not isinstance(author_intent, Mapping):
        return ""
    return str(author_intent.get("summary") or "")


def _idea_summaries(payload: Mapping[str, Any]) -> list[str]:
    ideas = payload.get("ideas") or []
    if not isinstance(ideas, list):
        return []
    summaries: list[str] = []
    for idea in ideas:
        if isinstance(idea, Mapping):
            summaries.append(str(idea.get("summary") or ""))
    return summaries


def _local_idea_texts(inventory: Mapping[str, Any]) -> list[str]:
    ids = list(inventory.get("idea_input_ids") or [])
    return [local_idea_text(inventory, str(item)) for item in ids]


def _inventory_counts(payload: Mapping[str, Any]) -> dict[str, int]:
    stats = payload.get("stats") if isinstance(payload.get("stats"), Mapping) else {}
    def _len(key: str) -> int:
        value = payload.get(key)
        return len(value) if isinstance(value, list) else 0

    relations = 0
    for idea in payload.get("ideas") or []:
        if isinstance(idea, Mapping) and isinstance(idea.get("relations"), list):
            relations += len(idea.get("relations") or [])
    return {
        "topics": int(stats.get("topic_count") or _len("topics")),
        "ideas": int(stats.get("idea_count") or _len("ideas")),
        "examples": int(stats.get("example_count") or _len("examples")),
        "references": int(stats.get("reference_count") or _len("references")),
        "uncertainties": int(stats.get("uncertainty_count") or _len("uncertainties")),
        "repetitions": int(stats.get("repetition_count") or _len("repetitions")),
        "relations": relations,
        "source_refs": int(stats.get("referenced_source_segments") or 0),
    }


def validate_candidate_payload(
    payload: Mapping[str, Any],
    transcript: TranscriptInput,
) -> dict[str, Any]:
    parse_ok = isinstance(payload, Mapping) and bool(payload)
    structural = scan_editorial_structure(dict(payload))
    model_ok = False
    model_error = ""
    source_map = None
    try:
        source_map = SourceMap.from_dict(payload)
        model_ok = True
    except Exception as exc:  # noqa: BLE001 — candidate arbitraire
        model_error = f"{type(exc).__name__}: {exc}"
    canonical_errors = validate_published_payload(payload, transcript)
    if source_map is not None:
        canonical_errors = list(canonical_errors) or list(
            validate_source_map(source_map, transcript)
        )
    canonical_ok = not canonical_errors
    idea_src_ok = False
    if source_map is not None:
        idea_src_ok = all(idea.source_refs for idea in source_map.ideas)
    return {
        "json_object": parse_ok,
        "model_load": _status(model_ok),
        "model_error": model_error,
        "canonical_validation": _status(canonical_ok),
        "canonical_errors": list(canonical_errors)[:12],
        "structural": structural,
        "structural_scan": structural.get("status"),
        "forbidden_editorial_structure": "NO" if structural.get("ok") else "YES",
        "traceability": _status(canonical_ok and idea_src_ok),
        "idea_src": _status(idea_src_ok) if model_ok else "FAIL",
        "source_map": source_map,
        "inventory": _inventory_counts(payload),
    }


def evaluate_prepublication_gate(
    candidate_bytes: bytes,
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
    pastoral_contract: bool = True,
    publication_eligible: str | None = None,
    transcript: TranscriptInput | None = None,
) -> dict[str, Any]:
    identity = bytes_identity(candidate_bytes)
    payload = identity.get("payload") or {}
    if publication_eligible is not None:
        eligible = str(publication_eligible).strip().upper()
    else:
        eligible = read_a48_publication_eligible(project_name, sortie_dir=sortie_dir)
    semantic = (
        read_a48_semantic_status(project_name, sortie_dir=sortie_dir)
        if pastoral_contract
        else "PASS"
    )
    technical = (
        _load_json(a48_technical_path(project_name, sortie_dir=sortie_dir))
        if pastoral_contract
        else {}
    )
    if pastoral_contract:
        raw_identity = verify_a46_identity(project_name, sortie_dir=sortie_dir)
        transcript = transcript or load_clean_transcript(
            project_name, sortie_dir=sortie_dir
        )
        expected_intent = a46_intent_text(project_name, sortie_dir=sortie_dir)
    else:
        raw_identity = {
            "ok": True,
            "raw_response_hash": "fixture",
            "recomputed_raw_text_hash": "fixture",
        }
        expected_intent = _intent_from_payload(payload)
    if transcript is not None:
        validation = validate_candidate_payload(payload, transcript)
    else:
        structural = scan_editorial_structure(dict(payload) if payload else {})
        parse_ok = identity.get("json_parse") == "PASS" and bool(payload)
        model_ok = False
        if parse_ok:
            try:
                SourceMap.from_dict(payload)
                model_ok = True
            except Exception:  # noqa: BLE001
                model_ok = False
        validation = {
            "json_object": parse_ok,
            "model_load": _status(model_ok),
            "model_error": "",
            "canonical_validation": "FAIL" if not parse_ok or not model_ok else "PASS",
            "canonical_errors": [] if parse_ok else ["candidate JSON illisible"],
            "structural": structural,
            "structural_scan": structural.get("status"),
            "forbidden_editorial_structure": "NO" if structural.get("ok") else "YES",
            "traceability": "FAIL" if not parse_ok or not model_ok else "PASS",
            "idea_src": "FAIL" if not parse_ok else "PASS",
            "inventory": _inventory_counts(payload),
        }
    intent = _intent_from_payload(payload)
    intent_ok = (
        len(intent) == A46_INTENT_LENGTH
        and GLOBAL_INTENT_MAX_CHARS == 320
        and intent == expected_intent
    )
    ideas = _idea_summaries(payload)
    reuse_ok = False
    accountability = f"{len(ideas)} / {len(ideas)}" if ideas else "0 / 0"
    if pastoral_contract:
        a48_reuse = (
            technical.get("reuse_text_audit")
            if isinstance(technical.get("reuse_text_audit"), dict)
            else {}
        )
        reuse_ok = len(ideas) == EXPECTED_IDEA and (
            a48_reuse.get("all_canonical_equals_local") is True
            or int(technical.get("keep_count") or 0) == EXPECTED_IDEA
        )
        if not reuse_ok:
            inventory = load_a46_inventory(project_name, sortie_dir=sortie_dir)
            local_texts = _local_idea_texts(inventory)
            reuse_ok = (
                len(ideas) == EXPECTED_IDEA
                and len(local_texts) == EXPECTED_IDEA
                and Counter(ideas) == Counter(local_texts)
            )
        accountability = f"{len(ideas)} / {EXPECTED_IDEA}"
    else:
        reuse_ok = identity.get("json_parse") == "PASS"
    a48_pass = A48_STATUS_PRESERVED == "PASS"
    gates = {
        "a48_pass": _status(a48_pass),
        "candidate_identity": _status(bool(identity.get("sha256"))),
        "candidate_provenance": _status(
            bool(raw_identity.get("ok")) and (intent_ok if pastoral_contract else True)
        ),
        "raw_a46_unchanged": _status(bool(raw_identity.get("ok"))),
        "canonical_validation": validation["canonical_validation"],
        "intent_contract": _status(intent_ok) if pastoral_contract else "PASS",
        "idea_accountability": (
            _status(len(ideas) == EXPECTED_IDEA) if pastoral_contract else "PASS"
        ),
        "reuse_identity": _status(reuse_ok) if pastoral_contract else "PASS",
        "traceability": validation["traceability"],
        "structural_scanner": validation["structural_scan"],
        "semantic_review": _status(semantic == "PASS") if pastoral_contract else "PASS",
        "publication_eligible": _status(eligible == "YES"),
    }
    all_pass = all(value == "PASS" for value in gates.values())
    authorized = all_pass and eligible == "YES"
    return {
        "gates": gates,
        "all_pass": all_pass,
        "authorized": authorized,
        "publication_eligible": eligible,
        "semantic_review": semantic,
        "a48_status": A48_STATUS_PRESERVED,
        "identity": identity,
        "raw_identity": {
            "ok": raw_identity.get("ok"),
            "raw_response_hash": raw_identity.get("raw_response_hash"),
            "recomputed_raw_text_hash": raw_identity.get("recomputed_raw_text_hash"),
        },
        "validation": {
            key: value
            for key, value in validation.items()
            if key != "source_map"
        },
        "intent": {
            "text": intent,
            "length": len(intent),
            "expected_length": A46_INTENT_LENGTH,
            "limit": GLOBAL_INTENT_MAX_CHARS,
            "unchanged": intent == expected_intent,
            "status": _status(intent_ok) if pastoral_contract else "PASS",
        },
        "accountability": {
            "local_ideas": EXPECTED_IDEA if pastoral_contract else len(ideas),
            "accounted": len(ideas),
            "reuse": EXPECTED_IDEA if pastoral_contract and reuse_ok else (
                len(ideas) if reuse_ok else 0
            ),
            "merge": 0,
            "drop": 0,
            "label": accountability,
            "reuse_identity": _status(reuse_ok),
        },
        "technical_a48": {
            "canonical_validation": technical.get("canonical_validation"),
            "idea_accountability": technical.get("idea_accountability"),
            "keep_count": technical.get("keep_count"),
            "merge_equivalent_count": technical.get("merge_equivalent_count"),
            "drop_count": technical.get("drop_count"),
            "candidate_hash": technical.get("candidate_hash"),
        },
        "inventory": validation["inventory"],
        "blocked_reason": (
            ""
            if authorized
            else "PRE_PUBLICATION_GATE"
        ),
    }


__all__ = [
    "evaluate_prepublication_gate",
    "locate_validated_candidate",
    "read_a48_publication_eligible",
    "read_a48_semantic_status",
    "validate_candidate_payload",
]
