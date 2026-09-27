"""
window-analysis-1.3 — extraction sémantique LOCALE à handles symboliques.

Ne modifie pas window-analysis-1.0 / 1.1 / 1.2 / 1.2.1.
"""

from __future__ import annotations

from typing import Any

from app.ai.estimation import estimate_tokens
from app.file_utils import content_hash
from app.source_analysis.canonical_vocabulary import (
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis.models import CONFIDENCE_LEVELS
from app.source_analysis.prompt import FORBIDDEN_STRUCTURE_BLOCK, build_language_directive
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.constants import ESTIMATION_MODEL
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_hybrid.materialize import WindowContent, materialize_window_content
from app.source_analysis_local_v2.constants import (
    DEFERRED_KINDS,
    HARD_CEILINGS,
    LOCAL_KINDS,
    OVERFLOW_TOKEN,
    OVERFLOW_UNCERTAINTY_KIND,
    OVERFLOW_UNCERTAINTY_SEVERITY,
    SOFT_TARGETS,
    SOURCE_REFS_HARD_MAX,
    TOTAL_HARD_CEILING,
    TOTAL_SOFT_TARGET,
)
from app.source_analysis_local_v2.granularity import TEXT_HARD_LIMITS
from app.source_analysis_local_v2.prompt import (
    _OWNERSHIP_BLOCK,
    _COMPACT_BLOCK,
    _FIDELITY_BLOCK,
    _ROLE_BLOCK,
    _SCOPE_BLOCK,
    _render_context,
    _render_owned,
)
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)

WINDOW_PROMPT_ROLE = "LOCAL SEMANTIC EXTRACTOR"


def _budget_lines() -> str:
    rows = [f"{kind} cible {SOFT_TARGETS[kind]} / plafond {HARD_CEILINGS[kind]}" for kind in LOCAL_KINDS]
    rows.append(f"TOTAL cible {TOTAL_SOFT_TARGET} / plafond {TOTAL_HARD_CEILING}")
    return "\n".join(rows)


_HANDLE_RULES_BLOCK = """HANDLE RULES

Assign local topic labels T1, T2, T3...
Assign local idea labels I1, I2, I3...
Use those exact labels when expressing relationships.
Do not calculate record indexes. Do not count positions. Do not use 0, 1, 2 as links.

h = owner label of THIS record.
TOPIC owns a T label. IDEA owns an I label.
RELATION, EXAMPLE, REFERENCE, UNCERTAINTY own no label : h="".

l = the same labels, used as targets.
Forward labels are legal. Resolution happens after the full records[] list.
Labels need not be gap-free. T1 and T3 are legal if T2 is unused.
Each owner label must be unique in its type. Unknown labels are invalid.

RELATION and EXAMPLE may NEVER target T handles.
IDEA may NEVER target I handles.

TOPIC : h=Tn ; l=[] required
IDEA : h=In ; l = zero or more T labels
RELATION : h="" ; l = exactly two distinct I labels [from, to] ; type in v
EXAMPLE : h="" ; l = I labels ; empty only if no local IDEA exists
REFERENCE : h="" ; l=[] required
UNCERTAINTY : h="" ; l=[] required

Correct compact example (2 TOPIC, 3 IDEA, 1 RELATION, 1 EXAMPLE):
{"k":"TOPIC","v":"Planning","s":["SRC999001"],"h":"T1","l":[],"m":["Careful plans."]}
{"k":"TOPIC","v":"Checking","s":["SRC999002"],"h":"T2","l":[],"m":["Verify twice."]}
{"k":"IDEA","v":"Planning reduces mistakes.","s":["SRC999001"],"h":"I1","l":["T1"],"m":["claim","central"]}
{"k":"IDEA","v":"A second check catches gaps.","s":["SRC999002"],"h":"I2","l":["T2"],"m":["claim","supporting"]}
{"k":"IDEA","v":"Checking serves planning.","s":["SRC999002"],"h":"I3","l":["T1","T2"],"m":["claim","supporting"]}
{"k":"RELATION","v":"supports","s":[],"h":"","l":["I3","I1"],"m":[]}
{"k":"EXAMPLE","v":"Check the plan twice.","s":["SRC999002"],"h":"","l":["I2"],"m":["anecdote"]}

Recommended first-emitted order: first TOPIC=T1, second TOPIC=T2, first IDEA=I1.
Order is recommended, not required. Uniqueness and type matter more than gaps.

Recommended kind order: TOPIC, IDEA, RELATION, EXAMPLE, REFERENCE, UNCERTAINTY.
Kind order is not required."""


def _vocabulary_block_v13() -> str:
    return "\n".join(
        [
            "IDENTIFIANTS CONTRÔLÉS — copie exacte",
            f"idea.kind : {', '.join(IDEA_KINDS)}",
            f"idea.importance : {', '.join(IMPORTANCE_LEVELS)}",
            f"relation.type : {', '.join(RELATION_KINDS)}",
            f"example.kind : {', '.join(EXAMPLE_KINDS)}",
            f"reference.kind : {', '.join(REFERENCE_KINDS)}",
            f"reference.completeness : {', '.join(REFERENCE_COMPLETENESS)}",
            f"uncertainty.kind : {', '.join(UNCERTAINTY_KINDS)}",
            f"uncertainty.severity : {', '.join(SEVERITY_LEVELS)}",
            f"confidence : {', '.join(CONFIDENCE_LEVELS)}",
            "TOPIC : v=label ; m=[summary] ; s=SRC ; h=T1… ; l=[]",
            "IDEA : v=summary ; m=[kind, importance] ; h=I1… ; l=T labels ; s=SRC",
            "RELATION : v=type ; h=\"\" ; l=[from I, to I] ; s=[]",
            "EXAMPLE : v=summary ; m=[kind] ; h=\"\" ; l=I labels ; s=SRC",
            "REFERENCE : v=raw ; m=[kind, completeness, normalized] ; s=SRC ; h=\"\" ; l=[]",
            "UNCERTAINTY : v=desc ; m=[kind, severity] ; s=SRC ; h=\"\" ; l=[]",
        ]
    )


_TASK_BLOCK_V13 = f"""TÂCHE

Réponds en JSON ultra-compact ({SEMANTIC_TRANSPORT_VERSION_V3}) :

{{"theme":"...","intent":"...","ic":"...","aud":"...","ac":"...","records":[{{"k":"...","v":"...","s":[],"h":"","l":[],"m":[]}}]}}

Kinds locaux autorisés uniquement :
{', '.join(LOCAL_KINDS)}

Kinds interdits ici :
{', '.join(DEFERRED_KINDS)}

ic / ac = jetons confidence.
h = local owner label (T1… / I1…). Empty for RELATION, EXAMPLE, REFERENCE, UNCERTAINTY.
l[] = those exact labels as targets. Never numeric record indexes. Never self-link.

CIBLES / PLAFONDS :
{_budget_lines()}

source_refs : SRC réels, maximum {SOURCE_REFS_HARD_MAX} par record.
TOPIC.v ≤ {TEXT_HARD_LIMITS['TOPIC.v']} ; IDEA.v ≤ {TEXT_HARD_LIMITS['IDEA.v']}.

Si capacité insuffisante : UNCERTAINTY v={OVERFLOW_TOKEN}
m=["{OVERFLOW_UNCERTAINTY_KIND}","{OVERFLOW_UNCERTAINTY_SEVERITY}"]
s = au moins un SRC owned.

Sortie : uniquement le transport. Pas de raisonnement écrit."""


def build_window_system_prompt_v13(primary_language: str) -> str:
    return "\n\n".join(
        [
            _ROLE_BLOCK,
            _SCOPE_BLOCK,
            _COMPACT_BLOCK,
            _OWNERSHIP_BLOCK,
            _FIDELITY_BLOCK,
            FORBIDDEN_STRUCTURE_BLOCK,
            _vocabulary_block_v13(),
            _HANDLE_RULES_BLOCK,
            build_language_directive(primary_language),
        ]
    )


def build_window_user_prompt_v13(
    transcript: TranscriptInput,
    window: WindowInput,
    content: WindowContent | None = None,
) -> str:
    materialized = content or materialize_window_content(transcript, window)
    return "\n\n".join(
        [
            _TASK_BLOCK_V13,
            _HANDLE_RULES_BLOCK,
            build_language_directive(transcript.primary_language),
            (
                f"WINDOW — {window.window_id} — transcript {transcript.transcript_id} — "
                f"{window.owned_src_count} owned SRC, "
                f"{window.context_src_count} context-only SRC"
            ),
            "Notes locales compactes seulement. Pas de métadonnées globales finales.",
            _render_owned(materialized),
            _render_context(materialized),
        ]
    )


def window_prompt_v13_sha256(system_prompt: str) -> str:
    return content_hash(system_prompt)


def window_prompt_v13_fingerprint(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<LOCAL_V3_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<LOCAL_V3_USER>>>\n"
        + (user_prompt or "")
    )


def estimate_v13_request_tokens(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    content: WindowContent | None = None,
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    materialized = content or materialize_window_content(transcript, window)
    system = build_window_system_prompt_v13(transcript.primary_language)
    user = build_window_user_prompt_v13(transcript, window, materialized)
    total = estimate_tokens("\n".join([system, user]), model=model)
    return {
        "model": model,
        "method": total.method,
        "estimated": True,
        "total_tokens": total.tokens,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
        "transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
    }


_SRC_COPY_BLOCK_V131 = """SOURCE IDENTIFIERS

Copy every SRC identifier EXACTLY from the supplied source.
SRC identifiers are case-sensitive.
Never generate an SRC identifier from memory or from its number.
Never change prefix, case, zero padding, or digits.
If a record is supported by multiple segments, copy each exact ID.
Never cite an SRC that is not present in the supplied window."""


def _handle_rules_v131() -> str:
    return _HANDLE_RULES_BLOCK.replace(
        "EXAMPLE : h=\"\" ; l = I labels ; empty only if no local IDEA exists",
        "EXAMPLE : h=\"\" ; l = I labels of the idea(s) this example supports ; "
        "l=[] allowed if no appropriate extracted IDEA exists. Grounding stays in s[].",
    )


def _vocabulary_block_v131() -> str:
    return _vocabulary_block_v13().replace(
        "EXAMPLE : v=summary ; m=[kind] ; h=\"\" ; l=I labels ; s=SRC",
        "EXAMPLE : v=summary ; m=[kind] ; h=\"\" ; l=I labels or [] ; s=SRC",
    )


def build_window_system_prompt_v131(primary_language: str) -> str:
    return "\n\n".join(
        [
            _ROLE_BLOCK,
            _SCOPE_BLOCK,
            _COMPACT_BLOCK,
            _OWNERSHIP_BLOCK,
            _FIDELITY_BLOCK,
            FORBIDDEN_STRUCTURE_BLOCK,
            _vocabulary_block_v131(),
            _handle_rules_v131(),
            _SRC_COPY_BLOCK_V131,
            build_language_directive(primary_language),
        ]
    )


def build_window_user_prompt_v131(
    transcript: TranscriptInput,
    window: WindowInput,
    content: WindowContent | None = None,
) -> str:
    materialized = content or materialize_window_content(transcript, window)
    return "\n\n".join(
        [
            _TASK_BLOCK_V13,
            _handle_rules_v131(),
            _SRC_COPY_BLOCK_V131,
            build_language_directive(transcript.primary_language),
            (
                f"WINDOW — {window.window_id} — transcript {transcript.transcript_id} — "
                f"{window.owned_src_count} owned SRC, "
                f"{window.context_src_count} context-only SRC"
            ),
            "Notes locales compactes seulement. Pas de métadonnées globales finales.",
            _render_owned(materialized),
            _render_context(materialized),
        ]
    )


def window_prompt_v131_sha256(system_prompt: str) -> str:
    return content_hash(system_prompt)


def window_prompt_v131_fingerprint(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<LOCAL_V3_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<LOCAL_V3_USER>>>\n"
        + (user_prompt or "")
    )


def estimate_v131_request_tokens(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    content: WindowContent | None = None,
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    materialized = content or materialize_window_content(transcript, window)
    system = build_window_system_prompt_v131(transcript.primary_language)
    user = build_window_user_prompt_v131(transcript, window, materialized)
    total = estimate_tokens("\n".join([system, user]), model=model)
    return {
        "model": model,
        "method": total.method,
        "estimated": True,
        "total_tokens": total.tokens,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
        "transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
    }


_IDEA_EXAMPLE_TYPE_CONTRACT_V132 = """IDEA VERSUS EXAMPLE

For IDEA records, the semantic kind MUST be exactly one of:
claim, explanation, principle, instruction, observation, question, testimony.

Never use "example" as an IDEA kind. "example" is an EXAMPLE metadata kind only.

If a passage merely illustrates an idea, emit it as EXAMPLE and link it to
the relevant IDEA when appropriate. l[] on EXAMPLE remains optional.

If a concrete story also communicates a proposition, separate the proposition
as IDEA from the illustrative material as EXAMPLE. Do not emit both an IDEA
with kind=example and an EXAMPLE for the same illustration."""


def _handle_rules_v132() -> str:
    return _handle_rules_v131()


def _vocabulary_block_v132() -> str:
    return _vocabulary_block_v131()


def build_window_system_prompt_v132(primary_language: str) -> str:
    return "\n\n".join(
        [
            _ROLE_BLOCK,
            _SCOPE_BLOCK,
            _COMPACT_BLOCK,
            _OWNERSHIP_BLOCK,
            _FIDELITY_BLOCK,
            FORBIDDEN_STRUCTURE_BLOCK,
            _vocabulary_block_v132(),
            _handle_rules_v132(),
            _SRC_COPY_BLOCK_V131,
            _IDEA_EXAMPLE_TYPE_CONTRACT_V132,
            build_language_directive(primary_language),
        ]
    )


def build_window_user_prompt_v132(
    transcript: TranscriptInput,
    window: WindowInput,
    content: WindowContent | None = None,
) -> str:
    materialized = content or materialize_window_content(transcript, window)
    return "\n\n".join(
        [
            _TASK_BLOCK_V13,
            _handle_rules_v132(),
            _SRC_COPY_BLOCK_V131,
            _IDEA_EXAMPLE_TYPE_CONTRACT_V132,
            build_language_directive(transcript.primary_language),
            (
                f"WINDOW — {window.window_id} — transcript {transcript.transcript_id} — "
                f"{window.owned_src_count} owned SRC, "
                f"{window.context_src_count} context-only SRC"
            ),
            "Notes locales compactes seulement. Pas de métadonnées globales finales.",
            _render_owned(materialized),
            _render_context(materialized),
        ]
    )


def window_prompt_v132_sha256(system_prompt: str) -> str:
    return content_hash(system_prompt)


def window_prompt_v132_fingerprint(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<LOCAL_V3_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<LOCAL_V3_USER>>>\n"
        + (user_prompt or "")
    )


def estimate_v132_request_tokens(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    content: WindowContent | None = None,
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    materialized = content or materialize_window_content(transcript, window)
    system = build_window_system_prompt_v132(transcript.primary_language)
    user = build_window_user_prompt_v132(transcript, window, materialized)
    total = estimate_tokens("\n".join([system, user]), model=model)
    return {
        "model": model,
        "method": total.method,
        "estimated": True,
        "total_tokens": total.tokens,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V132,
        "transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
    }


def _vocabulary_block_v140() -> str:
    return "\n".join(
        [
            "IDENTIFIANTS CONTRÔLÉS — copie exacte",
            f"idea.importance : {', '.join(IMPORTANCE_LEVELS)}",
            f"relation.type : {', '.join(RELATION_KINDS)}",
            f"example.kind : {', '.join(EXAMPLE_KINDS)}",
            f"reference.kind : {', '.join(REFERENCE_KINDS)}",
            f"reference.completeness : {', '.join(REFERENCE_COMPLETENESS)}",
            f"uncertainty.kind : {', '.join(UNCERTAINTY_KINDS)}",
            f"uncertainty.severity : {', '.join(SEVERITY_LEVELS)}",
            f"confidence : {', '.join(CONFIDENCE_LEVELS)}",
            "TOPIC : v=label ; m=[summary] ; s=SRC ; h=T1… ; l=[]",
            "IDEA : v=summary ; m=[importance] ; h=I1… ; l=T labels ; s=SRC",
            "RELATION : v=type ; h=\"\" ; l=[from I, to I] ; s=[]",
            "EXAMPLE : v=summary ; m=[kind] ; h=\"\" ; l=I labels or [] ; s=SRC",
            "REFERENCE : v=raw ; m=[kind, completeness, normalized] ; s=SRC ; h=\"\" ; l=[]",
            "UNCERTAINTY : v=desc ; m=[kind, severity] ; s=SRC ; h=\"\" ; l=[]",
        ]
    )


_HANDLE_RULES_V140 = """HANDLE RULES

Assign local topic labels T1, T2, T3...
Assign local idea labels I1, I2, I3...
Use those exact labels when expressing relationships.
Do not calculate record indexes. Do not count positions. Do not use 0, 1, 2 as links.

h = owner label of THIS record.
TOPIC owns a T label. IDEA owns an I label.
RELATION, EXAMPLE, REFERENCE, UNCERTAINTY own no label : h="".

l = the same labels, used as targets.
Forward labels are legal. Resolution happens after the full records[] list.
Labels need not be gap-free. T1 and T3 are legal if T2 is unused.
Each owner label must be unique in its type. Unknown labels are invalid.

RELATION and EXAMPLE may NEVER target T handles.
IDEA may NEVER target I handles.

TOPIC : h=Tn ; l=[] required
IDEA : h=In ; l = zero or more T labels
RELATION : h="" ; l = exactly two distinct I labels [from, to] ; type in v
EXAMPLE : h="" ; l = I labels of the idea(s) this example supports ; l=[] allowed if no appropriate extracted IDEA exists. Grounding stays in s[].
REFERENCE : h="" ; l=[] required
UNCERTAINTY : h="" ; l=[] required

Correct compact example (2 TOPIC, 3 IDEA, 1 RELATION, 1 EXAMPLE):
{"k":"TOPIC","v":"Planning","s":["SRC999001"],"h":"T1","l":[],"m":["Careful plans."]}
{"k":"TOPIC","v":"Checking","s":["SRC999002"],"h":"T2","l":[],"m":["Verify twice."]}
{"k":"IDEA","v":"Planning reduces mistakes.","s":["SRC999001"],"h":"I1","l":["T1"],"m":["central"]}
{"k":"IDEA","v":"A second check catches gaps.","s":["SRC999002"],"h":"I2","l":["T2"],"m":["supporting"]}
{"k":"IDEA","v":"Checking serves planning.","s":["SRC999002"],"h":"I3","l":["T1","T2"],"m":["supporting"]}
{"k":"RELATION","v":"supports","s":[],"h":"","l":["I3","I1"],"m":[]}
{"k":"EXAMPLE","v":"Check the plan twice.","s":["SRC999002"],"h":"","l":["I2"],"m":["anecdote"]}

Recommended first-emitted order: first TOPIC=T1, second TOPIC=T2, first IDEA=I1.
Order is recommended, not required. Uniqueness and type matter more than gaps.

Recommended kind order: TOPIC, IDEA, RELATION, EXAMPLE, REFERENCE, UNCERTAINTY.
Kind order is not required."""


_TASK_BLOCK_V140 = f"""TÂCHE

Réponds en JSON ultra-compact ({SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE}) :

{{"theme":"...","intent":"...","ic":"...","aud":"...","ac":"...","records":[{{"k":"...","v":"...","s":[],"h":"","l":[],"m":[]}}]}}

Kinds locaux autorisés uniquement :
{', '.join(LOCAL_KINDS)}

Kinds interdits ici :
{', '.join(DEFERRED_KINDS)}

ic / ac = jetons confidence.
h = local owner label (T1… / I1…). Empty for RELATION, EXAMPLE, REFERENCE, UNCERTAINTY.
l[] = those exact labels as targets. Never numeric record indexes. Never self-link.

CIBLES / PLAFONDS :
{_budget_lines()}

source_refs : SRC réels, maximum {SOURCE_REFS_HARD_MAX} par record.
TOPIC.v ≤ {TEXT_HARD_LIMITS['TOPIC.v']} ; IDEA.v ≤ {TEXT_HARD_LIMITS['IDEA.v']}.

Si capacité insuffisante : UNCERTAINTY v={OVERFLOW_TOKEN}
m=["{OVERFLOW_UNCERTAINTY_KIND}","{OVERFLOW_UNCERTAINTY_SEVERITY}"]
s = au moins un SRC owned.

Sortie : uniquement le transport. Pas de raisonnement écrit."""


_IDEA_LOCAL_LITE_CONTRACT_V140 = """IDEA LOCAL EXTRACTION

For IDEA records, extract the proposition, teaching, or meaning expressed
by the source. Ground it in exact SRC identifiers. Associate it to TOPIC
labels. Preserve importance.

Do not classify the IDEA as claim, explanation, principle, instruction,
observation, question, testimony, or example.

Local IDEA metadata contains importance only: m=[importance].

IDEA VERSUS EXAMPLE

IDEA = a substantive proposition, teaching, or meaning.
EXAMPLE = a concrete story, illustration, analogy, case, event,
testimony detail, or other illustrative material.

If a passage contains both, extract the proposition as IDEA and the
illustration as EXAMPLE when useful.

Do not create an IDEA whose only content is a duplicate description of
an already extracted EXAMPLE.

Fine-grained IDEA subtype classification is not a local task."""


def build_window_system_prompt_v140(primary_language: str) -> str:
    return "\n\n".join(
        [
            _ROLE_BLOCK,
            _SCOPE_BLOCK,
            _COMPACT_BLOCK,
            _OWNERSHIP_BLOCK,
            _FIDELITY_BLOCK,
            FORBIDDEN_STRUCTURE_BLOCK,
            _vocabulary_block_v140(),
            _HANDLE_RULES_V140,
            _SRC_COPY_BLOCK_V131,
            _IDEA_LOCAL_LITE_CONTRACT_V140,
            build_language_directive(primary_language),
        ]
    )


def build_window_user_prompt_v140(
    transcript: TranscriptInput,
    window: WindowInput,
    content: WindowContent | None = None,
) -> str:
    materialized = content or materialize_window_content(transcript, window)
    return "\n\n".join(
        [
            _TASK_BLOCK_V140,
            _HANDLE_RULES_V140,
            _SRC_COPY_BLOCK_V131,
            _IDEA_LOCAL_LITE_CONTRACT_V140,
            build_language_directive(transcript.primary_language),
            (
                f"WINDOW — {window.window_id} — transcript {transcript.transcript_id} — "
                f"{window.owned_src_count} owned SRC, "
                f"{window.context_src_count} context-only SRC"
            ),
            "Notes locales compactes seulement. Pas de métadonnées globales finales.",
            _render_owned(materialized),
            _render_context(materialized),
        ]
    )


def window_prompt_v140_sha256(system_prompt: str) -> str:
    return content_hash(system_prompt)


def window_prompt_v140_fingerprint(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<LOCAL_V3_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<LOCAL_V3_USER>>>\n"
        + (user_prompt or "")
    )


def estimate_v140_request_tokens(
    transcript: TranscriptInput,
    window: WindowInput,
    *,
    content: WindowContent | None = None,
    model: str = ESTIMATION_MODEL,
) -> dict[str, Any]:
    materialized = content or materialize_window_content(transcript, window)
    system = build_window_system_prompt_v140(transcript.primary_language)
    user = build_window_user_prompt_v140(transcript, window, materialized)
    total = estimate_tokens("\n".join([system, user]), model=model)
    return {
        "model": model,
        "method": total.method,
        "estimated": True,
        "total_tokens": total.tokens,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        "transport_version": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    }


__all__ = [
    "WINDOW_PROMPT_ROLE",
    "build_window_system_prompt_v13",
    "build_window_system_prompt_v131",
    "build_window_system_prompt_v132",
    "build_window_system_prompt_v140",
    "build_window_user_prompt_v13",
    "build_window_user_prompt_v131",
    "build_window_user_prompt_v132",
    "build_window_user_prompt_v140",
    "estimate_v13_request_tokens",
    "estimate_v131_request_tokens",
    "estimate_v132_request_tokens",
    "estimate_v140_request_tokens",
    "window_prompt_v13_fingerprint",
    "window_prompt_v13_sha256",
    "window_prompt_v131_fingerprint",
    "window_prompt_v131_sha256",
    "window_prompt_v132_fingerprint",
    "window_prompt_v132_sha256",
    "window_prompt_v140_fingerprint",
    "window_prompt_v140_sha256",
]
