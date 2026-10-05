"""Isolated 1.1-candidate contracts. Never promoted. Never mutate 1.0."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.constants import (
    CLASSIFICATIONS,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
)
from app.book_semantic_gate_4b23.prompt import (
    instruction_prompt,
    prompt_fingerprint,
    system_prompt,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.book_semantic_gate_4b261.constants import (
    CANDIDATE_PROMPT_VERSION,
    CANDIDATE_TRANSPORT_VERSION,
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.file_utils import content_hash

_CANDIDATE_SYSTEM = """You are the Independent Semantic Gate of a book-production pipeline.

You receive generated paragraph candidates plus the canonical evidence
assigned to them. You are an evidence-bounded semantic auditor.

You are NOT a fact checker using world knowledge.
You are NOT a theologian, Bible commentator, historian, or legal scholar.
You are NOT an editor improving prose.
You are NOT a co-author.
You do not rewrite the manuscript.

Judge ONLY against the supplied canonical evidence.
Do not use your own knowledge to justify a generated claim.
If a claim is plausible, familiar, or stylistically natural but unsupported
by the supplied evidence, it is not supported.

Valid IDEA/SRC/REF handles are necessary hints, never sufficient proof.
A paragraph may cite correct handles and still contain an unsupported clause.

A partial reference — scripture, book, law, science, history, quotation, or
named authority — permits only what the supplied REF and SRC text actually
contain. Do not complete or expand omitted content from memory.
A correct reference identity does not license a remembered quotation.

Paraphrase is allowed. Judge semantic entailment, not lexical equality.
Synthesis across multiple supplied evidence items is allowed only if the
result does not exceed their combined support.

Treat new causal connectors carefully: because, therefore, thus, so that,
which means, as a result. They may create claims stronger than the evidence.
Do not rely on keyword matching as the final judgment.

Reject unjustified strengthening: sometimes→always, may→will,
associated with→causes, possible→certain, partial→complete.
Preserve canonical uncertainty.

Inspect connective prose if it contains substantive meaning.
The provider label "con" is not authoritative.
Purely rhetorical or structural transitions may be NON_SUBSTANTIVE.

Evaluate at claim level with paragraph anchoring.
Decompose every required paragraph into claims that together cover the
entire paragraph text. Give exact start and end offsets.
Do not skip a subordinate clause.

Classifications:
- SUPPORTED
- QUESTIONABLE
- UNSUPPORTED
- NON_SUBSTANTIVE

Use QUESTIONABLE when a clause is a close but unsupported semantic
extension, not a clearly invented fact.
Use UNSUPPORTED for invented examples, invented anecdotes, invented
hypotheticals, or claims with no supplied support.

Reason codes are machine-readable. Use only the supplied closed list.
Do not request or emit hidden chain-of-thought.
Do not copy claim text into the JSON. Offsets identify the span.
Do not write free-form essays. Reason codes carry the justification.
Add a short reservation only when QUESTIONABLE or UNSUPPORTED.

Unknown paragraph or evidence handles must be listed in uh.
Do not invent handles.

Respond only through the requested JSON object.
"""

_CANDIDATE_INSTRUCTIONS = """Audit SEMANTIC_GATE_INPUT_JSON.

For every paragraph in candidate.sections[].paras[] return one pr[] row.
For every paragraph, return claims c[] whose offsets [s,e) cover the full
paragraph text t, except whitespace.

Output one compact object:
- ch = the supplied chapter handle
- v = PASS, REVIEW, or FAIL
- pr[] = paragraph results
- pr[].h = paragraph handle
- pr[].v = SUPPORTED | QUESTIONABLE | UNSUPPORTED | NON_SUBSTANTIVE
- pr[].c[] = claims
- pr[].c[].i = claim index starting at 0
- pr[].c[].s = start offset
- pr[].c[].e = end offset
- pr[].c[].k = classification
- pr[].c[].ev = evidence handles actually used as support
- pr[].c[].r = reason codes (empty if SUPPORTED or NON_SUBSTANTIVE)
- pr[].c[].n = short reservation, only if QUESTIONABLE or UNSUPPORTED
- pr[].ev = evidence used for the paragraph
- pr[].r = paragraph reason codes
- sc = counts of claim classifications
- uh = unknown handles
- rr = true if any QUESTIONABLE claim exists

Do not emit pr[].c[].t. The caller recovers text from offsets.
Do not emit long explanations.
Do not emit confidence fields.

v = FAIL if any UNSUPPORTED claim exists or uh is non-empty.
v = REVIEW if any QUESTIONABLE claim exists and none are UNSUPPORTED.
v = PASS only if every required paragraph is present and every claim is
SUPPORTED or NON_SUBSTANTIVE.

Do not rewrite manuscript text.
Do not use evidence from other chapters unless approved_reuse says so.
"""


def candidate_system_prompt() -> str:
    return _CANDIDATE_SYSTEM.strip() + "\n"


def candidate_instruction_prompt() -> str:
    return _CANDIDATE_INSTRUCTIONS.strip() + "\n"


def candidate_prompt_bundle() -> dict[str, str]:
    system = candidate_system_prompt()
    instructions = candidate_instruction_prompt()
    return {
        "version": CANDIDATE_PROMPT_VERSION,
        "system": system,
        "instructions": instructions,
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "prompt_sha256": prompt_fingerprint(system, instructions),
        "historical_not_replaced": True,
        "historical_system_sha256": content_hash(system_prompt()),
        "historical_instructions_sha256": content_hash(instruction_prompt()),
    }


def render_candidate_user_prompt(gate_input_json: str) -> str:
    return candidate_instruction_prompt() + "\nSEMANTIC_GATE_INPUT_JSON\n" + gate_input_json + "\n"


def build_candidate_schema() -> dict[str, Any]:
    claim = {
        "type": "object",
        "required": ["i", "s", "e", "k", "ev", "r"],
        "properties": {
            "i": {"type": "integer", "description": "Claim index inside the paragraph."},
            "s": {"type": "integer", "description": "Inclusive start offset."},
            "e": {"type": "integer", "description": "Exclusive end offset."},
            "k": {"type": "string", "enum": list(CLASSIFICATIONS)},
            "ev": {"type": "array", "items": {"type": "string"}},
            "r": {
                "type": "array",
                "items": {"type": "string", "enum": list(REASON_CODES)},
            },
            "n": {
                "type": "string",
                "description": "Short reservation. Omit when SUPPORTED or NON_SUBSTANTIVE.",
            },
        },
    }
    paragraph = {
        "type": "object",
        "required": ["h", "v", "c", "ev", "r"],
        "properties": {
            "h": {"type": "string"},
            "v": {"type": "string", "enum": list(CLASSIFICATIONS)},
            "c": {"type": "array", "items": {"$ref": "#/$defs/claim"}},
            "ev": {"type": "array", "items": {"type": "string"}},
            "r": {
                "type": "array",
                "items": {"type": "string", "enum": list(REASON_CODES)},
            },
        },
    }
    counts = {
        "type": "object",
        "required": ["supported", "questionable", "unsupported", "non_substantive"],
        "properties": {
            "supported": {"type": "integer"},
            "questionable": {"type": "integer"},
            "unsupported": {"type": "integer"},
            "non_substantive": {"type": "integer"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": CANDIDATE_TRANSPORT_VERSION,
        "type": "object",
        "required": ["ch", "v", "pr", "sc", "uh", "rr"],
        "properties": {
            "ch": {"type": "string"},
            "v": {"type": "string", "enum": [VERDICT_PASS, VERDICT_REVIEW, VERDICT_FAIL]},
            "pr": {"type": "array", "items": {"$ref": "#/$defs/paragraph"}},
            "sc": counts,
            "uh": {"type": "array", "items": {"type": "string"}},
            "rr": {"type": "boolean"},
        },
        "$defs": {"claim": claim, "paragraph": paragraph},
    }


def candidate_schema_identity() -> dict[str, Any]:
    schema = build_candidate_schema()
    historical = build_semantic_validation_schema()
    raw = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    hist = json.dumps(historical, ensure_ascii=False, sort_keys=True)
    return {
        "transport_version": CANDIDATE_TRANSPORT_VERSION,
        "raw_schema_sha256": content_hash(raw),
        "raw_schema_bytes": len(raw.encode("utf-8")),
        "historical_transport_version": historical.get("title"),
        "historical_schema_sha256": content_hash(hist),
        "identical_to_historical": raw == hist,
        "promoted": False,
        "dropped_required_claim_fields": ["t", "x"],
        "dropped_optional_claim_fields": ["cf"],
        "added_optional_claim_fields": ["n"],
        "kept": ["i", "s", "e", "k", "ev", "r", "h", "v", "c", "ch", "sc", "uh", "rr"],
    }


def recover_claim_text(paragraph_text: str, start: int, end: int) -> str:
    return paragraph_text[int(start) : int(end)]


def expand_candidate_to_historical(
    payload: Mapping[str, Any],
    *,
    paragraph_texts: Mapping[str, str],
) -> dict[str, Any]:
    """Expand a 1.1-candidate payload to the 1.0 transport shape for local checks."""
    expanded = {
        "ch": payload.get("ch"),
        "v": payload.get("v"),
        "sc": dict(payload.get("sc") or {}),
        "uh": list(payload.get("uh") or []),
        "rr": payload.get("rr"),
        "pr": [],
    }
    for para in payload.get("pr") or []:
        handle = str(para.get("h") or "")
        text = str(paragraph_texts.get(handle) or "")
        claims = []
        for claim in para.get("c") or []:
            start = int(claim.get("s") or 0)
            end = int(claim.get("e") or 0)
            kind = str(claim.get("k") or "")
            note = str(claim.get("n") or "").strip()
            explanation = note
            if not explanation:
                if kind in {CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE}:
                    explanation = "span-only compact claim"
                else:
                    explanation = "reservation-required"
            claims.append(
                {
                    "i": claim.get("i"),
                    "t": recover_claim_text(text, start, end) or text or "missing-span",
                    "s": start,
                    "e": end,
                    "k": kind,
                    "ev": list(claim.get("ev") or []),
                    "r": list(claim.get("r") or []),
                    "x": explanation,
                    "cf": "HIGH",
                }
            )
        expanded["pr"].append(
            {
                "h": handle,
                "v": para.get("v"),
                "c": claims,
                "ev": list(para.get("ev") or []),
                "r": list(para.get("r") or []),
            }
        )
    return expanded


def compact_claim(
    index: int,
    *,
    start: int,
    end: int,
    kind: str,
    evidence: Sequence[str] | None = None,
    reasons: Sequence[str] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "i": index,
        "s": start,
        "e": end,
        "k": kind,
        "ev": list(evidence or []),
        "r": list(reasons or []),
    }
    if note and kind in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED}:
        row["n"] = note
    return row


__all__ = [
    "build_candidate_schema",
    "candidate_instruction_prompt",
    "candidate_prompt_bundle",
    "candidate_schema_identity",
    "candidate_system_prompt",
    "compact_claim",
    "expand_candidate_to_historical",
    "recover_claim_text",
    "render_candidate_user_prompt",
]
