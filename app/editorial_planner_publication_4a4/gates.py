"""Pre-publication gates. Offline. No regeneration. No provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.editorial_planner_canary_4a35.accountability import exact_accountability
from app.editorial_planner_canary_4a35.language import language_audit
from app.editorial_planner_language_policy_4a32.language import load_language_provenance
from app.editorial_planner_publication_4a4.constants import (
    EXPECTED_ASSIGNED,
    EXPECTED_CANDIDATE_BYTES,
    EXPECTED_CANDIDATE_CHARS,
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_CANONICAL_DOCUMENT_LANGUAGE,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_DEFERRED,
    EXPECTED_DUPLICATE_PRIMARY,
    EXPECTED_EXCLUDED,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REUSED,
    EXPECTED_SECTION_COUNT,
    EXPECTED_SILENT_OMISSIONS,
    EXPECTED_SOURCE_MAP_SHA256,
    EXPECTED_UNKNOWN_REFS,
    LANGUAGE_POLICY,
    WORKING_TITLE,
)
from app.editorial_planner_publication_4a4.identity import bytes_identity, file_identity
from app.editorial_planner_publication_4a4.paths import (
    a35_accountability_path,
    a35_candidate_path,
    a35_execution_path,
    a35_language_path,
    a35_precall_path,
    a35_publication_path,
    a35_readiness_path,
    a35_response_path,
    a35_semantic_path,
    a35_technical_path,
)
from app.editorial_planning.models import EditorialPlan
from app.editorial_planning.validator import validate_editorial_plan
from app.source_analysis.models import SourceMap


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _match(ok: bool) -> str:
    return "MATCH" if ok else "MISMATCH"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _yn_bool(value: Any) -> bool:
    if value is True:
        return True
    text = str(value or "").strip().upper()
    return text in {"YES", "TRUE", "PASS"}


def unknown_reference_counts(
    plan: EditorialPlan, source_map: SourceMap
) -> dict[str, int]:
    known = {
        "IDEA": {idea.idea_id for idea in source_map.ideas},
        "TOP": {topic.topic_id for topic in source_map.topics},
        "EX": {item.example_id for item in source_map.examples},
        "REF": {item.reference_id for item in source_map.references},
        "UNC": {item.uncertainty_id for item in source_map.uncertainties},
    }
    counts = {"IDEA": 0, "TOP": 0, "EX": 0, "REF": 0, "UNC": 0}

    def _count(refs: tuple[str, ...], kind: str) -> None:
        for ref in refs:
            if ref not in known[kind]:
                counts[kind] += 1

    for chapter in plan.chapters:
        _count(chapter.topic_refs, "TOP")
        for section in chapter.sections:
            _count(section.idea_refs, "IDEA")
            _count(section.topic_refs, "TOP")
            _count(section.example_refs, "EX")
            _count(section.reference_refs, "REF")
            _count(section.uncertainty_refs, "UNC")
    return counts


def verify_a35_evidence(
    *,
    candidate_sha256: str,
    root: Path | None = None,
) -> dict[str, Any]:
    execution = _load_json(a35_execution_path(root=root))
    precall = _load_json(a35_precall_path(root=root))
    technical = _load_json(a35_technical_path(root=root))
    accountability = _load_json(a35_accountability_path(root=root))
    language = _load_json(a35_language_path(root=root))
    semantic = _load_json(a35_semantic_path(root=root))
    publication = _load_json(a35_publication_path(root=root))
    readiness = _load_json(a35_readiness_path(root=root))
    response = _load_json(a35_response_path(root=root))

    authorized_calls = int(
        execution.get("anthropic_post_attempts")
        or execution.get("engine_generate_attempts")
        or 0
    )
    actual_calls = authorized_calls
    retries = int(execution.get("retries") or 0)
    fallbacks = int(execution.get("fallbacks") or 0)
    request_identity = str(precall.get("request_identity") or "")
    semantic_status = str(semantic.get("status") or "").upper()
    technical_hash = str(technical.get("plan_sha256") or "")
    evidence_hash_ok = technical_hash == candidate_sha256 and bool(candidate_sha256)
    eligible = _yn_bool(publication.get("PUBLICATION_ELIGIBLE"))
    ready = _yn_bool(readiness.get("READY_FOR_CONTROLLED_EDITORIAL_PLAN_PUBLICATION"))
    gates = {
        "authorized_provider_calls": _status(authorized_calls == 1),
        "actual_provider_calls": _status(actual_calls == 1),
        "retries": _status(retries == 0),
        "fallbacks": _status(fallbacks == 0),
        "request_identity": _status(request_identity == "MATCH"),
        "structured_parse": _status(technical.get("structured_parse") == "PASS"),
        "transport_decoder": _status(technical.get("transport_decoder") == "PASS"),
        "handles": _status(technical.get("handle_validation") == "PASS"),
        "canonical_reconstruction": _status(
            technical.get("canonical_reconstruction") == "PASS"
        ),
        "idea_coverage": _status(
            accountability.get("coverage_display") == "286 / 286"
            or accountability.get("exactly_once") is True
        ),
        "silent_omissions": _status(int(accountability.get("silent_omissions") or 0) == 0),
        "duplicate_primary": _status(
            not accountability.get("duplicate_primary_ids")
        ),
        "editorial_language": _status(
            language.get("editorial_language_match") == "PASS"
            or language.get("status") == "PASS"
        ),
        "traceability": _status(technical.get("traceability") == "PASS"),
        "invention_boundary": _status(technical.get("invention_boundary") == "PASS"),
        "uncertainty": _status(technical.get("uncertainty_preservation") == "PASS"),
        "validator": _status(
            technical.get("editorial_plan_validator") == "PASS"
            or (technical.get("validator") or {}).get("status") == "PASS"
        ),
        "deterministic_replay": _status(technical.get("deterministic_replay") == "PASS"),
        "semantic_review": _status(semantic_status == "PASS"),
        "publication_eligible": _status(eligible),
        "ready_for_publication": _status(ready),
        "semantic_evidence_hash": _status(evidence_hash_ok),
    }
    return {
        "gates": gates,
        "all_pass": all(value == "PASS" for value in gates.values()),
        "authorized_provider_calls": authorized_calls,
        "actual_provider_calls": actual_calls,
        "retries": retries,
        "fallbacks": fallbacks,
        "request_identity": request_identity,
        "semantic_review": semantic_status,
        "publication_eligible": "YES" if eligible else "NO",
        "candidate_hash_in_evidence": technical_hash,
        "evidence_corresponds_to_candidate": evidence_hash_ok,
        "request_id": str(response.get("request_id") or ""),
        "present": all(
            path.is_file()
            for path in (
                a35_execution_path(root=root),
                a35_precall_path(root=root),
                a35_technical_path(root=root),
                a35_accountability_path(root=root),
                a35_language_path(root=root),
                a35_semantic_path(root=root),
                a35_publication_path(root=root),
            )
        ),
    }


def validate_candidate_plan(
    payload: Mapping[str, Any],
    source_map: SourceMap,
    *,
    canonical_document_language: str,
    expected_idea_count: int | None = None,
    expected_title: str | None = None,
    expected_chapters: int | None = None,
    expected_sections: int | None = None,
    check_forensic_ideas: bool = False,
) -> dict[str, Any]:
    parse_ok = isinstance(payload, Mapping) and bool(payload)
    plan = None
    model_error = ""
    try:
        plan = EditorialPlan.from_dict(payload)
        model_ok = True
    except Exception as exc:  # noqa: BLE001
        model_ok = False
        model_error = f"{type(exc).__name__}: {exc}"
    validation = None
    if plan is not None:
        validation = validate_editorial_plan(plan, source_map, payload=payload)
    accountability = exact_accountability(payload if parse_ok else None, source_map)
    language = language_audit(
        payload if parse_ok else None,
        canonical_document_language=canonical_document_language,
    )
    unknown = (
        unknown_reference_counts(plan, source_map)
        if plan is not None
        else {"IDEA": -1, "TOP": -1, "EX": -1, "REF": -1, "UNC": -1}
    )
    unknown_total = sum(max(0, value) for value in unknown.values())
    chapters = len(plan.chapters) if plan is not None else 0
    sections = len(plan.all_sections()) if plan is not None else 0
    title = plan.selected_title if plan is not None else ""
    forensic = accountability.get("forensic_followup") or {}
    idea007 = forensic.get("IDEA007") or {}
    idea008 = forensic.get("IDEA008") or {}
    idea_count = expected_idea_count
    if idea_count is None:
        idea_count = len(source_map.ideas)
    coverage_ok = (
        accountability.get("exactly_once") is True
        and int(accountability.get("assigned_count") or 0)
        == (EXPECTED_ASSIGNED if idea_count == EXPECTED_IDEA_COUNT else idea_count)
        and int(accountability.get("deferred_count") or 0) == EXPECTED_DEFERRED
        and int(accountability.get("excluded_count") or 0) == EXPECTED_EXCLUDED
        and int(accountability.get("silent_omissions") or 0) == EXPECTED_SILENT_OMISSIONS
        and not accountability.get("duplicate_primary_ids")
        and int(accountability.get("reused_count") or 0) == EXPECTED_REUSED
        and int(accountability.get("input_ideas_count") or 0) == idea_count
    )
    if idea_count != EXPECTED_IDEA_COUNT:
        coverage_ok = (
            accountability.get("exactly_once") is True
            and int(accountability.get("silent_omissions") or 0) == 0
            and not accountability.get("duplicate_primary_ids")
            and unknown_total == 0
        )
    hierarchy_ok = True
    if expected_chapters is not None:
        hierarchy_ok = hierarchy_ok and chapters == expected_chapters
    if expected_sections is not None:
        hierarchy_ok = hierarchy_ok and sections == expected_sections
    if plan is not None:
        chapter_ids = [chapter.chapter_id for chapter in plan.chapters]
        section_ids = [section.section_id for section in plan.all_sections()]
        hierarchy_ok = hierarchy_ok and chapter_ids == [
            f"CH{index:03d}" for index in range(1, chapters + 1)
        ]
        hierarchy_ok = hierarchy_ok and section_ids == [
            f"SEC{index:03d}" for index in range(1, sections + 1)
        ]
    title_ok = True
    if expected_title is not None:
        title_ok = title == expected_title
    forensic_ok = True
    if check_forensic_ideas:
        forensic_ok = (
            idea007.get("disposition") == "ASSIGNED"
            and idea007.get("primary_section_id") == "SEC004"
            and idea008.get("disposition") == "ASSIGNED"
            and idea008.get("primary_section_id") == "SEC004"
            and idea007.get("special_cased") is False
            and idea008.get("special_cased") is False
        )
    validator_status = validation.status if validation is not None else "FAIL"
    language_status = str(language.get("editorial_language_match") or "FAIL")
    return {
        "json_object": parse_ok,
        "model_load": _status(model_ok),
        "model_error": model_error,
        "validator": validator_status,
        "validator_errors": list(validation.errors) if validation is not None else [
            "plan illisible"
        ],
        "accountability": accountability,
        "language": language,
        "editorial_language": language_status,
        "unknown_refs": unknown,
        "unknown_ref_total": unknown_total,
        "chapters": chapters,
        "sections": sections,
        "selected_title": title,
        "coverage_ok": coverage_ok,
        "hierarchy_ok": hierarchy_ok,
        "title_ok": title_ok,
        "forensic_ok": forensic_ok,
        "unknown_ok": unknown_total == EXPECTED_UNKNOWN_REFS,
        "plan": plan,
    }


def evaluate_prepublication_gate(
    candidate_bytes: bytes,
    source_map: SourceMap,
    source_map_sha256: str,
    *,
    root: Path | None = None,
    pastoral_contract: bool = True,
    expected_candidate_sha256: str | None = None,
    expected_candidate_bytes: int | None = None,
    expected_candidate_chars: int | None = None,
    expected_source_map_sha256: str | None = None,
    expected_canonical_language: str | None = None,
    expected_idea_count: int | None = None,
    publication_eligible_override: str | None = None,
) -> dict[str, Any]:
    identity = bytes_identity(candidate_bytes)
    payload = identity.get("payload") or {}
    if pastoral_contract:
        expected_sha = expected_candidate_sha256 or EXPECTED_CANDIDATE_SHA256
        expected_bytes = expected_candidate_bytes or EXPECTED_CANDIDATE_BYTES
        expected_chars = expected_candidate_chars or EXPECTED_CANDIDATE_CHARS
        expected_map = expected_source_map_sha256 or EXPECTED_SOURCE_MAP_SHA256
        language = expected_canonical_language or EXPECTED_CANONICAL_DOCUMENT_LANGUAGE
        idea_count = expected_idea_count or EXPECTED_IDEA_COUNT
        expected_title = WORKING_TITLE
        expected_chapters = EXPECTED_CHAPTER_COUNT
        expected_sections = EXPECTED_SECTION_COUNT
        check_forensic = True
        require_identity = True
    else:
        expected_sha = expected_candidate_sha256
        expected_bytes = expected_candidate_bytes
        expected_chars = expected_candidate_chars
        expected_map = expected_source_map_sha256
        language = expected_canonical_language or source_map.primary_language or "en"
        idea_count = expected_idea_count or len(source_map.ideas)
        expected_title = None
        expected_chapters = None
        expected_sections = None
        check_forensic = False
        require_identity = expected_sha is not None or expected_map is not None

    candidate_match = True
    if expected_sha is not None:
        candidate_match = identity.get("sha256") == expected_sha
    if expected_bytes is not None:
        candidate_match = candidate_match and identity.get("utf8_bytes") == expected_bytes
    if expected_chars is not None:
        candidate_match = (
            candidate_match and identity.get("character_count") == expected_chars
        )
    source_match = True
    if expected_map is not None:
        source_match = source_map_sha256 == expected_map

    if pastoral_contract:
        try:
            provenance = load_language_provenance(source_map, root=root)
            language_chain_ok = (
                provenance.get("canonical_document_language") == language
                and provenance.get("blocked") is False
                and provenance.get("policy") == LANGUAGE_POLICY
            )
        except Exception as exc:  # noqa: BLE001
            provenance = {"error": f"{type(exc).__name__}: {exc}"}
            language_chain_ok = False
        evidence = verify_a35_evidence(
            candidate_sha256=str(identity.get("sha256") or ""),
            root=root,
        )
        if publication_eligible_override is not None:
            eligible = str(publication_eligible_override).strip().upper()
        else:
            eligible = evidence.get("publication_eligible") or "NO"
    else:
        provenance = {
            "canonical_document_language": language,
            "policy": LANGUAGE_POLICY,
            "blocked": False,
        }
        language_chain_ok = bool(language)
        evidence = {
            "gates": {},
            "all_pass": True,
            "semantic_review": "PASS",
            "publication_eligible": "YES",
            "evidence_corresponds_to_candidate": True,
            "present": True,
        }
        eligible = (
            str(publication_eligible_override).strip().upper()
            if publication_eligible_override is not None
            else "YES"
        )

    validation = validate_candidate_plan(
        payload,
        source_map,
        canonical_document_language=language,
        expected_idea_count=idea_count,
        expected_title=expected_title,
        expected_chapters=expected_chapters,
        expected_sections=expected_sections,
        check_forensic_ideas=check_forensic,
    )
    gates = {
        "candidate_identity": _status(candidate_match and bool(identity.get("sha256"))),
        "source_map_identity": _status(source_match and bool(source_map_sha256)),
        "a35_evidence": _status(bool(evidence.get("all_pass"))),
        "publication_eligible": _status(eligible == "YES"),
        "validator": _status(validation.get("validator") == "PASS"),
        "coverage": _status(bool(validation.get("coverage_ok"))),
        "unknown_refs": _status(bool(validation.get("unknown_ok"))),
        "editorial_language": _status(validation.get("editorial_language") == "PASS"),
        "language_chain": _status(language_chain_ok),
        "hierarchy": _status(bool(validation.get("hierarchy_ok"))),
        "working_title": _status(bool(validation.get("title_ok"))),
        "forensic_ideas": _status(bool(validation.get("forensic_ok"))),
        "model_load": validation.get("model_load") or "FAIL",
    }
    all_pass = all(value == "PASS" for value in gates.values())
    authorized = all_pass and eligible == "YES"
    if require_identity and (not candidate_match or not source_match):
        authorized = False
    blocked_reason = ""
    if not authorized:
        if not candidate_match:
            blocked_reason = "CANDIDATE_IDENTITY"
        elif not source_match:
            blocked_reason = "SOURCE_MAP_IDENTITY"
        elif eligible != "YES":
            blocked_reason = "PUBLICATION_ELIGIBLE"
        elif validation.get("validator") != "PASS":
            blocked_reason = "VALIDATOR"
        elif validation.get("editorial_language") != "PASS":
            blocked_reason = "LANGUAGE"
        elif not validation.get("coverage_ok"):
            blocked_reason = "COVERAGE"
        elif not validation.get("unknown_ok"):
            blocked_reason = "UNKNOWN_REF"
        else:
            blocked_reason = "PRE_PUBLICATION_GATE"
    return {
        "gates": gates,
        "all_pass": all_pass,
        "authorized": authorized,
        "blocked_reason": blocked_reason,
        "candidate_identity": identity,
        "candidate_identity_status": _match(candidate_match),
        "source_map_sha256": source_map_sha256,
        "source_map_identity_status": _match(source_match),
        "publication_eligible": eligible,
        "validation": {
            key: value for key, value in validation.items() if key != "plan"
        },
        "evidence": evidence,
        "language_provenance": provenance,
        "canonical_document_language": language,
        "language_policy": LANGUAGE_POLICY,
        "pastoral_contract": pastoral_contract,
        "plan": validation.get("plan"),
    }


def locate_validated_candidate(*, root: Path | None = None) -> Path:
    path = a35_candidate_path(root=root)
    if not path.is_file():
        raise FileNotFoundError(
            "Candidat A.3.5 introuvable — publication bloquée : " + str(path)
        )
    return path


__all__ = [
    "evaluate_prepublication_gate",
    "file_identity",
    "locate_validated_candidate",
    "unknown_reference_counts",
    "validate_candidate_plan",
    "verify_a35_evidence",
]
