"""Contract 2.0 candidate. Isolated. Does not mutate 1.1.3-candidate or 2.0-proposal."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import EXPECTED_PROMPT_113_SHA256
from app.book_semantic_gate_4b28.contract import semantic_contract_20_proposal
from app.book_semantic_gate_4b29.constants import (
    CLASSIFICATIONS,
    OFFSET_CONVENTION,
    OVERFIT_TOKENS,
    PHASE,
    PROMPT_VERSION_113,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_20_PROPOSAL,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
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

Paraphrase is allowed. A faithful paraphrase may be SUPPORTED.
Judge semantic entailment, not lexical equality.
Do not rely on keyword matching as the final judgment.
A stylistic intensifier is not a new fact.
A restatement of an attested absence is not a new event.

A plausible implication that is not demonstrated must not be accepted
automatically. A new causal relation must be reported. An unsupported
universal guarantee must be rejected. A rhetorical sentence is not
automatically NON_SUBSTANTIVE. An origin attribution may be an assertion
that still requires evidence.

High stylistic freedom. Low semantic freedom.
"""

_INSTRUCTIONS_20 = """Audit SEMANTIC_GATE_INPUT_JSON.

Validation units are supplied by local code. Each unit already has a stable
identifier and exact text. The full paragraph is supplied once as context.
Offsets and coverage are owned locally. Do not recompute offsets. Do not
rebuild the segmentation. Do not omit a supplied unit. Do not invent a unit.
Do not copy unit text back in the response; return identifiers only.

For every supplied unit return one row:
- id = the supplied unit id
- k = SUPPORTED | QUESTIONABLE | UNSUPPORTED | NON_SUBSTANTIVE
- ev = evidence handles actually used, drawn from the supplied set
- r = reason codes from the closed catalog (empty only if SUPPORTED or NON_SUBSTANTIVE)
- n = short reservation, only when k is QUESTIONABLE or UNSUPPORTED

Also return:
- ch = supplied chapter handle
- v = PASS, REVIEW, or FAIL
- pr[] = paragraph results with h, v, and unit rows u[]
- sc = counts of k values
- uh = unknown handles (must be empty when all units are known)
- rr = true when human review is required

Closed reason catalog (unchanged):
NEW_FACT, NEW_CAUSAL_LINK, NEW_ARGUMENT, NEW_CONCLUSION, NEW_DOCTRINAL_CLAIM,
NEW_IMPLICATION, INVENTED_EXAMPLE, INVENTED_ANECDOTE, INVENTED_HYPOTHETICAL,
REFERENCE_COMPLETION, REFERENCE_EXPANSION, QUOTE_EXPANSION,
UNCERTAINTY_STRENGTHENED, SOURCE_MEANING_DISTORTED, EVIDENCE_MISMATCH, OTHER.

Blocking rules remain:
QUESTIONABLE and UNSUPPORTED block production acceptance.
Unknown reason codes are invalid.
Do not silently invent catalog synonyms.
Do not complete missing units.
Do not repair invalid evidence handles.

Output one compact JSON object. No markdown.
"""


def _overfit_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    for token in OVERFIT_TOKENS:
        needle = str(token or "").strip().lower()
        if needle and needle in lowered:
            hits.append(token)
    return hits


def semantic_contract_20_candidate() -> dict[str, Any]:
    frozen_113 = candidate_113_prompt_bundle()
    proposal = semantic_contract_20_proposal()
    prompt = _SYSTEM_20.strip() + "\n\n" + _INSTRUCTIONS_20.strip()
    overfit = _overfit_hits(prompt)
    return {
        "phase": PHASE,
        "candidate_version": PROMPT_VERSION_20_CANDIDATE,
        "candidate_activated": PROMPT_VERSION_20_ACTIVATED,
        "transport_candidate": TRANSPORT_VERSION_20_CANDIDATE,
        "transport_activated": TRANSPORT_VERSION_20_ACTIVATED,
        "proposal_version_unmodified": PROMPT_VERSION_20_PROPOSAL,
        "proposal_sha256": proposal.get("proposal_sha256"),
        "historical_1_1_3_unmodified": True,
        "historical_1_1_3_version": PROMPT_VERSION_113,
        "historical_1_1_3_sha256": frozen_113.get("prompt_sha256"),
        "expected_1_1_3_sha256": EXPECTED_PROMPT_113_SHA256,
        "does_not_replace_transport_1_1": True,
        "transport_1_1_preserved": TRANSPORT_VERSION_11,
        "offset_convention": OFFSET_CONVENTION,
        "objectives": [
            "Reduce model structural duties",
            "Use pre-established unit identifiers",
            "Stop the model from recomputing offsets",
            "Keep the full paragraph as compact context",
            "Keep targeted evidence",
            "Preserve semantic fidelity rules",
            "Preserve the closed reason catalog",
            "Preserve blocking verdicts",
            "Reduce structural generation requirements",
        ],
        "model_emits": ["id", "k", "ev", "r", "n", "ch", "v", "pr", "sc", "uh", "rr"],
        "model_does_not_emit": ["s", "e", "t"],
        "local_owns": ["s", "e", "coverage", "unit ids", "schema", "offsets"],
        "classifications": list(CLASSIFICATIONS),
        "closed_catalog": list(REASON_CODES),
        "catalog_definitions_unchanged": dict(REASON_DEFINITIONS),
        "blocking_rules_unchanged": True,
        "paraphrase_may_be_supported": True,
        "undemonstrated_implication_not_auto_accepted": True,
        "new_causality_must_be_flagged": True,
        "unsupported_universal_guarantee_rejected": True,
        "rhetorical_not_automatically_non_substantive": True,
        "origin_attribution_may_be_an_assertion": True,
        "human_labels_absent_from_provider_prompt": True,
        "system_candidate": _SYSTEM_20.strip(),
        "instructions_candidate": _INSTRUCTIONS_20.strip(),
        "candidate_sha256": content_hash(prompt),
        "overfit_tokens_in_prompt": overfit,
        "overfit_tokens_absent_from_candidate": not overfit,
        "historical_prompt_sha256": {
            "1.1": candidate_prompt_bundle().get("prompt_sha256"),
            "1.1.1": candidate_111_prompt_bundle().get("prompt_sha256"),
            "1.1.2": candidate_112_prompt_bundle().get("prompt_sha256"),
            "1.1.3": frozen_113.get("prompt_sha256"),
        },
        "frozen_1_0_schema_untouched": bool(build_semantic_validation_schema()),
        "evidence_level": "HYPOTHESIS",
        "secrets_included": False,
    }


__all__ = ["semantic_contract_20_candidate"]
