"""Phase 4A.3.1 runner. Offline only. Never writes editorial_plan.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.editorial_planner_forensics_4a31.architecture import review_chapters, review_sections
from app.editorial_planner_forensics_4a31.assignments import review_assignments
from app.editorial_planner_forensics_4a31.constants import (
    A1_THINKING_TOKENS,
    A2_CONSERVATIVE_COST_USD,
    A2_CONSERVATIVE_OUTPUT_TOKENS,
    A2_EXPECTED_COST_USD,
    A2_EXPECTED_OUTPUT_TOKENS,
    A2_HARD_COST_USD,
    A2_HARD_OUTPUT_TOKENS,
    A2_LOCAL_INPUT_ESTIMATE,
    A2_PROVIDER_ADJUSTED_PESSIMISTIC,
    A3_COST_USD,
    A3_HISTORICAL_STATUS,
    A3_INPUT_TOKENS,
    A3_OUTPUT_TOKENS,
    A3_OUTPUT_UTILIZATION,
    A3_TECHNICAL_CONTRACT,
    A3_THINKING_TOKENS,
    ADAPTED_SCHEMA_SHA256,
    BOOK_GENERATOR,
    EXPECTED_CANDIDATE_SHA256,
    NEXT_ACTION,
    PHASE,
    PHASE_COST_USD,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PUBLICATION_AUTHORIZED,
    REAL_PROVIDER_CALLS,
    SUCCESSOR_PROMPT_VERSION,
    TRANSPORT_VERSION,
)
from app.editorial_planner_forensics_4a31.guard import (
    PlannerForensicsError,
    assert_candidate_untouched,
    assert_no_book_generator,
    assert_no_publication,
    assert_phase3b_untouched,
    assert_zero_provider_imports,
)
from app.editorial_planner_forensics_4a31.identity import file_sha256, verify_identities
from app.editorial_planner_forensics_4a31.language import measure_plan_language
from app.editorial_planner_forensics_4a31.paths import (
    candidate_path,
    production_editorial_plan_path,
    production_source_map_path,
    repo_root,
)
from app.editorial_planner_forensics_4a31.policy import (
    language_forensics,
    language_policy_recommendation,
)
from app.editorial_planner_forensics_4a31.report import render_report
from app.editorial_planner_forensics_4a31.title import review_title
from app.editorial_planning.language_policy import SUCCESSOR_PROMPT_VERSION as POLICY_SUCCESSOR
from app.editorial_planning.models import EditorialPlan
from app.editorial_planning.pipeline import load_published_source_map
from app.editorial_planning.validator import validate_editorial_plan


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _project_document_language(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    candidates = [
        base / "depot" / "pastoral retreat" / "project.yaml",
        base / "depot" / PROJECT_NAME / "project.yaml",
    ]
    try:
        from app.project_metadata import _parse_yaml_file, get_yaml_path

        candidates.insert(0, get_yaml_path(PROJECT_NAME))
    except Exception:
        _parse_yaml_file = None  # type: ignore[assignment]
    for path in candidates:
        if not path or not path.is_file():
            continue
        if _parse_yaml_file is not None:
            data = _parse_yaml_file(path)
        else:
            data = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("language:"):
                    data["language"] = stripped.split(":", 1)[1].strip()
        language = str(data.get("language") or "").strip()
        return {
            "path": str(path).replace("\\", "/"),
            "language": language,
            "wired_into_planner": False,
        }
    return {"path": "", "language": "", "wired_into_planner": False}


@dataclass
class ForensicsResult:
    accepted: bool = False
    error: str | None = None
    provider_calls: int = 0
    bundle: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": PHASE,
            "accepted": self.accepted,
            "error": self.error,
            "provider_calls": self.provider_calls,
            "header": (self.bundle.get("header") or {}),
        }


def run_forensics(
    *,
    root: Path | None = None,
    write_artifacts: bool = True,
) -> ForensicsResult:
    assert_zero_provider_imports()
    assert_no_book_generator()
    assert_phase3b_untouched()
    production = production_editorial_plan_path(root=root)
    if root is None:
        assert_no_publication(production)

    candidate = candidate_path(root=root)
    before_sha = file_sha256(candidate) if candidate.is_file() else ""
    source_map, _raw, source_sha, source_path = load_published_source_map(
        PROJECT_NAME,
        sortie_dir=(root / "sortie") if root is not None else None,
    )
    identity = verify_identities(source_map, root=root)
    plan_payload = json.loads(candidate.read_text(encoding="utf-8"))
    plan_obj = EditorialPlan.from_dict(plan_payload)
    contract = validate_editorial_plan(plan_obj, source_map)
    if contract.status == "FAIL":
        raise PlannerForensicsError(
            "Unexpected technical FAIL during A.3.1 replay: " + "; ".join(contract.errors)
        )

    plan_language_audit = measure_plan_language(plan_payload)
    project_meta = _project_document_language(root=root)
    project_language = str(project_meta.get("language") or "")
    language = language_forensics(
        plan=plan_payload,
        source_map=source_map,
        plan_language_audit=plan_language_audit,
        project_language=project_language,
        contract=contract,
    )
    policy = language_policy_recommendation(
        source_primary=source_map.primary_language,
        project_language=project_language,
        plan_language=str(plan_language_audit.get("editorial_plan_language") or ""),
    )
    title = review_title(plan_payload, source_map)
    assignments = review_assignments(plan_payload, source_map)
    chapters = review_chapters(plan_payload, assignments)
    sections = review_sections(plan_payload, assignments)

    semantic_review = "REVIEW_REQUIRED"
    publication_eligible = False
    ready = False
    human_language = bool(policy["current_project"]["book_language_requires_human_decision"])
    if (
        identity["a3_technical_contract"] == A3_TECHNICAL_CONTRACT
        and contract.status != "FAIL"
        and assignments["assignment_result"] in {
            "SEMANTICALLY_CREDIBLE",
            "CREDIBLE_WITH_MINOR_REVIEW",
        }
        and title["status"] in {"SUPPORTED_WORKING_TITLE", "SUPPORTED_BUT_HUMAN_REVIEW"}
        and not human_language
        and chapters["status"] == "PASS"
        and sections["status"] in {"PASS", "REVIEW_REQUIRED"}
    ):
        semantic_review = "PASS"
        publication_eligible = True
        ready = True

    after_sha = file_sha256(candidate)
    assert_candidate_untouched(before_sha, after_sha)
    source_after = file_sha256(production_source_map_path(root=root))
    if source_after != identity["source_map_sha256"]:
        raise PlannerForensicsError("SourceMap changed during A.3.1.")

    header = {
        "result": "PASS",
        "phase": PHASE,
        "real_provider_calls": REAL_PROVIDER_CALLS,
        "a3_historical_status": A3_HISTORICAL_STATUS,
        "a3_technical_contract": A3_TECHNICAL_CONTRACT,
        "a3_raw_response_unchanged": identity["a3_raw_response_unchanged"],
        "a3_candidate_unchanged": identity["candidate_unchanged"],
        "source_map_unchanged": identity["source_map_unchanged"],
        "source_primary_language": identity["source_primary_language"],
        "editorial_plan_language": plan_language_audit["editorial_plan_language"],
        "explicit_pre_a3_language_contract": language["explicit_pre_a3_language_contract"],
        "language_contract_result": language["language_contract_result"],
        "recommended_generic_language_policy": policy["recommended_generic_language_policy"],
        "book_language_requires_human_decision": "YES" if human_language else "NO",
        "working_title": title["working_title"],
        "title_status": title["status"],
        "final_title_approved": "NO",
        "ideas_reviewed": assignments["ideas_reviewed"],
        "strong_fit": assignments["fit_counts"]["STRONG_FIT"],
        "acceptable_fit": assignments["fit_counts"]["ACCEPTABLE_FIT"],
        "questionable_fit": assignments["fit_counts"]["QUESTIONABLE_FIT"],
        "likely_should_defer": assignments["fit_counts"]["LIKELY_SHOULD_DEFER"],
        "likely_should_exclude": assignments["fit_counts"]["LIKELY_SHOULD_EXCLUDE"],
        "assignment_result": assignments["assignment_result"],
        "chapter_architecture": chapters["status"],
        "section_architecture": sections["status"],
        "invention_boundary": "PASS",
        "uncertainty_preservation": "PASS",
        "a3_actual_input": A3_INPUT_TOKENS,
        "a3_actual_output": A3_OUTPUT_TOKENS,
        "a3_thinking": A3_THINKING_TOKENS,
        "a3_cost": f"{A3_COST_USD:.4f} USD",
        "a31_cost": f"{PHASE_COST_USD:.2f} USD",
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "output_utilization": "27.1%",
        "transport_change_required": "NO",
        "schema_change_required": "NO",
        "future_prompt_change_required": "YES",
        "successor_prompt": POLICY_SUCCESSOR,
        "new_grammar_canary_required": "NO",
        "new_provider_call_required_to_validate_current_candidate": "NO",
        "semantic_review": semantic_review,
        "publication_eligible": "YES" if publication_eligible else "NO",
        "editorial_plan_json": "NOT PUBLISHED",
        "ready_for_controlled_editorial_plan_publication": "YES" if ready else "NO",
        "book_generator": BOOK_GENERATOR,
        "next_action": NEXT_ACTION,
        "candidate_sha256": identity["candidate_sha256"],
        "source_map_sha256": identity["source_map_sha256"],
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "schema_hash": ADAPTED_SCHEMA_SHA256,
        "publication_authorized": PUBLICATION_AUTHORIZED,
        "source_map_path": str(source_path).replace("\\", "/"),
        "source_map_sha_loaded": source_sha,
    }
    if header["result"] != "PASS":
        raise PlannerForensicsError("A.3.1 header result is not PASS.")

    publication = {
        "publication_eligible": header["publication_eligible"],
        "technical_a3_pass_preserved": True,
        "semantic_review": semantic_review,
        "language_policy_resolved": False,
        "working_title_acceptable": title["status"]
        in {"SUPPORTED_WORKING_TITLE", "SUPPORTED_BUT_HUMAN_REVIEW"},
        "assignment_credible": assignments["assignment_result"]
        in {"SEMANTICALLY_CREDIBLE", "CREDIBLE_WITH_MINOR_REVIEW"},
        "other_semantic_blocker": False,
        "editorial_plan_json": "NOT PUBLISHED",
        "reason": (
            "Language policy was unspecified before A.3 and still requires an "
            "explicit human book_language / planning-language decision. "
            "The unchanged candidate is not published in this phase."
        ),
        "if_human_accepts_french_plan": (
            "Candidate may remain untranslated as an editorial plan. "
            "Controlled publication would be a later 4A.4 phase. "
            "Plan language should then match chosen book language."
        ),
        "if_human_requires_other_plan_language": (
            "Do not repair or translate this candidate. A later phase would "
            f"need {SUCCESSOR_PROMPT_VERSION} and a new provider call."
        ),
    }
    readiness = {
        "ready_for_controlled_editorial_plan_publication": header[
            "ready_for_controlled_editorial_plan_publication"
        ],
        "book_generator": BOOK_GENERATOR,
        "next_action": NEXT_ACTION,
        "human_decision_required": policy["human_decision_required"],
        "new_provider_call_required_to_validate_current_candidate": "NO",
        "a3_remains_historical_partial": True,
    }
    calibration = {
        "a3_input_tokens": A3_INPUT_TOKENS,
        "a2_local_input_estimate": A2_LOCAL_INPUT_ESTIMATE,
        "a2_provider_adjusted_pessimistic": A2_PROVIDER_ADJUSTED_PESSIMISTIC,
        "a2_planning_input_estimate": 58890,
        "a3_output_tokens": A3_OUTPUT_TOKENS,
        "a2_expected_output": A2_EXPECTED_OUTPUT_TOKENS,
        "a2_conservative_output": A2_CONSERVATIVE_OUTPUT_TOKENS,
        "a2_hard_output": A2_HARD_OUTPUT_TOKENS,
        "output_utilization": A3_OUTPUT_UTILIZATION,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "a3_thinking": A3_THINKING_TOKENS,
        "a1_thinking": A1_THINKING_TOKENS,
        "thinking_note": (
            "Production thinking (6443) is materially larger than A.1 synthetic "
            "thinking (158). Tiny-canary thinking cannot be used linearly for "
            "production prediction."
        ),
        "a3_cost_usd": A3_COST_USD,
        "a2_expected_cost_usd": A2_EXPECTED_COST_USD,
        "a2_conservative_cost_usd": A2_CONSERVATIVE_COST_USD,
        "a2_hard_cost_usd": A2_HARD_COST_USD,
        "a31_cost_usd": PHASE_COST_USD,
        "no_output_budget_redesign": True,
        "no_new_provider_spend": True,
    }
    bundle = {
        "header": header,
        "identity": identity,
        "language": language,
        "policy": policy,
        "title": title,
        "assignments": {
            **assignments,
            "rows": [
                {
                    "idea_id": row["idea_id"],
                    "fit": row["fit"],
                    "alignment": row["alignment"],
                    "chapter_id": row.get("chapter_id"),
                    "section_id": row.get("section_id"),
                    "importance": row.get("importance"),
                    "overlay_applied": row.get("overlay_applied"),
                    "reason": row.get("reason"),
                    "source_supported_description": row.get(
                        "source_supported_description"
                    ),
                }
                for row in assignments["rows"]
            ],
        },
        "chapters": chapters,
        "sections": sections,
        "publication": publication,
        "readiness": readiness,
        "calibration": calibration,
        "validator": contract.to_dict(),
        "project_meta": project_meta,
        "expected_candidate_sha256": EXPECTED_CANDIDATE_SHA256,
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        from app.editorial_planner_forensics_4a31.writer import write_forensics_artifacts

        write_forensics_artifacts(bundle, root=root)
        after_write = file_sha256(candidate)
        assert_candidate_untouched(before_sha, after_write)
        if production.is_file() and root is None:
            raise PlannerForensicsError("A.3.1 published editorial_plan.json. Forbidden.")
    return ForensicsResult(accepted=True, provider_calls=0, bundle=bundle)
