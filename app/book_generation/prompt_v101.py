"""
Successor prompt book-generator-1.0.1.

Does not mutate book-generator-1.0. Narrow contract hardening only:
non-empty paragraphs, connective non-substantiveness, no invented
examples/illustrations/hypotheticals/anecdotes, evidence-bounded
substantive prose, and a pre-return completeness/fidelity self-check.
Does not request chain-of-thought or exposed verification steps.
"""

from __future__ import annotations

from app.book_generation.constants import BOOK_GENERATOR_PROMPT_VERSION
from app.book_generation.prompt import (
    instruction_prompt as instruction_prompt_v10,
    prompt_fingerprint,
    system_prompt as system_prompt_v10,
)
from app.file_utils import content_hash

BOOK_GENERATOR_PROMPT_VERSION_V101 = "book-generator-1.0.1"

_SYSTEM_HARDENING = """
Non-empty paragraphs:
Never emit an empty paragraph or block. Every emitted paragraph must
contain meaningful manuscript text. If no paragraph is needed, omit
the paragraph object entirely.

Connective prose:
Connective prose may only connect, orient, or transition between
already-supported ideas. It must not introduce a new argument,
conclusion, factual claim, doctrinal claim, example, or implication
that is not supported by supplied evidence. This applies to section
closers, chapter closers, bridges, introductions, and transitions.
A provider label of kind=con is not proof that the paragraph is
non-substantive. If a paragraph introduces a new claim, treat it as
substantive and cite supplied evidence, or omit the claim.

Examples and illustrations:
Do not create new examples, illustrations, anecdotes, scenarios, or
hypotheticals. Use an example only when it is explicitly present in
the supplied canonical evidence. Do not add illustrative material
merely to improve readability, emotional impact, clarity, literary
quality, or chapter flow.

Source fidelity:
Stylistic expansion is allowed. Semantic expansion is not.
Every substantive sentence must remain bounded by the supplied
canonical evidence.
"""

_INSTRUCTION_HARDENING = """
Before returning the structured response, verify silently:
- every paragraph contains text;
- every substantive paragraph is supported by supplied evidence;
- connective prose introduces no new claim;
- no example, illustration, anecdote, or hypothetical was invented;
- every planned IDEA is represented;
- every planned section is present exactly once.
Do not expose internal reasoning or verification steps.
Return only the compliant structured output.
"""


def system_prompt() -> str:
    return system_prompt_v10().rstrip() + "\n" + _SYSTEM_HARDENING.strip() + "\n"


def instruction_prompt() -> str:
    return (
        instruction_prompt_v10().rstrip()
        + "\n\n"
        + _INSTRUCTION_HARDENING.strip()
        + "\n"
    )


def prompt_bundle() -> dict[str, str]:
    system = system_prompt()
    instructions = instruction_prompt()
    return {
        "version": BOOK_GENERATOR_PROMPT_VERSION_V101,
        "system": system,
        "instructions": instructions,
        "system_sha256": content_hash(system),
        "instructions_sha256": content_hash(instructions),
        "prompt_sha256": prompt_fingerprint(system, instructions),
        "historical_prompt_version": "book-generator-1.0",
        "historical_prompt_mutated": False,
    }


def render_user_prompt(bundle_json: str) -> str:
    return instruction_prompt() + "\nEVIDENCE_BUNDLE_JSON\n" + bundle_json + "\n"


assert BOOK_GENERATOR_PROMPT_VERSION == BOOK_GENERATOR_PROMPT_VERSION_V101
assert "p9b" not in system_prompt()
assert "funeral" not in system_prompt().lower()
assert "CH016" not in system_prompt()
assert "p9b" not in instruction_prompt()
assert "funeral" not in instruction_prompt().lower()
assert "CH016" not in instruction_prompt()

__all__ = [
    "BOOK_GENERATOR_PROMPT_VERSION_V101",
    "instruction_prompt",
    "prompt_bundle",
    "prompt_fingerprint",
    "render_user_prompt",
    "system_prompt",
]
