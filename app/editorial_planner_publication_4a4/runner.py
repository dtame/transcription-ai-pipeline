"""Assemble Phase 4A.4. 0 provider. Atomic publication of the A.3.5 candidate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.editorial_planner_canary_4a35.constants import (
    A3_CANDIDATE_SHA256,
    A33_CANDIDATE_SHA256,
)
from app.editorial_planner_publication_4a4.constants import (
    BOOK_GENERATOR,
    BOOK_GENERATOR_INPUT_CONTRACT,
    BYTE_IDENTITY_EXACT,
    COVERAGE_CONTRACT,
    COVERAGE_POLICY,
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_CANONICAL_DOCUMENT_LANGUAGE,
    EXPECTED_CHAPTER_COUNT,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SECTION_COUNT,
    EXPECTED_SOURCE_MAP_SHA256,
    FINAL_TITLE_APPROVED,
    HISTORICAL_PROMPTS,
    LANGUAGE_CONTRACT,
    LANGUAGE_POLICY,
    MODEL,
    NEXT_ACTION,
    PHASE,
    PHASE_4A4_COST_USD,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    PROVIDER_DISPLAY,
    PUBLICATION_MODE_CONFLICT,
    PUBLICATION_POLICY,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    RELATION_QUALITY_TECHNICAL_DEBT,
    REQUEST_ID,
    SCHEMA_HASH,
    THINKING_MODE,
    TRANSPORT_VERSION,
    WORKING_TITLE,
    WORKING_TITLE_STATUS,
)
from app.editorial_planner_publication_4a4.gates import (
    evaluate_prepublication_gate,
    locate_validated_candidate,
)
from app.editorial_planner_publication_4a4.identity import file_identity, sha256_file
from app.editorial_planner_publication_4a4.offline import (
    assert_analyzer_untouched,
    assert_no_book_generator,
    assert_offline_package,
)
from app.editorial_planner_publication_4a4.paths import (
    a3_candidate_path,
    a33_candidate_path,
    a35_candidate_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.editorial_planner_publication_4a4.publish import publish_exact_bytes
from app.editorial_planner_publication_4a4.reload import reload_published
from app.editorial_planning.pipeline import load_published_source_map


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _historical_hashes(*, root: Path | None = None) -> dict[str, Any]:
    a35 = a35_candidate_path(root=root)
    a33 = a33_candidate_path(root=root)
    a3 = a3_candidate_path(root=root)
    observed = {
        "a35": sha256_file(a35),
        "a33": sha256_file(a33),
        "a3": sha256_file(a3),
    }
    return {
        "a35_path": str(a35).replace("\\", "/"),
        "a35_sha256": observed["a35"],
        "a35_unchanged": observed["a35"] == EXPECTED_CANDIDATE_SHA256,
        "a33_path": str(a33).replace("\\", "/"),
        "a33_sha256": observed["a33"],
        "a33_unchanged": observed["a33"] == A33_CANDIDATE_SHA256,
        "a3_path": str(a3).replace("\\", "/"),
        "a3_sha256": observed["a3"],
        "a3_unchanged": observed["a3"] == A3_CANDIDATE_SHA256,
        "all_unchanged": (
            observed["a35"] == EXPECTED_CANDIDATE_SHA256
            and observed["a33"] == A33_CANDIDATE_SHA256
            and observed["a3"] == A3_CANDIDATE_SHA256
        ),
    }


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    root: Path | None = None,
    sortie_dir: Path | None = None,
    candidate_path: Path | None = None,
    source_map_file: Path | None = None,
    target_path: Path | None = None,
    pastoral_contract: bool = True,
    expected_candidate_sha256: str | None = None,
    expected_candidate_bytes: int | None = None,
    expected_candidate_chars: int | None = None,
    expected_source_map_sha256: str | None = None,
    expected_canonical_language: str | None = None,
    expected_idea_count: int | None = None,
    publication_eligible_override: str | None = None,
    tests: str = "offline 4A.4",
    test_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_untouched()
    assert_no_book_generator()
    if candidate_path is None:
        candidate_path = locate_validated_candidate(root=root)
    else:
        candidate_path = Path(candidate_path)
        if not candidate_path.is_file():
            raise FileNotFoundError(
                "Candidat introuvable — publication bloquée : " + str(candidate_path)
            )
    candidate_bytes = candidate_path.read_bytes()
    candidate_identity = file_identity(candidate_path)
    if source_map_file is not None:
        from app.editorial_planning.preflight import load_source_map_file

        source_map, source_raw, source_digest = load_source_map_file(
            Path(source_map_file)
        )
        source_path = Path(source_map_file)
    else:
        source_map, source_raw, source_digest, source_path = load_published_source_map(
            project_name, sortie_dir=sortie_dir
        )
    source_pre = source_digest
    gate = evaluate_prepublication_gate(
        candidate_bytes,
        source_map,
        source_digest,
        root=root,
        pastoral_contract=pastoral_contract,
        expected_candidate_sha256=expected_candidate_sha256,
        expected_candidate_bytes=expected_candidate_bytes,
        expected_candidate_chars=expected_candidate_chars,
        expected_source_map_sha256=expected_source_map_sha256,
        expected_canonical_language=expected_canonical_language,
        expected_idea_count=expected_idea_count,
        publication_eligible_override=publication_eligible_override,
    )
    target = Path(target_path) if target_path is not None else (
        production_editorial_plan_path(project_name, sortie_dir=sortie_dir)
    )
    publication = publish_exact_bytes(
        target,
        candidate_bytes,
        authorized=bool(gate["authorized"]),
    )
    conflict = publication.get("mode") == PUBLICATION_MODE_CONFLICT
    published_ok = bool(publication.get("published")) and not conflict
    language = (
        expected_canonical_language
        or gate.get("canonical_document_language")
        or EXPECTED_CANONICAL_DOCUMENT_LANGUAGE
    )
    expected_title = WORKING_TITLE if pastoral_contract else None
    if published_ok:
        reload = reload_published(
            project_name,
            candidate_bytes=candidate_bytes,
            source_map=source_map,
            sortie_dir=sortie_dir,
            published_path=target,
            canonical_document_language=language,
            expected_title=expected_title,
        )
    else:
        reload = {
            "json_parse": "FAIL",
            "model_load": "FAIL",
            "validator": "FAIL",
            "reload": "FAIL",
            "byte_identity": "NOT_PUBLISHED",
            "published_sha256": "",
            "published_bytes": 0,
            "published_chars": 0,
            "chapters": 0,
            "sections": 0,
            "selected_title": "",
            "editorial_language": "FAIL",
            "unknown_ref_total": -1,
            "accountability": {},
            "exists": target.is_file(),
            "path": str(target).replace("\\", "/"),
        }
    source_post = sha256_file(source_path)
    source_unchanged = source_pre == source_post and bool(source_post)
    historical = (
        _historical_hashes(root=root)
        if pastoral_contract
        else {
            "a35_unchanged": True,
            "a33_unchanged": True,
            "a3_unchanged": True,
            "all_unchanged": True,
            "a35_sha256": candidate_identity.get("sha256"),
            "a33_sha256": "",
            "a3_sha256": "",
        }
    )
    new_failures = int((test_delta or {}).get("new_failure_count") or 0)
    tests_ok = new_failures == 0
    validation = gate.get("validation") or {}
    accountability = validation.get("accountability") or reload.get("accountability") or {}
    post_ok = (
        published_ok
        and reload.get("reload") == "PASS"
        and reload.get("validator") == "PASS"
        and reload.get("byte_identity") == BYTE_IDENTITY_EXACT
        and source_unchanged
        and bool(historical.get("all_unchanged"))
    )
    freeze = post_ok and tests_ok and not conflict
    if conflict:
        result = "BLOCKED_CONFLICT"
    elif not gate["authorized"]:
        result = "BLOCKED"
    elif published_ok and not post_ok:
        result = "FAIL"
    elif freeze:
        result = "PASS"
    else:
        result = "FAIL"
    plan_status = "PUBLISHED" if post_ok else "NOT PUBLISHED"
    phase_status = "FROZEN" if freeze else "NOT FROZEN"
    header = {
        "result": result,
        "phase": PHASE,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "approved_candidate_path": str(candidate_path).replace("\\", "/"),
        "expected_candidate_sha256": (
            expected_candidate_sha256 or EXPECTED_CANDIDATE_SHA256
            if pastoral_contract
            else expected_candidate_sha256 or candidate_identity.get("sha256")
        ),
        "actual_candidate_sha256": candidate_identity.get("sha256"),
        "candidate_identity": gate.get("candidate_identity_status"),
        "source_map_sha256_pre": source_pre,
        "source_map_sha256_post": source_post,
        "source_map_unchanged": "YES" if source_unchanged else "NO",
        "canonical_language": language,
        "language_policy": LANGUAGE_POLICY,
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "schema_hash": SCHEMA_HASH,
        "provider_provenance": f"{PROVIDER_DISPLAY} / {MODEL}",
        "request_id": REQUEST_ID if pastoral_contract else "",
        "request_sha256": EXPECTED_REQUEST_SHA256 if pastoral_contract else "",
        "publication_path": str(target).replace("\\", "/"),
        "atomic_publication": publication.get("atomic_publication"),
        "published_sha256": reload.get("published_sha256") or "",
        "byte_identity": reload.get("byte_identity") or publication.get("byte_identity"),
        "reload": reload.get("reload"),
        "validator": (
            validation.get("validator") if not published_ok else reload.get("validator")
        ),
        "chapters": reload.get("chapters") or validation.get("chapters") or 0,
        "sections": reload.get("sections") or validation.get("sections") or 0,
        "idea_coverage": accountability.get("coverage_display") or "0 / 0",
        "assigned": accountability.get("assigned_count") or 0,
        "deferred": accountability.get("deferred_count") or 0,
        "excluded": accountability.get("excluded_count") or 0,
        "silent_omissions": accountability.get("silent_omissions") or 0,
        "duplicate_primary_dispositions": len(
            accountability.get("duplicate_primary_ids") or []
        ),
        "unknown_refs": (
            reload.get("unknown_ref_total")
            if published_ok
            else validation.get("unknown_ref_total")
        ),
        "editorial_language": (
            reload.get("editorial_language")
            if published_ok
            else validation.get("editorial_language")
        ),
        "working_title": reload.get("selected_title")
        or validation.get("selected_title")
        or "",
        "working_title_status": WORKING_TITLE_STATUS if pastoral_contract else "",
        "final_title_approved": "NO",
        "phase_4_contract_freeze": _status(freeze),
        "phase_4_ai_cost": f"{PHASE_4A4_COST_USD} USD",
        "tests": tests,
        "new_failures": (test_delta or {}).get("new_failure_count", "pending"),
        "editorial_plan_json": plan_status,
        "phase_4_status": phase_status,
        "ready_for_book_generator_phase_4b": "YES" if freeze else "NO",
        "book_generator": BOOK_GENERATOR,
        "next_action": NEXT_ACTION,
        "publication_mode": publication.get("mode"),
        "target_preexisted": "YES" if publication.get("preexisted") else "NO",
        "target_conflict": "YES" if publication.get("conflict") else "NO",
        "blocked_reason": gate.get("blocked_reason") or "",
    }
    freeze_manifest = {
        "source_map_sha256": source_post,
        "editorial_plan_sha256": reload.get("published_sha256") or "",
        "prompt_version": PROMPT_VERSION,
        "historical_prompts_preserved": list(HISTORICAL_PROMPTS),
        "transport_version": TRANSPORT_VERSION,
        "schema_hash": SCHEMA_HASH,
        "language_policy": LANGUAGE_POLICY,
        "canonical_language": language,
        "provider": PROVIDER,
        "provider_display": PROVIDER_DISPLAY,
        "model": MODEL,
        "thinking": THINKING_MODE,
        "production_max_tokens": PRODUCTION_MAX_OUTPUT_TOKENS,
        "request_id": REQUEST_ID if pastoral_contract else "",
        "request_sha256": EXPECTED_REQUEST_SHA256 if pastoral_contract else "",
        "coverage_policy": COVERAGE_POLICY,
        "coverage_contract": COVERAGE_CONTRACT,
        "publication_policy": PUBLICATION_POLICY,
        "language_contract": LANGUAGE_CONTRACT,
        "chapter_count": reload.get("chapters") or 0,
        "section_count": reload.get("sections") or 0,
        "idea_count": accountability.get("input_ideas_count") or 0,
        "working_title": header["working_title"],
        "working_title_status": WORKING_TITLE_STATUS if pastoral_contract else "",
        "final_title_approved": FINAL_TITLE_APPROVED,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "planner_validation_passed_despite_relation_debt": freeze,
        "book_generator_input_contract": BOOK_GENERATOR_INPUT_CONTRACT,
        "book_generator_must_not_use_audit_candidate": True,
        "book_generator_canonical_language": language,
        "do_not_regenerate_for_style": True,
        "phase_4_status": phase_status,
        "frozen": freeze,
    }
    readiness = {
        "READY_FOR_BOOK_GENERATOR_PHASE_4B": "YES" if freeze else "NO",
        "PHASE_4_STATUS": phase_status,
        "editorial_plan.json": plan_status,
        "BOOK_GENERATOR": BOOK_GENERATOR,
        "FINAL_TITLE_APPROVED": "NO",
        "REAL_PROVIDER_CALLS": REAL_PROVIDER_CALLS_THIS_PHASE,
        "PHASE_4A4_COST_USD": PHASE_4A4_COST_USD,
        "NEXT_ACTION": NEXT_ACTION,
        "do_not_call_provider": True,
        "do_not_start_book_generator": True,
        "do_not_create_book_json": True,
        "do_not_generate_manuscript": True,
        "do_not_start_word": True,
        "do_not_generate_cover": True,
        "do_not_generate_pdf": True,
        "do_not_implement_translation": True,
        "future_change_requires_versioned_request": True,
        "expected_inventory": {
            "chapters": EXPECTED_CHAPTER_COUNT if pastoral_contract else header["chapters"],
            "sections": EXPECTED_SECTION_COUNT if pastoral_contract else header["sections"],
            "ideas": EXPECTED_IDEA_COUNT if pastoral_contract else (
                accountability.get("input_ideas_count") or 0
            ),
        },
        "source_map_sha256": EXPECTED_SOURCE_MAP_SHA256 if pastoral_contract else source_post,
    }
    return {
        "header": header,
        "gate": {
            key: value for key, value in gate.items() if key != "plan"
        },
        "candidate_identity": candidate_identity,
        "publication": publication,
        "reload": reload,
        "freeze": freeze_manifest,
        "readiness": readiness,
        "historical": historical,
        "source_map_pre": source_pre,
        "source_map_post": source_post,
        "test_delta": test_delta or {},
        "result": result,
        "published": post_ok,
        "candidate_path": str(candidate_path).replace("\\", "/"),
        "source_map_path": str(source_path).replace("\\", "/"),
        "target_path": str(target).replace("\\", "/"),
    }


__all__ = ["build_bundle"]
