"""
Validateur du EditorialPlan.

Juge, ne répare pas. FAIL = violation de contrat. REVIEW = heuristique
de balance. PASS = aucun erreur ni avertissement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from app.editorial_planning.constants import (
    DEFERRAL_REASONS,
    EDITORIAL_ACTIONS,
    EDITORIAL_PLAN_SCHEMA_VERSION,
    EXCLUSION_REASONS,
    IDEA_DISPOSITIONS,
    VALIDATION_FAIL,
    VALIDATION_PASS,
    VALIDATION_REVIEW,
)
from app.editorial_planning.coverage import missing_idea_ids, valid_reason_for
from app.editorial_planning.errors import EditorialPlanValidationError
from app.editorial_planning.models import (
    EditorialPlan,
    scan_forbidden_plan_structure,
)
from app.editorial_planning.settings import PlannerSettings, frozen_production_settings
from app.source_analysis.models import SourceMap

_CHAPTER_ID = re.compile(r"^CH\d{3}$")
_SECTION_ID = re.compile(r"^SEC\d{3}$")
_IDEA_ID = re.compile(r"^IDEA\d{3,}$")
_TOP_ID = re.compile(r"^TOP\d{3,}$")
_EX_ID = re.compile(r"^EX\d{3,}$")
_REF_ID = re.compile(r"^REF\d{3,}$")
_UNC_ID = re.compile(r"^UNC\d{3,}$")
_REP_ID = re.compile(r"^REP\d{3,}$")


@dataclass(frozen=True)
class EditorialPlanValidation:
    status: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status != VALIDATION_FAIL

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_editorial_plan(
    plan: EditorialPlan,
    source_map: SourceMap,
    *,
    settings: PlannerSettings | None = None,
    payload: Mapping | None = None,
) -> EditorialPlanValidation:
    settings = settings or frozen_production_settings()
    errors: list[str] = []
    warnings: list[str] = []

    if payload is not None:
        leaked = scan_forbidden_plan_structure(payload)
        if leaked:
            errors.extend(f"structure interdite : {name}" for name in leaked)
    leaked_plan = scan_forbidden_plan_structure(plan.to_dict())
    if leaked_plan:
        errors.extend(f"structure interdite dans le plan : {name}" for name in leaked_plan)

    _validate_header(plan, source_map, errors)
    _validate_hierarchy(plan, errors)
    _validate_ids(plan, errors)
    _validate_references(plan, source_map, errors)
    _validate_coverage(plan, source_map, errors)
    _validate_traceability(plan, errors)
    _validate_invention(plan, errors)
    _validate_uncertainty(plan, source_map, warnings)
    _validate_balance(plan, settings, errors, warnings)
    _validate_stats(plan, errors)

    if errors:
        status = VALIDATION_FAIL
    elif warnings:
        status = VALIDATION_REVIEW
    else:
        status = VALIDATION_PASS
    return EditorialPlanValidation(
        status=status, errors=tuple(errors), warnings=tuple(warnings)
    )


def ensure_valid_editorial_plan(
    plan: EditorialPlan,
    source_map: SourceMap,
    *,
    settings: PlannerSettings | None = None,
) -> EditorialPlanValidation:
    result = validate_editorial_plan(plan, source_map, settings=settings)
    if result.status == VALIDATION_FAIL:
        raise EditorialPlanValidationError(list(result.errors))
    return result


def _validate_header(
    plan: EditorialPlan, source_map: SourceMap, errors: list[str]
) -> None:
    if plan.schema_version != EDITORIAL_PLAN_SCHEMA_VERSION:
        errors.append(
            f"schema_version {plan.schema_version!r} ≠ {EDITORIAL_PLAN_SCHEMA_VERSION}"
        )
    if not plan.project_name:
        errors.append("project.name vide")
    if plan.project_name != source_map.project_name:
        errors.append("project.name ≠ SourceMap.project")
    if not plan.book_concept.purpose or not plan.book_concept.core_subject:
        errors.append("book_concept incomplet")
    if not plan.selected_title:
        errors.append("selected_title vide")
    if not plan.title_candidates:
        errors.append("title_candidates vide")
    for candidate in plan.title_candidates:
        if not candidate.is_editorial_construct:
            errors.append("title candidate non marqué editorial construct")
        if not candidate.title:
            errors.append("title candidate vide")
    if not plan.editorial_angle:
        errors.append("editorial_angle vide")
    if not plan.target_reader:
        errors.append("target_reader vide")
    if not plan.editorial_strategy:
        errors.append("editorial_strategy vide")
    if not plan.chapters:
        errors.append("aucun chapitre")


def _validate_hierarchy(plan: EditorialPlan, errors: list[str]) -> None:
    for chapter in plan.chapters:
        if not chapter.sections:
            errors.append(f"{chapter.chapter_id} sans section")
        if not chapter.working_title:
            errors.append(f"{chapter.chapter_id} working_title vide")
        for section in chapter.sections:
            if not section.working_title:
                errors.append(f"{section.section_id} working_title vide")


def _validate_ids(plan: EditorialPlan, errors: list[str]) -> None:
    chapter_ids = [chapter.chapter_id for chapter in plan.chapters]
    section_ids = [section.section_id for section in plan.all_sections()]
    if len(chapter_ids) != len(set(chapter_ids)):
        errors.append("chapter_id dupliqué")
    if len(section_ids) != len(set(section_ids)):
        errors.append("section_id dupliqué")
    for index, chapter_id in enumerate(chapter_ids, start=1):
        expected = f"CH{index:03d}"
        if chapter_id != expected or not _CHAPTER_ID.match(chapter_id):
            errors.append(f"chapter_id {chapter_id!r} ≠ {expected}")
    for index, section_id in enumerate(section_ids, start=1):
        expected = f"SEC{index:03d}"
        if section_id != expected or not _SECTION_ID.match(section_id):
            errors.append(f"section_id {section_id!r} ≠ {expected}")


def _validate_references(
    plan: EditorialPlan, source_map: SourceMap, errors: list[str]
) -> None:
    known = {
        "IDEA": {idea.idea_id for idea in source_map.ideas},
        "TOP": {topic.topic_id for topic in source_map.topics},
        "EX": {item.example_id for item in source_map.examples},
        "REF": {item.reference_id for item in source_map.references},
        "UNC": {item.uncertainty_id for item in source_map.uncertainties},
        "REP": {item.repetition_id for item in source_map.repetitions},
    }
    for chapter in plan.chapters:
        _check_ref_list(chapter.topic_refs, known["TOP"], "TOP", chapter.chapter_id, errors)
        for section in chapter.sections:
            loc = section.section_id
            _check_ref_list(section.idea_refs, known["IDEA"], "IDEA", loc, errors)
            _check_ref_list(section.topic_refs, known["TOP"], "TOP", loc, errors)
            _check_ref_list(section.example_refs, known["EX"], "EX", loc, errors)
            _check_ref_list(section.reference_refs, known["REF"], "REF", loc, errors)
            _check_ref_list(section.uncertainty_refs, known["UNC"], "UNC", loc, errors)
            _check_ref_list(section.repetition_refs, known["REP"], "REP", loc, errors)
            _check_id_shape(section.idea_refs, _IDEA_ID, loc, errors)
            _check_id_shape(section.example_refs, _EX_ID, loc, errors)
            _check_id_shape(section.reference_refs, _REF_ID, loc, errors)
            _check_id_shape(section.uncertainty_refs, _UNC_ID, loc, errors)
            _check_id_shape(section.repetition_refs, _REP_ID, loc, errors)
            _check_id_shape(section.topic_refs, _TOP_ID, loc, errors)
            for action in list(section.editorial_actions) + list(
                chapter.editorial_actions
            ):
                if action.kind not in EDITORIAL_ACTIONS:
                    errors.append(f"{loc} action inconnue {action.kind!r}")


def _check_ref_list(
    refs: tuple[str, ...],
    known: set[str],
    kind: str,
    loc: str,
    errors: list[str],
) -> None:
    for ref in refs:
        if ref not in known:
            errors.append(f"{loc} référence {kind} inconnue : {ref}")


def _check_id_shape(refs: tuple[str, ...], pattern, loc: str, errors: list[str]) -> None:
    for ref in refs:
        if not pattern.match(ref):
            errors.append(f"{loc} identifiant mal formé : {ref}")


def _validate_coverage(
    plan: EditorialPlan, source_map: SourceMap, errors: list[str]
) -> None:
    missing = missing_idea_ids(plan, source_map)
    if missing:
        errors.append(
            "IDEA omise silencieusement : " + ", ".join(missing[:12])
            + (f" (+{len(missing) - 12})" if len(missing) > 12 else "")
        )
    coverage_ids = [item.idea_id for item in plan.idea_coverage]
    if len(coverage_ids) != len(set(coverage_ids)):
        errors.append("idea_coverage contient un IDEA dupliqué")
    known_sections = {section.section_id for section in plan.all_sections()}
    assigned_from_sections = plan.assigned_idea_ids()
    for item in plan.idea_coverage:
        if item.disposition not in IDEA_DISPOSITIONS:
            errors.append(
                f"{item.idea_id} disposition invalide ou manquante "
                f"({item.disposition!r})"
            )
            continue
        if item.disposition == "ASSIGNED":
            if item.idea_id not in assigned_from_sections:
                errors.append(f"{item.idea_id} ASSIGNED sans section")
            if item.primary_section_id not in known_sections:
                errors.append(
                    f"{item.idea_id} primary_section_id inconnu "
                    f"{item.primary_section_id!r}"
                )
            for extra in item.additional_section_ids:
                if extra not in known_sections:
                    errors.append(f"{item.idea_id} section extra inconnue {extra}")
        else:
            if not valid_reason_for(item.disposition, item.reason):
                allowed = (
                    EXCLUSION_REASONS
                    if item.disposition == "EXCLUDED"
                    else DEFERRAL_REASONS
                )
                errors.append(
                    f"{item.idea_id} {item.disposition} motif invalide "
                    f"{item.reason!r} (attendu {allowed})"
                )
            if item.idea_id in assigned_from_sections:
                errors.append(
                    f"{item.idea_id} {item.disposition} mais aussi assigné à une section"
                )


def _validate_traceability(plan: EditorialPlan, errors: list[str]) -> None:
    for section in plan.all_sections():
        if not section.idea_refs:
            errors.append(f"{section.section_id} sans IDEA (section vide / non traçable)")
        elif not section.source_refs:
            errors.append(
                f"{section.section_id} sans source_refs dérivés (traçabilité)"
            )


def _validate_invention(plan: EditorialPlan, errors: list[str]) -> None:
    for chapter in plan.chapters:
        if not any(section.idea_refs for section in chapter.sections):
            errors.append(
                f"{chapter.chapter_id} sans couverture IDEA (unité non supportée)"
            )


def _validate_uncertainty(
    plan: EditorialPlan, source_map: SourceMap, warnings: list[str]
) -> None:
    if source_map.uncertainties and not plan.uncertainty_handling.assigned_uncertainty_refs:
        warnings.append(
            "SourceMap contient des UNC mais aucune n'est rattachée au plan"
        )
    if "certainty" in plan.uncertainty_handling.policy.lower() and "not" not in plan.uncertainty_handling.policy.lower():
        warnings.append("uncertainty policy ambiguë")


def _validate_balance(
    plan: EditorialPlan,
    settings: PlannerSettings,
    errors: list[str],
    warnings: list[str],
) -> None:
    chapter_count = len(plan.chapters)
    if chapter_count < settings.min_chapters:
        warnings.append(
            f"nombre de chapitres {chapter_count} < min {settings.min_chapters}"
        )
    if chapter_count > settings.max_chapters:
        errors.append(
            f"nombre de chapitres {chapter_count} > max {settings.max_chapters}"
        )
    total_sections = sum(len(chapter.sections) for chapter in plan.chapters)
    if total_sections > settings.max_total_sections:
        errors.append(
            f"nombre de sections {total_sections} > max {settings.max_total_sections}"
        )
    assigned_total = max(1, plan.stats.assigned_idea_count)
    for chapter in plan.chapters:
        n_sections = len(chapter.sections)
        if n_sections < settings.min_sections_per_chapter:
            errors.append(
                f"{chapter.chapter_id} sections {n_sections} < min "
                f"{settings.min_sections_per_chapter}"
            )
        if n_sections > settings.max_sections_per_chapter:
            warnings.append(
                f"{chapter.chapter_id} sections {n_sections} > "
                f"{settings.max_sections_per_chapter}"
            )
        share = len(chapter.idea_refs) / assigned_total
        if share >= settings.max_chapter_idea_share_warn:
            warnings.append(
                f"{chapter.chapter_id} concentre {share:.0%} des IDEA assignées"
            )
        if (
            chapter_count >= settings.min_chapters
            and share <= settings.min_chapter_idea_share_warn
            and chapter.idea_refs
        ):
            warnings.append(
                f"{chapter.chapter_id} très petit ({share:.0%} des IDEA assignées)"
            )
        for section in chapter.sections:
            if len(section.idea_refs) > settings.max_ideas_per_section_warn:
                warnings.append(
                    f"{section.section_id} {len(section.idea_refs)} IDEA "
                    f"(seuil {settings.max_ideas_per_section_warn})"
                )
    reused = [item for item in plan.idea_coverage if item.additional_section_ids]
    if plan.stats.assigned_idea_count:
        ratio = len(reused) / plan.stats.assigned_idea_count
        if ratio > settings.max_reused_idea_ratio_warn:
            warnings.append(
                f"réutilisation IDEA {ratio:.0%} > {settings.max_reused_idea_ratio_warn:.0%}"
            )
    for item in reused:
        extra = 1 + len(item.additional_section_ids)
        if extra > settings.max_idea_reuse_count_warn:
            warnings.append(
                f"{item.idea_id} réutilisée {extra} fois "
                f"(seuil {settings.max_idea_reuse_count_warn})"
            )


def _validate_stats(plan: EditorialPlan, errors: list[str]) -> None:
    if plan.stats.chapter_count != len(plan.chapters):
        errors.append("stats.chapter_count incohérent")
    if plan.stats.section_count != len(plan.all_sections()):
        errors.append("stats.section_count incohérent")
    assigned = sum(1 for item in plan.idea_coverage if item.disposition == "ASSIGNED")
    if plan.stats.assigned_idea_count != assigned:
        errors.append("stats.assigned_idea_count incohérent")


def validator_contract_dict() -> dict:
    return {
        "validator_version": "editorial-plan-validator-1.0",
        "statuses": [VALIDATION_PASS, VALIDATION_REVIEW, VALIDATION_FAIL],
        "hard_failures": [
            "malformed hierarchy",
            "empty chapter",
            "empty section",
            "duplicate canonical ids",
            "unknown IDEA/TOP/EX/REF/UNC/REP",
            "silent missing IDEA",
            "invalid exclusion/deferral reason",
            "section without IDEA provenance",
            "invented unsupported unit",
            "forbidden manuscript/technical/nested keys",
        ],
        "review_heuristics": [
            "chapter count below preferred min",
            "overloaded chapter",
            "tiny chapter",
            "overloaded section",
            "excessive IDEA reuse",
            "uncertainties present in SourceMap but none assigned",
        ],
        "silent_idea_omission": "FAIL",
        "unknown_reference": "FAIL",
        "controlled_reuse": "REVIEW unless policy later says FAIL",
        "publication_requires": [
            "provider completion valid",
            "structured parse PASS",
            "transport decoder PASS",
            "reference validation PASS",
            "coverage PASS",
            "canonical reconstruction PASS",
            "canonical validator PASS",
            "semantic review acceptable",
        ],
        "phase4a_publication": "BLOCKED",
    }
