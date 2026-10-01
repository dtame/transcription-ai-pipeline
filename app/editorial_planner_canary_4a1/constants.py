"""
Phase 4A.1 — tiny synthetic grammar + contract canary.

Isolated from production pastoral planning. Frozen Phase 4A identities
are recorded here; a mismatch blocks the provider call.
"""

from __future__ import annotations

from app.editorial_planning.constants import (
    EDITORIAL_PLAN_TRANSPORT_VERSION,
    EDITORIAL_PLANNER_PROMPT_VERSION,
    HARD_MAX_OUTPUT_TOKENS,
    MODEL,
    PROPOSED_MAX_OUTPUT_TOKENS,
    PROVIDER,
)

PHASE = "4A.1"
PHASE_NAME = "EDITORIAL_PLANNER_TINY_GRAMMAR_CONTRACT_CANARY"
CANARY_VERSION = "editorial-planner-canary-4a1-1.0"

AUTHORIZATION_SCOPE = "EDITORIAL_PLANNER_4A1_TINY_GRAMMAR_CONTRACT_CANARY_ONLY"

PROVIDER = PROVIDER
MODEL = MODEL
assert PROVIDER == "anthropic"
assert MODEL == "claude-opus-5"

PROMPT_VERSION = EDITORIAL_PLANNER_PROMPT_VERSION
TRANSPORT_VERSION = EDITORIAL_PLAN_TRANSPORT_VERSION
assert PROMPT_VERSION == "editorial-planner-1.0"
assert TRANSPORT_VERSION == "editorial-plan-transport-1.0"

STAGE_CANARY = "editorial_planner_canary_4a1"

MAX_ENGINE_GENERATE = 1
MAX_ANTHROPIC_POST = 1
MAX_ATTEMPTS = 1
RETRIES = 0

CANARY_MAX_OUTPUT_TOKENS = 4096
PRODUCTION_PROPOSED_MAX_OUTPUT = PROPOSED_MAX_OUTPUT_TOKENS
assert PRODUCTION_PROPOSED_MAX_OUTPUT == 16384
assert HARD_MAX_OUTPUT_TOKENS == 32000

# Phase 4A FakeAI full-scale output budget — preserved, not recomputed
# from this tiny canary and not used as canary max_output.
PHASE_4A_EXPECTED_OUTPUT_TOKENS = 4192
PHASE_4A_CONSERVATIVE_OUTPUT_TOKENS = 10822
PHASE_4A_HARD_OUTPUT_TOKENS = 21644
PRODUCTION_OUTPUT_BUDGET_REVIEW_REQUIRED = True

CANARY_CONNECT_TIMEOUT_SECONDS = 30.0
CANARY_READ_TIMEOUT_SECONDS = 180.0

# Phase 4A frozen schema identity (live recomputation must match).
PHASE_4A_RAW_SCHEMA_SHA256 = (
    "34e3f0656e1781b791a899deb89a53dc2bfd7d459e10d949776e6f28f3f1f509"
)
PHASE_4A_ADAPTED_SCHEMA_SHA256 = (
    "1cebcf97ed7fa5cfa4b4758d1eb1451b6770347e9508772e8287228a768ba77e"
)
PHASE_4A_RAW_SCHEMA_BYTES = 3661
PHASE_4A_ADAPTED_SCHEMA_BYTES = 3909

PHASE_4A_SYSTEM_SHA256 = (
    "7faeacaa81d123510c321d4756f3cd975d6b58460fdd9f216146d6a15efeeb55"
)
PHASE_4A_INSTRUCTIONS_SHA256 = (
    "e9193763e49859c03c1d30c9ef259163a05b371354cdca1979bf9b1db807294c"
)
PHASE_4A_PROMPT_SHA256 = (
    "1c2e8309ede9d7b5d4aed1c2b09f28437d8041b9efdf668f504527f8a7aef68a"
)

PROJECT_NAME = "community_garden_workshop_canary_4a1"
TRANSCRIPT_ID = "TR_CANARY_EP4A1"
CANARY_WINDOW_ID = "CANARY_EP4A1"

SYNTHETIC_SRC_IDS = (
    "SRC999101",
    "SRC999102",
    "SRC999103",
    "SRC999104",
    "SRC999105",
    "SRC999106",
    "SRC999107",
    "SRC999108",
)

FORBIDDEN_TRANSCRIPT_IDS = ("TR001",)
FORBIDDEN_WINDOW_IDS = (
    "WIN001",
    "WIN002",
    "WIN003",
    "WIN004",
    "WIN005",
    "WIN006",
    "WIN007",
)
PASTORAL_MARKERS = (
    "pastoral_retreat",
    "pastoral retreat",
    "pastoral_retreat_v2_validation",
    "WIN001",
    "WIN002",
    "WIN003",
    "WIN004",
    "WIN005",
    "WIN006",
    "WIN007",
    "SRC000001",
    "TR001",
    "df32f5943a21ed4013c5344d7579dbaaa46d35a77df342e1b2f6718794fc2855",
)

LOCK_NAME = "canary_real_call.lock"

AUDIT_DIRNAME = "editorial_planner_canary_4a1"
AUDIT_PRECALL = "editorial_planner_4a1_precall_identity.json"
AUDIT_FIXTURE = "editorial_planner_4a1_synthetic_fixture.json"
AUDIT_RESPONSE = "editorial_planner_4a1_response_identity.json"
AUDIT_THINKING = "editorial_planner_4a1_opus_thinking_observation.json"
AUDIT_CONTRACT = "editorial_planner_4a1_contract_validation.json"
AUDIT_SEMANTIC = "editorial_planner_4a1_semantic_review.json"
AUDIT_BUDGET = "editorial_planner_4a1_production_budget_status.json"
AUDIT_READINESS = "editorial_planner_post_4a1_readiness.json"
AUDIT_REQUEST = "editorial_planner_4a1_request_payload.json"
AUDIT_RAW_RESPONSE = "editorial_planner_4a1_raw_structured_response.json"
AUDIT_RECONSTRUCTED = "editorial_planner_4a1_reconstructed_plan.json"
AUDIT_EXECUTION = "editorial_planner_4a1_execution.json"
REPORT_NAME = "PHASE_4A1_EDITORIAL_PLANNER_TINY_GRAMMAR_CONTRACT_CANARY_REPORT.md"

NEXT_ACTION = "HUMAN REVIEW"
