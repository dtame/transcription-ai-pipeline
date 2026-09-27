"""Rapport markdown Phase 3B.4.5 — structure imposée par le protocole."""

from __future__ import annotations

from app.source_analysis_vocabulary_compliance_canary.constants import (
    CANARY_MAX_OUTPUT_TOKENS,
    CACHE_NAMESPACE,
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    HISTORICAL_SRC_IDS,
    OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS,
    TRANSPORT_VERSION,
)
from app.source_analysis_vocabulary_compliance_canary.runner import (
    VocabularyComplianceCanaryResult,
)


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


def _token_table(rows: list[dict]) -> str:
    if not rows:
        return "(aucun jeton contrôlé observé)"
    lines = ["| vocabulary | token | canonical? |", "|---|---|---|"]
    for item in rows:
        lines.append(
            f"| `{item.get('vocabulary')}` | `{item.get('value')}` | "
            f"{_yn(item.get('canonical'))} |"
        )
    return "\n".join(lines)


def _invalid_block(rows: list[dict]) -> str:
    if not rows:
        return "`[]`"
    lines = []
    for item in rows:
        allowed = ", ".join(f"`{value}`" for value in (item.get("allowed_values") or []))
        lines.append(
            f"- vocabulary : `{item.get('vocabulary')}` ; "
            f"actual : `{item.get('actual_token')}` ; "
            f"allowed : {allowed or '(vide)'}"
        )
    return "\n".join(lines)


def _authorize_3b_final(result: VocabularyComplianceCanaryResult) -> str:
    if (
        result.outcome == "PASS"
        and not result.dry_run
        and result.vocabulary_prompt_compliance == "VERIFIED"
        and result.pipeline_result == "PASS"
        and result.canonical_validation == "PASS"
    ):
        return (
            "OUI, sous revue humaine. Generation C server acceptance was "
            "previously verified in 3B.4.3. Prompt 1.3 canonical vocabulary "
            "compliance is now verified on a real Anthropic response. The "
            "complete canary chain semantic-transport-v1 → decoder → "
            "normalizer → canonical validator passed. No known canary "
            "blocker remains before the reviewed 3B FINAL clean Source "
            "Analyzer run.\n\n"
            "STOP. Ce run n'est PAS lancé ici."
        )
    return (
        "NON. 3B FINAL n'est pas autorisé. "
        "Attendre la revue humaine. Aucun second appel Anthropic."
    )


def render_canary_report(result: VocabularyComplianceCanaryResult) -> str:
    gen_c = ((result.complexity.get("generation_c") or {}).get("metrics") or {})
    gen_ac = ((result.complexity.get("anthropic_generation_c") or {}).get("metrics") or {})
    decoder = result.decoder_integrity or {}
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

    schema_acceptance = "PREVIOUSLY VERIFIED"
    if result.classification == "SERVER_GRAMMAR_REGRESSION":
        schema_acceptance = "REGRESSED"
    elif result.server_grammar_acceptance == "VERIFIED" and result.real_call_executed:
        schema_acceptance = "PREVIOUSLY VERIFIED (reconfirmed ACCEPTED this run)"

    ids = (
        f"- TOP : {', '.join(result.topic_ids) or '(aucun)'}\n"
        f"- IDEA : {', '.join(result.idea_ids) or '(aucun)'}\n"
        f"- EX : {', '.join(result.example_ids) or '(aucun)'}\n"
        f"- REF : {', '.join(result.reference_ids) or '(aucun)'}\n"
        f"- UNC : {', '.join(result.uncertainty_ids) or '(aucun)'}\n"
        f"- REP : {', '.join(result.repetition_ids) or '(aucun)'}"
    )
    complexity = result.complexity or {}
    prompt_preflight = result.prompt_preflight or {}
    sha_match = _yn(complexity.get("sha_match_3b42"))
    contract_included = _yn(prompt_preflight.get("vocabulary_contract_included"))
    has_aliases = _yn(decoder.get("aliases") or decoder.get("synonym_map"))
    used_prompt_13 = _yn(result.prompt_version == "1.3")

    return f"""# PHASE 3B.4.5 — CANONICAL VOCABULARY COMPLIANCE CANARY

## 1. Result

**{result.outcome}**

SCHEMA SERVER ACCEPTANCE =
{schema_acceptance}

VOCABULARY PROMPT COMPLIANCE =
{result.vocabulary_prompt_compliance}

PIPELINE RESULT =
{result.pipeline_result}

- stop_reason : {result.stop_reason or "(aucun)"}
- error_type : {result.error_type or "(aucun)"}
- classification : {result.classification or "(aucune)"}

## 2. Objective

Vérifier SERVER-SIDE / MODEL-SIDE que Claude, avec le Prompt 1.3,
produit un semantic-transport-v1 dont tous les identifiants contrôlés
sont des jetons de protocole canoniques, permettant à la chaîne

Claude / Prompt 1.3
→ Generation C
→ semantic-transport-v1 parse
→ controlled vocabulary validation
→ decoder fail-closed
→ canonical raw reconstruction
→ normalize_source_map()
→ canonical validator

de produire un SourceMap CANARY valide.

Ce n'est PAS 3B FINAL.

## 3. Baseline

Commande : `.venv\\Scripts\\python.exe -m pytest -q`

Avant appel : {result.tests_before or "voir exécution opérateur"}

Après appel : {result.tests_after or "voir exécution opérateur"}

## 4. Historical context

3B.4.3 : Generation C server-accepted (HTTP 200, json_schema, end_turn).
Le transport était parseable, SRC et links valides, mais Claude avait
inventé `transcription_artifact`, `ambiguous_reference`,
`incomplete_thought`. Decoder fail-closed : refus correct, aucune réparation.

3B.4.4 : durcissement OFFLINE du contrat lexical (Prompt 1.2 → 1.3).
12 vocabulaires fermés, parité 100 %, 0 alias, decoder inchangé.
VOCABULARY PROMPT COMPLIANCE restait UNVERIFIED.

## 5. Generation C integrity

- raw SHA : `{result.raw_generation_c_sha256 or "n/a"}`
- Anthropic SHA : `{result.anthropic_generation_c_sha256 or "n/a"}`
- raw bytes : {gen_c.get("serialized_json_bytes", "n/a")}
- Anthropic bytes : {gen_ac.get("serialized_json_bytes", "n/a")}
- objects : {gen_c.get("object_nodes", "n/a")}
- arrays of objects : {gen_c.get("arrays_of_objects", "n/a")}
- properties : {gen_c.get("total_properties", "n/a")}
- constraints : {gen_c.get("constraints", "n/a")}
- provider enums : {gen_c.get("enum_count", "n/a")}
- instance depth : {(result.complexity.get("generation_c") or {}).get("instance_max_depth", "n/a")}
- SHA match 3B.4.3 / 3B.4.2 : {_yn((result.complexity or {}).get("sha_match_3b42"))}

## 6. Prompt integrity

- version : `{result.prompt_version or "n/a"}`
- SHA canary (system+user extrait) : `{result.prompt_sha256 or "n/a"}`
- SHA production (system+user corpus chargé) : `{result.production_prompt_sha256 or "n/a"}`

## 7. Vocabulary contract

- SHA : `{result.vocabulary_contract_sha256 or "n/a"}`
- 12 vocabulaires fermés : record.kind, idea.kind, idea.importance,
  relation.type, example.kind, reference.kind, reference.completeness,
  uncertainty.kind, uncertainty.severity, repetition.character,
  voice.field, confidence
- missing_from_prompt : {result.missing_from_prompt or []}
- extra_in_prompt : {result.extra_in_prompt or []}
- parity : {result.vocabulary_parity}

## 8. Decoder integrity

- fail-closed : {_yn(decoder.get("fail_closed"))}
- aliases : {_yn(decoder.get("aliases"))}
- synonym map : {_yn(decoder.get("synonym_map"))}
- fuzzy repair : {_yn(decoder.get("fuzzy_repair"))}

## 9. Canary input

- SRC IDs : {src_list}
- segments : {result.selected_segment_count}
- words : {result.selected_word_count}

Attendu historique : {", ".join(HISTORICAL_SRC_IDS)}

## 10. Historical input comparison

Same as 3B.4.3? {_yn(result.same_as_3b43_input)}

Expected YES on the real corpus.

## 11. Derived provenance

provenance_verified : {_yn(result.provenance_verified)}

Chargé depuis transcripts/clean/transcript_data.json via
cleanup_application.json (mode DERIVED 3A.2C).

## 12. Input determinism

run1 SHA : `{result.input_sha256_run1 or "n/a"}`

run2 SHA : `{result.input_sha256_run2 or "n/a"}`

identiques : {_yn(result.input_deterministic)}

## 13. Dry run

{dry}

- would_call_ai : {_yn(result.would_call_ai)}
- actual_real_calls (dry) : {0 if result.dry_run else "n/a (real call after dry-run preflight)"}
- provider : {EXPECTED_PROVIDER}
- model : {EXPECTED_MODEL}
- prompt version : {result.prompt_version or "n/a"}
- semantic transport : `{TRANSPORT_VERSION}`
- Generation C : {_yn(result.uses_production_generation_c)}
- provider enums : {gen_c.get("enum_count", "n/a")}
- vocabulary parity : {result.vocabulary_parity}
- native structured output : {_yn(result.output_format_type == "json_schema")}

## 14. Payload

- provider : {result.provider or EXPECTED_PROVIDER}
- model : {result.model or EXPECTED_MODEL}
- output_config.format.type : {result.output_format_type or "n/a"}
- Generation C used : {_yn(result.uses_production_generation_c)}
- Generation A absent : {_yn(result.generation_a_absent_from_payload)}
- Generation B absent : {_yn(result.generation_b_absent_from_payload)}

## 15. Token estimate

- system : {result.estimated_system_tokens if result.estimated_system_tokens is not None else "n/a"}
- user : {result.estimated_user_tokens if result.estimated_user_tokens is not None else "n/a"}
- total : {result.estimated_input_tokens if result.estimated_input_tokens is not None else "n/a"}
- max output : {result.estimated_output_budget if result.estimated_output_budget is not None else CANARY_MAX_OUTPUT_TOKENS}

Le budget de sortie {CANARY_MAX_OUTPUT_TOKENS} est local au canary.
La configuration globale Source Analyzer n'a pas été modifiée.
Prompt 1.3 est plus grand que 1.2 ; l'estimation 2136 de 3B.4.3 n'est
pas réutilisée.

## 16. Call guard

- max calls : {result.max_real_calls}
- actual calls : {result.actual_real_calls}
- max attempts : {result.max_attempts}
- retry : {_yn(not result.retry_disabled)}
- fallback : none

## 17. HTTP result

status : {result.http_status if result.http_status is not None else "n/a"}

request accepted : {_yn(result.request_accepted)}

## 18. Provider generation

Did generation occur? {_yn(result.provider_generation_occurred)}

## 19. Finish reason

{result.finish_reason or "n/a"}

## 20. Semantic transport parse

{result.transport_parse}

## 21. Controlled tokens observed

{_token_table(result.controlled_tokens_observed)}

## 22. Invalid controlled tokens

{_invalid_block(result.invalid_tokens)}

Jetons 3B.4.3 réutilisés : {result.reused_3b43_invalid_tokens or []}

Référence historique : {list(OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS)}

## 23. VOCABULARY PROMPT COMPLIANCE

**{result.vocabulary_prompt_compliance}**

VERIFIED only if the actual real response uses controlled identifiers
correctly and the pipeline can validate them.

## 24. Source refs

all in CANARY_SOURCE_SET? {result.source_refs_in_canary}

## 25. Links

{result.link_validation}

## 26. Decoder

{result.decoder}

## 27. Canonical reconstruction

{result.reconstruction}

## 28. Normalization

{result.normalization}

## 29. Canonical IDs

{ids}

Attribués localement. Les SRC restent leurs IDs réels.

## 30. Canonical validation

{result.canonical_validation}

Validateur de production, corpus = extrait canary uniquement.

## 31. Editorial leakage

{result.editorial_leakage}

## 32. Usage

- input : {result.input_tokens if result.input_tokens is not None else "n/a"}
- output : {result.output_tokens if result.output_tokens is not None else "n/a"}
- total : {result.total_tokens if result.total_tokens is not None else "n/a"}
- source : {result.usage_source or "n/a"}

Si usage absent : cost/usage = unknown/unavailable, PAS zéro.

## 33. Cost

- input : {result.input_cost if result.input_cost is not None else "n/a"}
- output : {result.output_cost if result.output_cost is not None else "n/a"}
- total : {result.total_cost if result.total_cost is not None else "n/a"}
- currency : {result.cost_currency or "n/a"}
- status : {result.cost_status or "n/a"}

## 34. Latency

{result.latency_ms if result.latency_ms is not None else "n/a"} ms

## 35. Request ID

{"présent (représentation sûre, aucun secret)" if result.request_id else "absent"}

## 36. Network

- Anthropic : {network.get("anthropic", 0)}
- OpenAI : {network.get("openai", 0)}
- Whisper : {network.get("whisper", 0)}
- Ollama : {network.get("ollama", 0)}
- LM Studio : {network.get("lm_studio", 0)}
- other : {network.get("other", 0)}

## 37. Production source_map

Expected: NOT CREATED.

NOT CREATED : {_yn(not result.production_source_map_created)}

writer production appelé : {_yn(result.writer_production_called)}

## 38. Canary SourceMap

created? {_yn(result.canary_source_map_created)}

path if created : `audit/source_analysis_vocabulary_compliance_canary_source_map.json`

Marqué CANARY / PARTIAL CORPUS / NOT PRODUCTION.

## 39. Project state

global Source Analyzer remains non-success? {_yn(not result.global_source_analysis_success)}

## 40. Cache isolation

isolated / disabled : {_yn(result.cache_isolated)}

production cache used : {_yn(result.cache_used)}

namespace : `{CACHE_NAMESPACE}`

## 41. Tests before

{result.tests_before or "voir exécution opérateur"}

## 42. Tests after

{result.tests_after or "voir exécution opérateur"}

## 43. Protected artifacts

Inchangés : {_yn(result.protected_unchanged)}

Avant :

{_sha_block(result.protected_before)}

Après :

{_sha_block(result.protected_after)}

## 44. New artifacts

{files}

## 45. Files modified

Uniquement le package canary 3B.4.5, ses tests, et les nouveaux artefacts
listés ci-dessus. Aucun artefact protégé. Aucun report.json.
Aucun project_state.source_analysis SUCCESS. Aucun analysis/source_map.json.

## 46. Technical decision

- Generation C était-elle identique à la version server-verified ?
  {sha_match}
- Le Prompt 1.3 a-t-il été utilisé ? {used_prompt_13}
- Le vocabulary contract était-il réellement inclus ?
  {contract_included}
- missing_from_prompt = {result.missing_from_prompt or []}
- extra_in_prompt = {result.extra_in_prompt or []}
- Le decoder est-il toujours fail-closed ? {_yn(decoder.get("fail_closed"))}
- Des aliases ou synonym mappings existent-ils ?
  {has_aliases}
- L'extrait était-il exactement le même que 3B.4.3 ? {_yn(result.same_as_3b43_input)}
- Quels SRC ? {src_list}
- Combien de mots ? {result.selected_word_count}
- Combien de tokens estimés ? {result.estimated_input_tokens}
- Combien d'appels Anthropic ? {result.actual_real_calls}
- Combien de tentatives ? {result.max_attempts}
- HTTP status ? {result.http_status if result.http_status is not None else "n/a"}
- Generation occurred ? {_yn(result.provider_generation_occurred)}
- Finish reason ? {result.finish_reason or "n/a"}
- Quels controlled tokens Claude a-t-il réellement émis ?
  voir §21
- A-t-il réutilisé l'un des trois tokens invalides de 3B.4.3 ?
  {result.reused_3b43_invalid_tokens or []}
- A-t-il inventé un autre token ? {_yn(bool(result.invalid_tokens))}
- invalid_tokens = {result.invalid_tokens or []}
- VOCABULARY PROMPT COMPLIANCE = {result.vocabulary_prompt_compliance}
- Les SRC étaient-ils valides ? {result.source_refs_in_canary}
- Les links étaient-ils valides ? {result.link_validation}
- Le decoder a-t-il passé ? {result.decoder}
- La reconstruction canonique ? {result.reconstruction}
- La normalisation ? {result.normalization}
- Le canonical validator ? {result.canonical_validation}
- Le contrôle editorial leakage ? {result.editorial_leakage}
- Combien de tokens provider réels ? {result.total_tokens if result.total_tokens is not None else "n/a"}
- Quel coût ? {result.total_cost if result.total_cost is not None else "n/a"} {result.cost_currency or ""}
- Un source_map de production a-t-il été créé ?
  {_yn(result.production_source_map_created)}
  Réponse attendue : NON.
- Le Source Analyzer global a-t-il été marqué SUCCESS ?
  {_yn(result.global_source_analysis_success)}
  Réponse attendue : NON.
- Les artefacts protégés sont-ils intacts ? {_yn(result.protected_unchanged)}
- Les tests sont-ils verts ? {result.tests_after or result.tests_before or "voir exécution opérateur"}
- 3B FINAL peut-il maintenant être autorisé ?

{_authorize_3b_final(result)}
"""
