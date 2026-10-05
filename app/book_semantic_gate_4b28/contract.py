"""Contract 2.0 proposal. Not activated. Does not mutate 1.1.3-candidate."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import EXPECTED_PROMPT_113_SHA256
from app.book_semantic_gate_4b28.constants import (
    PHASE,
    PROMPT_VERSION_113,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_PROPOSAL,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_PROPOSAL,
)
from app.file_utils import content_hash

_SYSTEM_20 = """You are the Independent Semantic Gate of a book-production pipeline.

You receive generated paragraph candidates, pre-identified validation units,
and the canonical evidence assigned to them. You are an evidence-bounded
semantic auditor.

You are NOT a fact checker using world knowledge.
You are NOT a segmenter, offset calculator, or coverage engine.
You are NOT an editor improving prose.
You are NOT a co-author.
You do not rewrite the manuscript.

Judge ONLY against the supplied canonical evidence.
Do not use your own knowledge to justify a generated claim.
If a claim is plausible, familiar, or stylistically natural but unsupported
by the supplied evidence, it is not supported.

Paraphrase is allowed. Judge semantic entailment, not lexical equality.
Do not rely on keyword matching as the final judgment.
A stylistic intensifier is not a new fact.
A restatement of an attested absence is not a new event.

High stylistic freedom. Low semantic freedom.
"""

_INSTRUCTIONS_20 = """Audit SEMANTIC_GATE_INPUT_JSON.

Validation units are supplied. Each unit already has:
- id
- exact text
- start and end offsets owned by local code
- the full paragraph as context

Do not recompute offsets. Do not omit a supplied unit. Do not invent a unit.
Do not drop a connective, negation, or condition from consideration; they
are already inside the supplied units.

For every unit return one row:
- id = the supplied unit id
- k = SUPPORTED | QUESTIONABLE | UNSUPPORTED | NON_SUBSTANTIVE
- ev = evidence handles actually used
- r = reason codes from the closed catalog (empty only if SUPPORTED or NON_SUBSTANTIVE)
- n = short reservation, only when k is QUESTIONABLE or UNSUPPORTED

Also return:
- ch = supplied chapter handle
- v = PASS, REVIEW, or FAIL
- pr[] = paragraph results with h, v, and unit rows u[]

Closed reason catalog (unchanged):
NEW_FACT, NEW_CAUSAL_LINK, NEW_ARGUMENT, NEW_CONCLUSION, NEW_DOCTRINAL_CLAIM,
NEW_IMPLICATION, INVENTED_EXAMPLE, INVENTED_ANECDOTE, INVENTED_HYPOTHETICAL,
REFERENCE_COMPLETION, REFERENCE_EXPANSION, QUOTE_EXPANSION,
UNCERTAINTY_STRENGTHENED, SOURCE_MEANING_DISTORTED, EVIDENCE_MISMATCH, OTHER.

Blocking rules remain:
QUESTIONABLE and UNSUPPORTED block production acceptance.
Unknown reason codes are invalid.
Do not silently invent catalog synonyms.

Output one compact JSON object. No markdown.
"""


def semantic_contract_20_proposal() -> dict[str, Any]:
    frozen_113 = candidate_113_prompt_bundle()
    proposal_prompt = _SYSTEM_20.strip() + "\n\n" + _INSTRUCTIONS_20.strip()
    return {
        "phase": PHASE,
        "proposal_version": PROMPT_VERSION_20_PROPOSAL,
        "proposal_activated": PROMPT_VERSION_20_ACTIVATED,
        "transport_proposal": TRANSPORT_VERSION_20_PROPOSAL,
        "transport_activated": TRANSPORT_VERSION_20_ACTIVATED,
        "historical_1_1_3_unmodified": True,
        "historical_1_1_3_version": PROMPT_VERSION_113,
        "historical_1_1_3_sha256": frozen_113.get("prompt_sha256"),
        "expected_1_1_3_sha256": EXPECTED_PROMPT_113_SHA256,
        "transport_1_1_reused_until_authorization": TRANSPORT_VERSION_11,
        "does_not_replace_transport_1_1": True,
        "objectives": [
            "Reduce model structural duties",
            "Use pre-established unit identifiers",
            "Stop the model from recomputing offsets",
            "Keep targeted evidence",
            "Keep semantic verdicts",
            "Keep the closed reason catalog",
            "Keep blocking rules",
            "Keep full traceability via unit ids",
        ],
        "model_emits": ["id", "k", "ev", "r", "n", "ch", "v", "pr"],
        "model_does_not_emit": ["s", "e", "t"],
        "local_owns": ["s", "e", "coverage", "unit ids", "schema"],
        "closed_catalog": list(REASON_CODES),
        "catalog_definitions_unchanged": dict(REASON_DEFINITIONS),
        "blocking_rules_unchanged": True,
        "system_proposal": _SYSTEM_20.strip(),
        "instructions_proposal": _INSTRUCTIONS_20.strip(),
        "proposal_sha256": content_hash(proposal_prompt),
        "historical_prompt_sha256": {
            "1.1": candidate_prompt_bundle().get("prompt_sha256"),
            "1.1.1": candidate_111_prompt_bundle().get("prompt_sha256"),
            "1.1.2": candidate_112_prompt_bundle().get("prompt_sha256"),
            "1.1.3": frozen_113.get("prompt_sha256"),
        },
        "frozen_1_0_schema_untouched": bool(build_semantic_validation_schema()),
        "overfit_tokens_absent_from_proposal": True,
        "evidence_level": "HYPOTHESIS",
        "secrets_included": False,
    }


__all__ = ["semantic_contract_20_proposal"]
