"""
Constantes du Editorial Planner — Phase 4.

Aucune constante de corpus : pas de thème, pas de religion, pas de compteur
d'idées d'un projet de validation. Le SourceMap pastoral n'est qu'une donnée
d'entrée pour Phase 4A.
"""

from __future__ import annotations

PHASE = "4A"
PHASE_NAME = "EDITORIAL_PLANNER_ARCHITECTURE_AND_OFFLINE_FOUNDATION"

EDITORIAL_PLAN_SCHEMA_VERSION = "1.0"
EDITORIAL_PLANNER_PROMPT_VERSION = "editorial-planner-1.0"
EDITORIAL_PLAN_TRANSPORT_VERSION = "editorial-plan-transport-1.0"
IDEA_COVERAGE_POLICY_VERSION = "idea-coverage-1.0"
EDITORIAL_PLAN_VALIDATOR_VERSION = "editorial-plan-validator-1.0"
PLANNER_SETTINGS_VERSION = "editorial-planner-settings-1.0"

STAGE_EDITORIAL_PLANNING = "editorial_planning"
STRATEGY_GLOBAL = "global"

PROVIDER = "anthropic"
MODEL = "claude-opus-5"

# Publication interdite en Phase 4A. Le fichier canonique n'est pas écrit.
PUBLICATION_AUTHORIZED = False
EDITORIAL_PLAN_FILENAME = "editorial_plan.json"

HIERARCHY = ("BOOK", "CHAPTER", "SECTION")

IDEA_DISPOSITIONS = (
    "ASSIGNED",
    "DEFERRED",
    "EXCLUDED",
)

EXCLUSION_REASONS = (
    "non_substantive",
    "administrative",
    "duplicate_at_editorial_level",
    "outside_selected_book_scope",
)

DEFERRAL_REASONS = (
    "later_volume",
    "insufficient_support",
    "requires_uncertainty_resolution",
)

EDITORIAL_ACTIONS = (
    "REORDER",
    "GROUP",
    "SPLIT_TOPIC",
    "CONNECT",
    "DEFER",
    "EXCLUDE",
)

VALIDATION_PASS = "PASS"
VALIDATION_REVIEW = "REVIEW"
VALIDATION_FAIL = "FAIL"

# Bornes configurables — pas un nombre de chapitres figé.
DEFAULT_MIN_CHAPTERS = 2
DEFAULT_MAX_CHAPTERS = 40
DEFAULT_MIN_SECTIONS_PER_CHAPTER = 1
DEFAULT_MAX_SECTIONS_PER_CHAPTER = 20
DEFAULT_MAX_TOTAL_SECTIONS = 200
DEFAULT_MAX_IDEAS_PER_SECTION_WARN = 40
DEFAULT_MAX_CHAPTER_IDEA_SHARE_WARN = 0.60
DEFAULT_MIN_CHAPTER_IDEA_SHARE_WARN = 0.02
DEFAULT_MAX_IDEA_REUSE_COUNT_WARN = 3
DEFAULT_MAX_REUSED_IDEA_RATIO_WARN = 0.15
DEFAULT_MAX_TITLE_CANDIDATES = 8

# Sortie : proposition Phase 4A, pas le plafond modèle 128000.
PROPOSED_MAX_OUTPUT_TOKENS = 16384
CONSERVATIVE_MAX_OUTPUT_TOKENS = 24000
HARD_MAX_OUTPUT_TOKENS = 32000

# Préflight du projet de validation uniquement — jamais lu par la logique métier.
VALIDATION_PROJECT_NAME = "pastoral_retreat_v2_validation"
EXPECTED_SOURCE_MAP_SHA256 = (
    "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855"
)
EXPECTED_SOURCE_MAP_BYTES = 202398
EXPECTED_TOPIC_COUNT = 67
EXPECTED_IDEA_COUNT = 286
EXPECTED_EXAMPLE_COUNT = 49
EXPECTED_REFERENCE_COUNT = 59
EXPECTED_UNCERTAINTY_COUNT = 35
EXPECTED_REPETITION_COUNT = 0

AUDIT_INPUT_BUDGET = "editorial_planner_phase4a_input_budget.json"
AUDIT_OUTPUT_BUDGET = "editorial_planner_phase4a_output_budget.json"
AUDIT_CONTRACT = "editorial_planner_phase4a_contract.json"
AUDIT_SCHEMA_IDENTITY = "editorial_planner_phase4a_schema_identity.json"
AUDIT_COVERAGE_POLICY = "editorial_planner_phase4a_idea_coverage_policy.json"
AUDIT_VALIDATOR = "editorial_planner_phase4a_validator_contract.json"
AUDIT_FAKEAI = "editorial_planner_phase4a_fakeai_validation.json"
AUDIT_PREFLIGHT = "editorial_planner_phase4a_real_source_map_preflight.json"
AUDIT_READINESS = "editorial_planner_post_phase4a_readiness.json"
AUDIT_REPORT = "PHASE_4A_EDITORIAL_PLANNER_ARCHITECTURE_AND_OFFLINE_FOUNDATION_REPORT.md"

REAL_PROVIDER_CALLS_THIS_PHASE = 0

assert PUBLICATION_AUTHORIZED is False
assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
assert EDITORIAL_PLAN_SCHEMA_VERSION == "1.0"
assert PROVIDER == "anthropic"
assert MODEL == "claude-opus-5"
