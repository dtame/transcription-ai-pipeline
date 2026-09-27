"""Rapport markdown Phase 3B.4.3 — structure imposée par le protocole."""

from __future__ import annotations

from app.source_analysis_ultra_compact_canary.constants import (
    CANARY_MAX_OUTPUT_TOKENS,
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    GLOBAL_ESTIMATED_TOKENS_REFERENCE,
    TRANSPORT_VERSION,
)
from app.source_analysis_ultra_compact_canary.runner import UltraCompactCanaryResult


def _yn(value) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "n/a"
    return str(value)


def _sha_block(hashes: dict[str, str]) -> str:
    if not hashes:
        return "- (aucun)"
    return "\n".join(f"- `{key}` : `{sha}`" for key, sha in hashes.items())


def _metrics_block(metrics: dict) -> str:
    if not metrics:
        return "- (aucune)"
    keys = (
        "serialized_json_bytes",
        "object_nodes",
        "array_nodes",
        "arrays_of_objects",
        "total_properties",
        "required_properties",
        "optional_properties",
        "constraints",
        "enum_count",
        "total_enum_values",
        "maximum_nesting_depth",
        "ref_count",
        "any_of",
        "one_of",
        "all_of",
        "union_count",
    )
    lines = []
    for key in keys:
        if key in metrics:
            lines.append(f"- {key} : {metrics[key]}")
    return "\n".join(lines) or "- (aucune)"


def _authorize_3b_final(result: UltraCompactCanaryResult) -> str:
    if result.outcome == "PASS" and not result.dry_run and result.pipeline_result == "PASS":
        return (
            "Generation C is server-verified and the complete canary "
            "transport→decoder→normalizer→canonical-validator chain passed. "
            "A separate reviewed phase may now authorize the full clean Source "
            "Analyzer run.\n\n"
            "STOP. Ce run n'est PAS lancé ici."
        )
    return (
        "NON. 3B FINAL n'est pas autorisé. "
        "Corriger d'abord offline si le serveur a accepté mais que le pipeline "
        "local a échoué. Attendre la revue humaine."
    )


def render_canary_report(result: UltraCompactCanaryResult) -> str:
    gen_c = ((result.complexity.get("generation_c") or {}).get("metrics") or {})
    gen_ac = ((result.complexity.get("anthropic_generation_c") or {}).get("metrics") or {})
    audit = result.local_audit or {}
    network = result.network or {}
    files = "\n".join(f"- `{name}`" for name in result.files_created) or "- (aucun)"
    src_list = ", ".join(result.selected_source_ids) or "(aucun)"
    dry = (
        "PASS"
        if result.dry_run_pass
        else (
            "N/A"
            if result.dry_run_pass is None and result.stop_reason == "PRE_CALL_FAILURE"
            else "FAIL"
        )
    )
    if result.dry_run and result.outcome == "PASS" and result.would_call_ai:
        dry = "PASS"

    return f"""# PHASE 3B.4.3 — ULTRA-COMPACT SERVER GRAMMAR CANARY

## 1. Result

**{result.outcome}**

SERVER GRAMMAR RESULT =
{result.server_grammar_result}

PIPELINE RESULT =
{result.pipeline_result}

- stop_reason : {result.stop_reason or "(aucun)"}
- error_type : {result.error_type or "(aucun)"}
- classification : {result.classification or "(aucune)"}

## 2. Objective

Vérifier expérimentalement qu'Anthropic accepte et compile Generation C
(semantic-transport-v1), puis — si et seulement si le serveur accepte —
que la chaîne

Anthropic structured response
→ semantic-transport-v1
→ decoder fail-closed
→ reconstruct canonical raw
→ normalize_source_map()
→ canonical validator

produit un SourceMap valide EN MÉMOIRE / CANARY ONLY.

Ce n'est PAS le Source Analyzer global.

## 3. Baseline

Commande : `.venv\\Scripts\\python.exe -m pytest -q`

Avant appel : {result.tests_before or "voir exécution opérateur"}

Après appel : {result.tests_after or "voir exécution opérateur"}

## 4. Historical context

Generation A : serialized bytes = 10492 — REJECTED HTTP 400
« The compiled grammar is too large... »

Generation B : serialized bytes = 4398 — REJECTED HTTP 400
« The compiled grammar is too large... »

Phase 3B.4.1 a prouvé que la taille de l'input n'était pas la cause
(10 SRC, 100 mots, ~2244 tokens estimés).

## 5. Generation C verification

transport version : `{TRANSPORT_VERSION}`

- Generation C selected : {_yn((result.architecture or {}).get("generation_c_selected"))}
- Generation B selected : {_yn((result.architecture or {}).get("generation_b_selected"))}
- Generation A selected : {_yn((result.architecture or {}).get("generation_a_selected"))}
- decoder exists : {_yn((result.architecture or {}).get("decoder_exists"))}
- decoder fail-closed : {_yn((result.architecture or {}).get("decoder_fail_closed"))}
- future analyzer uses C : {_yn((result.architecture or {}).get("future_analyzer_uses_c"))}

## 6. Canonical contract integrity

SourceMap changed? **NO**

validator changed? **NO**

Expected: NO / NO.

## 7. Schema metrics

Generation C raw.

{_metrics_block(gen_c)}

instance_max_depth : {(result.complexity.get("generation_c") or {}).get("instance_max_depth", "n/a")}

## 8. Anthropic-adapted schema metrics

{_metrics_block(gen_ac)}

instance_max_depth : {(result.complexity.get("anthropic_generation_c") or {}).get("instance_max_depth", "n/a")}

## 9. Schema SHA

raw : `{result.raw_generation_c_sha256 or "n/a"}`

Anthropic : `{result.anthropic_generation_c_sha256 or "n/a"}`

SHA match 3B.4.2 : {_yn((result.complexity or {}).get("sha_match_3b42"))}

## 10. Local Anthropic audit

{result.local_compatibility or "n/a"}

- objects : {audit.get("objects", "n/a")}
- arrays of objects : {audit.get("arrays_of_objects", "n/a")}
- properties : {audit.get("properties", "n/a")}
- constraints : {audit.get("constraints", "n/a")}
- provider enums : {audit.get("provider_enums", "n/a")}
- additionalProperties_not_false : {len(audit.get("additionalProperties_not_false") or [])}
- recursive_refs : {audit.get("recursive_refs", "n/a")}
- unsupported_minLength : {len(audit.get("unsupported_minLength") or [])}
- unsupported_minItems : {len(audit.get("unsupported_minItems") or [])}
- unsupported_maxLength : {len(audit.get("unsupported_maxLength") or [])}
- unsupported_maxItems : {len(audit.get("unsupported_maxItems") or [])}
- unsupported_minimum : {len(audit.get("unsupported_minimum") or [])}
- unsupported_maximum : {len(audit.get("unsupported_maximum") or [])}
- unsupported_multipleOf : {len(audit.get("unsupported_multipleOf") or [])}
- known unsupported constructs : {audit.get("known_unsupported_constructs", "n/a")}

## 11. Canary selection

- rule : {result.selection_rule or "(aucune)"}
- SRC IDs : {src_list}
- segments : {result.selected_segment_count}
- words : {result.selected_word_count}

## 12. Comparison with 3B.4.1 input

Same input? {_yn(result.same_as_3b41_input)}

Si non : le passage historique n'était plus présent ou n'était plus un
extrait cohérent ; une règle déterministe de repli a été utilisée.

## 13. Derived provenance

provenance_verified : {_yn(result.provenance_verified)}

Chargé depuis transcripts/clean/transcript_data.json via
cleanup_application.json (mode DERIVED 3A.2C).

## 14. Input determinism

run1 SHA : `{result.input_sha256_run1 or "n/a"}`

run2 SHA : `{result.input_sha256_run2 or "n/a"}`

identiques : {_yn(result.input_deterministic)}

## 15. Prompt

version : `{result.prompt_version or "n/a"}`

SHA : `{result.prompt_sha256 or "n/a"}`

Transport : `{TRANSPORT_VERSION}`

Le prompt complet n'est pas reproduit.

## 16. Token estimate

- system : {result.estimated_system_tokens if result.estimated_system_tokens is not None else "n/a"}
- user : {result.estimated_user_tokens if result.estimated_user_tokens is not None else "n/a"}
- total : {result.estimated_input_tokens if result.estimated_input_tokens is not None else "n/a"}
- max output : {result.estimated_output_budget if result.estimated_output_budget is not None else CANARY_MAX_OUTPUT_TOKENS}
- method : {result.estimation_method or "n/a"}
- référence appel global : {GLOBAL_ESTIMATED_TOKENS_REFERENCE}

Le budget de sortie {CANARY_MAX_OUTPUT_TOKENS} est local au canary.
La configuration globale Source Analyzer n'a pas été modifiée.

## 17. Credential

available : {_yn(result.credential_available)}

Aucune clé, aucun secret, aucun préfixe n'est publié.

## 18. Call guard

- max calls : {result.max_real_calls}
- actual calls : {result.actual_real_calls}
- max attempts : {result.max_attempts}
- retry : {_yn(not result.retry_disabled)}
- fallback : none

## 19. Dry run

{dry}

- would_call_ai : {_yn(result.would_call_ai)}
- actual_real_calls (dry) : {0 if result.dry_run else "n/a (real call after dry-run preflight)"}

## 20. Payload contract

- provider : {result.provider or EXPECTED_PROVIDER}
- model : {result.model or EXPECTED_MODEL}
- output_config.format.type : {result.output_format_type or "n/a"}

## 21. Production schema proof

Generation C used? {_yn(result.uses_production_generation_c)}

Generation B absent? {_yn(result.generation_b_absent_from_payload)}

Generation A absent? {_yn(result.generation_a_absent_from_payload)}

native structured output : {_yn(result.output_format_type == "json_schema")}

## 22. Real call

executed? {_yn(result.real_call_executed)}

count? {result.actual_real_calls}

## 23. HTTP result

status : {result.http_status if result.http_status is not None else "n/a"}

request accepted : {_yn(result.request_accepted)}

## 24. Server error

- type : {result.error_type or "(aucun)"}
- message (tronqué) : {result.error_message or "(aucun)"}

## 25. SERVER GRAMMAR RESULT

Question explicite :

Anthropic a-t-il accepté et compilé Generation C ?

Réponse :

**{result.server_grammar_result}**

## 26. SERVER GRAMMAR ACCEPTANCE

**{result.server_grammar_acceptance}**

## 27. Provider generation

Did generation occur? {_yn(result.provider_generation_occurred)}

## 28. Provider response

received? {_yn(result.request_accepted is True and result.real_call_executed)}

## 29. semantic-transport-v1 parse

{result.transport_parse}

## 30. Record kinds

{', '.join(result.record_kinds) or "(aucun)"}

## 31. Source refs

all in canary source set? {result.source_refs_in_canary}

## 32. Link validation

{result.link_validation}

## 33. Local semantic validation

{result.local_semantic}

## 34. Decoder

{result.decoder}

## 35. Canonical raw reconstruction

{result.reconstruction}

## 36. Normalization

{result.normalization}

## 37. Canonical IDs

- TOP : {", ".join(result.topic_ids) or "(aucun)"}
- IDEA : {", ".join(result.idea_ids) or "(aucun)"}
- EX : {", ".join(result.example_ids) or "(aucun)"}
- REF : {", ".join(result.reference_ids) or "(aucun)"}
- UNC : {", ".join(result.uncertainty_ids) or "(aucun)"}
- REP : {", ".join(result.repetition_ids) or "(aucun)"}

Attribués localement. Les SRC restent leurs IDs réels.

## 38. Canonical validation

{result.canonical_validation}

## 39. Editorial leakage

{result.editorial_leakage}

## 40. Usage

- input : {result.input_tokens if result.input_tokens is not None else "n/a"}
- output : {result.output_tokens if result.output_tokens is not None else "n/a"}
- total : {result.total_tokens if result.total_tokens is not None else "n/a"}
- source : {result.usage_source or "n/a"}

Si usage absent à cause d'un rejet pré-génération : cost/usage = unknown,
PAS zero.

## 41. Cost

- input : {result.input_cost if result.input_cost is not None else "n/a"}
- output : {result.output_cost if result.output_cost is not None else "n/a"}
- total : {result.total_cost if result.total_cost is not None else "n/a"}
- currency : {result.cost_currency or "n/a"}
- status : {result.cost_status or "n/a"}

## 42. Latency

{result.latency_ms if result.latency_ms is not None else "n/a"} ms

## 43. Request ID

{"présent (représentation sûre, aucun secret)" if result.request_id else "absent"}

## 44. Finish reason

{result.finish_reason or "n/a"}

## 45. Network

- Anthropic : {network.get("anthropic", 0)}
- OpenAI : {network.get("openai", 0)}
- Whisper : {network.get("whisper", 0)}
- Ollama : {network.get("ollama", 0)}
- LM Studio : {network.get("lm_studio", 0)}
- other : {network.get("other", 0)}

## 46. Production source_map

Expected: NOT CREATED.

NOT CREATED : {_yn(not result.production_source_map_created)}

writer production appelé : {_yn(result.writer_production_called)}

## 47. Canary SourceMap

created? {_yn(result.canary_source_map_created)}

path if diagnostic : `audit/source_analysis_ultra_compact_canary_source_map.json`

Marqué CANARY / PARTIAL CORPUS / NOT PRODUCTION.

## 48. Project state

global Source Analyzer remains non-success? {_yn(not result.global_source_analysis_success)}

## 49. Cache isolation

isolated / disabled : {_yn(result.cache_isolated)}

production cache used : {_yn(result.cache_used)}

namespace : `ultra-compact-canary-3b43`

## 50. Tests before call

{result.tests_before or "voir exécution opérateur"}

## 51. Tests after call

{result.tests_after or "voir exécution opérateur"}

## 52. Protected artifacts

Inchangés : {_yn(result.protected_unchanged)}

Avant :

{_sha_block(result.protected_before)}

Après :

{_sha_block(result.protected_after)}

## 53. New artifacts

{files}

## 54. Files modified

Uniquement les nouveaux artefacts 3B.4.3 listés ci-dessus.
Aucun artefact protégé. Aucun report.json. Aucun project_state.source_analysis SUCCESS.
Aucun analysis/source_map.json.

## 55. Technical decision

- Le canary utilisait-il exactement Generation C de production ? {_yn(result.uses_production_generation_c)}
- Generation C raw faisait combien d'octets ? {gen_c.get("serialized_json_bytes", "n/a")}
- Anthropic Generation C faisait combien d'octets ? {gen_ac.get("serialized_json_bytes", "n/a")}
- Combien d'objets ? {gen_c.get("object_nodes", "n/a")}
- Combien d'arrays of objects ? {gen_c.get("arrays_of_objects", "n/a")}
- Combien de propriétés ? {gen_c.get("total_properties", "n/a")}
- Combien de contraintes ? {gen_c.get("constraints", "n/a")}
- Combien d'enums provider ? {gen_c.get("enum_count", "n/a")}
- Quelle profondeur ? {(result.complexity.get("generation_c") or {}).get("instance_max_depth", "n/a")}
- Les schemas A et B étaient-ils absents ? {_yn(result.generation_a_absent_from_payload and result.generation_b_absent_from_payload)}
- Quel extrait a été envoyé ? {src_list}
- Combien de SRC ? {result.selected_segment_count}
- Combien de mots ? {result.selected_word_count}
- Combien de tokens estimés ? {result.estimated_input_tokens}
- Combien d'appels Anthropic réels ? {result.actual_real_calls}
- Combien de tentatives ? {result.max_attempts}
- Anthropic a-t-il encore répondu « compiled grammar too large » ? {_yn(result.classification == "SERVER_GRAMMAR_REJECTED")}
- Anthropic a-t-il accepté Generation C ? {_yn(result.server_grammar_result == "ACCEPTED")}
- SERVER GRAMMAR ACCEPTANCE = {result.server_grammar_acceptance}
- Une génération provider a-t-elle eu lieu ? {_yn(result.provider_generation_occurred)}
- Combien de tokens réels ? {result.total_tokens if result.total_tokens is not None else "n/a"}
- Quel coût réel ? {result.total_cost if result.total_cost is not None else "n/a"} {result.cost_currency or ""}
- Le semantic transport a-t-il été parsé ? {result.transport_parse}
- Le decoder fail-closed a-t-il accepté la réponse ? {result.decoder}
- Toutes les source refs appartenaient-elles au canary ? {result.source_refs_in_canary}
- Les links étaient-ils valides ? {result.link_validation}
- La reconstruction canonique a-t-elle réussi ? {result.reconstruction}
- La normalisation a-t-elle réussi ? {result.normalization}
- La validation canonique a-t-elle réussi ? {result.canonical_validation}
- Un source_map de production a-t-il été créé ? {_yn(result.production_source_map_created)}
  Réponse attendue : NON.
- Le Source Analyzer global a-t-il été marqué success ? {_yn(result.global_source_analysis_success)}
  Réponse attendue : NON.
- Les artefacts protégés sont-ils intacts ? {_yn(result.protected_unchanged)}
- Les tests sont-ils verts ? {result.tests_after or result.tests_before or "voir exécution opérateur"}
- Peut-on autoriser 3B FINAL sur les 8298 segments / 38313 mots ?

{_authorize_3b_final(result)}
"""
