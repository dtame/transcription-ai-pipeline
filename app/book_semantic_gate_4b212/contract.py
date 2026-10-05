"""Contract 2.0.2-candidate. Isolated. Does not mutate 2.0 or 2.0.1."""

from __future__ import annotations

import json
from typing import Any

from app.book_semantic_gate_4b23.reasons import REASON_CODES, REASON_DEFINITIONS
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import EXPECTED_PROMPT_113_SHA256
from app.book_semantic_gate_4b28.contract import semantic_contract_20_proposal
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.book_semantic_gate_4b210.contract import semantic_contract_201_candidate
from app.book_semantic_gate_4b212.constants import (
    CLASSIFICATIONS,
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    FORBIDDEN_MODEL_FIELDS,
    OPERATIONAL_DECISIONS,
    OVERFIT_TOKENS,
    PHASE,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_201_CANDIDATE,
    PROMPT_VERSION_202_ACTIVATED,
    PROMPT_VERSION_202_CANDIDATE,
    TECHNICAL_CONFORMANCE,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.file_utils import content_hash

_SYSTEM_202 = """You are the Independent Semantic Gate of a book-production pipeline.

You receive generated paragraph candidates, pre-identified validation units,
and the canonical evidence assigned to them. You are an evidence-bounded
semantic auditor.

You are NOT a fact checker using world knowledge.
You are NOT a segmenter, offset calculator, or coverage engine.
You are NOT an editor improving prose.
You are NOT a co-author.
You do not rewrite the manuscript.
You do not decide production acceptance.

Judge ONLY against the supplied canonical evidence.
Do not use your own knowledge to justify a generated claim.
If a claim is plausible, familiar, or stylistically natural but unsupported
by the supplied evidence, it is not supported.

High stylistic freedom. Low semantic freedom.

A generated unit may be rewritten, reordered, or restated.
That stylistic freedom does not authorize new facts, new examples,
new causal relations, new implications, universal guarantees absent
from the evidence, completed references without proof, or doctrinal
conclusions that the evidence does not attest.

Do not require the same words as the evidence.
Evaluate the complete meaning of each unit.
Consider the supplied evidence in its supplied context.
Accept a faithful reformulation.
Do not confuse a stylistic change with a factual addition.
Do not turn uncertainty into certainty.
Do not accept a causal relation merely because it seems plausible.
Do not accept an implication merely because it seems reasonable.

Emit semantic classifications only. Do not emit operational decisions.
Do not emit PASS, BLOCK, REVIEW, FAIL, VALID, or INVALID.

Semantic classifications (exact uppercase spelling required):

SUPPORTED
The unit is directly attested by the supplied evidence, or is a faithful
paraphrase of that evidence. Faithfulness does not require the same words.

QUESTIONABLE
The supplied evidence is not sufficient to conclude with enough confidence.
Do not automatically accept the unit.

UNSUPPORTED
The unit adds substantial unsupported content, or contradicts the evidence.
This includes a new causal relation, a new implication, a universal
guarantee, an unjustified strengthening, an invented example, or an
unsupported attribution.

NON_SUBSTANTIVE
A purely editorial element with no new assertion. This class must never
hide a substantial claim. A rhetorical sentence may still assert something.
An origin attribution may be substantial.
"""

_EXAMPLE_202 = {
    "ch": "C000",
    "pr": [
        {
            "h": "p00",
            "u": [
                {"id": "u00", "k": "SUPPORTED", "ev": ["SRC000001"], "r": []},
                {
                    "id": "u01",
                    "k": "QUESTIONABLE",
                    "ev": ["IDEA001"],
                    "r": ["EVIDENCE_MISMATCH"],
                    "n": "Evidence does not attest this strengthening.",
                },
                {
                    "id": "u02",
                    "k": "UNSUPPORTED",
                    "ev": ["SRC000001"],
                    "r": ["NEW_CAUSAL_LINK"],
                    "n": "Causal relation is not in the supplied evidence.",
                },
                {"id": "u03", "k": "NON_SUBSTANTIVE", "ev": [], "r": []},
            ],
        }
    ],
}

_INSTRUCTIONS_202 = """Audit SEMANTIC_GATE_INPUT_JSON.

Validation units are supplied by local code. Each unit already has a stable
identifier and exact text. The full paragraph is supplied once as context.
Offsets and coverage are owned locally. Do not recompute offsets. Do not
rebuild the segmentation. Do not omit a supplied unit. Do not invent a unit.
Do not copy unit text back in the response; return identifiers only.
Do not emit start or end offsets.

Return exactly this JSON object and no other top-level keys:
- ch = the supplied chapter handle (string)
- pr = array of exactly one paragraph object

Each paragraph object has exactly:
- h = the supplied paragraph handle (string)
- u = array of one row per supplied unit, in any order

Each unit row has:
- id = the supplied unit id (string, exact)
- k = one of SUPPORTED, QUESTIONABLE, UNSUPPORTED, NON_SUBSTANTIVE
      Exact uppercase. Never lowercase. Never PASS, BLOCK, REVIEW, FAIL,
      VALID, or INVALID.
- ev = array of evidence handles actually used, drawn from the supplied set
- r = array of reason codes from the closed catalog
      Empty array if and only if k is SUPPORTED or NON_SUBSTANTIVE
      At least one code if k is QUESTIONABLE or UNSUPPORTED
- n = short reservation string, required when k is QUESTIONABLE or
      UNSUPPORTED, omitted or empty otherwise

Do not emit:
- v
- sc
- uh
- rr
- paragraph-level v
- operational decisions
- technical conformance labels
- offsets
- unit text

Local Python code counts classifications, derives the paragraph
classification, and computes PASS, BLOCK, or REVIEW. The validator
decides VALID or INVALID. Do not perform those duties.

Closed reason catalog (unchanged, exact spelling):
NEW_FACT, NEW_CAUSAL_LINK, NEW_ARGUMENT, NEW_CONCLUSION, NEW_DOCTRINAL_CLAIM,
NEW_IMPLICATION, INVENTED_EXAMPLE, INVENTED_ANECDOTE, INVENTED_HYPOTHETICAL,
REFERENCE_COMPLETION, REFERENCE_EXPANSION, QUOTE_EXPANSION,
UNCERTAINTY_STRENGTHENED, SOURCE_MEANING_DISTORTED, EVIDENCE_MISMATCH, OTHER.

Unknown reason codes are invalid.
Do not silently invent catalog synonyms.
Do not complete missing units.
Do not repair invalid evidence handles.

Output one compact JSON object. No markdown.

Strictly conforming example (identifiers are illustrative, not labels):
""" + json.dumps(_EXAMPLE_202, ensure_ascii=False, separators=(",", ":"))


def _overfit_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    for token in OVERFIT_TOKENS:
        needle = str(token or "").strip().lower()
        if needle and needle in lowered:
            hits.append(token)
    return hits


def semantic_contract_202_candidate() -> dict[str, Any]:
    frozen_20 = semantic_contract_20_candidate()
    frozen_201 = semantic_contract_201_candidate()
    frozen_113 = candidate_113_prompt_bundle()
    proposal = semantic_contract_20_proposal()
    prompt = _SYSTEM_202.strip() + "\n\n" + _INSTRUCTIONS_202.strip()
    overfit = _overfit_hits(prompt)
    example = json.loads(json.dumps(_EXAMPLE_202))
    return {
        "phase": PHASE,
        "candidate_version": PROMPT_VERSION_202_CANDIDATE,
        "candidate_activated": PROMPT_VERSION_202_ACTIVATED,
        "does_not_overwrite_2_0_candidate": True,
        "does_not_overwrite_2_0_1_candidate": True,
        "predecessor_2_0_candidate": PROMPT_VERSION_20_CANDIDATE,
        "predecessor_2_0_sha256": frozen_20.get("candidate_sha256"),
        "predecessor_2_0_1_candidate": PROMPT_VERSION_201_CANDIDATE,
        "predecessor_2_0_1_sha256": frozen_201.get("candidate_sha256"),
        "transport_reused": TRANSPORT_VERSION_20_CANDIDATE,
        "transport_activated": False,
        "new_transport_not_created": True,
        "proposal_sha256": proposal.get("proposal_sha256"),
        "historical_1_1_3_unmodified": True,
        "historical_1_1_3_sha256": frozen_113.get("prompt_sha256"),
        "expected_1_1_3_sha256": EXPECTED_PROMPT_113_SHA256,
        "field_definitions": {
            "ch": {
                "type": "string",
                "required": True,
                "description": "Supplied chapter handle. Exact match.",
            },
            "pr": {
                "type": "array",
                "required": True,
                "length": 1,
                "description": "Exactly one paragraph result.",
            },
            "pr[].h": {
                "type": "string",
                "required": True,
                "description": "Supplied paragraph handle. Exact match.",
            },
            "pr[].u": {
                "type": "array",
                "required": True,
                "description": "One row per supplied unit identifier.",
            },
            "pr[].u[].id": {
                "type": "string",
                "required": True,
                "case": "exact_supplied_identifier",
            },
            "pr[].u[].k": {
                "type": "string",
                "required": True,
                "allowed": list(CLASSIFICATIONS),
                "case": "exact_uppercase",
                "forbidden": list(OPERATIONAL_DECISIONS) + ["FAIL", "VALID", "INVALID"],
            },
            "pr[].u[].ev": {
                "type": "array[string]",
                "required": True,
                "description": "Evidence handles actually used, subset of supplied set.",
            },
            "pr[].u[].r": {
                "type": "array[string]",
                "required": True,
                "allowed": list(REASON_CODES),
                "empty_iff": [CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE],
            },
            "pr[].u[].n": {
                "type": "string",
                "required_when": [CLASS_QUESTIONABLE, CLASS_UNSUPPORTED],
                "omitted_or_empty_otherwise": True,
            },
        },
        "allowed_values": {
            "k": list(CLASSIFICATIONS),
            "r": list(REASON_CODES),
        },
        "exact_case": {
            "classifications": "uppercase_only",
            "reason_codes": "uppercase_with_underscores",
            "no_lowercase_aliases": True,
        },
        "unit_structure": ["id", "k", "ev", "r", "n?"],
        "evidence_structure": "array of supplied canonical handles",
        "paragraph_classification": {
            "emitted_by_model": False,
            "computed_by_python": True,
            "rule": "worst unit k: UNSUPPORTED > QUESTIONABLE > SUPPORTED > NON_SUBSTANTIVE",
        },
        "operational_decision_excluded_from_model": True,
        "operational_decision_owner": "python",
        "operational_values": {
            DECISION_PASS: "all substantive SUPPORTED, contract valid, coverage valid",
            DECISION_REVIEW: "QUESTIONABLE present, no UNSUPPORTED, contract valid",
            DECISION_BLOCK: "UNSUPPORTED, invalid contract, invalid coverage, or technical anomaly",
        },
        "technical_conformance_owner": "validator",
        "technical_values": list(TECHNICAL_CONFORMANCE),
        "model_emits": ["ch", "pr", "pr.h", "pr.u", "id", "k", "ev", "r", "n"],
        "model_must_not_emit": list(FORBIDDEN_MODEL_FIELDS) + ["pr.v", "s", "e", "t"],
        "reason_codes": list(REASON_CODES),
        "catalog_definitions_unchanged": dict(REASON_DEFINITIONS),
        "example_json": example,
        "example_strictly_conformant": True,
        "paraphrase_instructions_preserved": True,
        "invention_protections_preserved": True,
        "human_labels_absent_from_provider_prompt": True,
        "system_candidate": _SYSTEM_202.strip(),
        "instructions_candidate": _INSTRUCTIONS_202.strip(),
        "candidate_sha256": content_hash(prompt),
        "overfit_tokens_in_prompt": overfit,
        "overfit_tokens_absent_from_candidate": not overfit,
        "historical_prompt_sha256": {
            "1.1": candidate_prompt_bundle().get("prompt_sha256"),
            "1.1.1": candidate_111_prompt_bundle().get("prompt_sha256"),
            "1.1.2": candidate_112_prompt_bundle().get("prompt_sha256"),
            "1.1.3": frozen_113.get("prompt_sha256"),
            "2.0": frozen_20.get("candidate_sha256"),
            "2.0.1": frozen_201.get("candidate_sha256"),
        },
        "frozen_1_0_schema_untouched": bool(build_semantic_validation_schema()),
        "differs_from_2_0": content_hash(prompt) != frozen_20.get("candidate_sha256"),
        "differs_from_2_0_1": content_hash(prompt) != frozen_201.get("candidate_sha256"),
        "no_silent_pass_to_supported": True,
        "no_silent_uppercase_to_lowercase": True,
        "evidence_level": "HYPOTHESIS",
        "secrets_included": False,
    }


def build_response_schema_202() -> dict[str, Any]:
    """Local JSON schema for 2.0.2. Not sent to a provider in this phase."""
    string = {"type": "string"}
    unit = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "k", "ev", "r"],
        "properties": {
            "id": {**string, "description": "Pre-established unit identifier."},
            "k": {
                "type": "string",
                "enum": list(CLASSIFICATIONS),
                "description": "Semantic classification. Exact uppercase.",
            },
            "ev": {"type": "array", "items": {"type": "string"}},
            "r": {
                "type": "array",
                "items": {"type": "string", "enum": list(REASON_CODES)},
            },
            "n": {**string, "description": "Reservation when QUESTIONABLE or UNSUPPORTED."},
        },
    }
    paragraph = {
        "type": "object",
        "additionalProperties": False,
        "required": ["h", "u"],
        "properties": {
            "h": {**string, "description": "Paragraph handle."},
            "u": {"type": "array", "items": {"$ref": "#/$defs/unit"}},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": PROMPT_VERSION_202_CANDIDATE,
        "type": "object",
        "additionalProperties": False,
        "required": ["ch", "pr"],
        "properties": {
            "ch": {**string, "description": "Chapter handle."},
            "pr": {
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {"$ref": "#/$defs/paragraph"},
            },
        },
        "$defs": {"unit": unit, "paragraph": paragraph},
    }


__all__ = ["build_response_schema_202", "semantic_contract_202_candidate"]
