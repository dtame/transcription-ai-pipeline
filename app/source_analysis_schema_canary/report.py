"""Rapport markdown Phase 3B.4.1 — structure imposée par le protocole."""

from __future__ import annotations

from app.source_analysis_schema_canary.constants import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    GLOBAL_ESTIMATED_TOKENS_REFERENCE,
)
from app.source_analysis_schema_canary.runner import SchemaCanaryResult


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


def render_canary_report(result: SchemaCanaryResult) -> str:
    compact = (result.complexity.get("compact") or {}) if result.complexity else {}
    old = (result.complexity.get("old") or {}) if result.complexity else {}
    reduction = (result.complexity.get("reduction") or {}) if result.complexity else {}
    compact_metrics = compact.get("metrics") or {}
    old_metrics = old.get("metrics") or {}
    audit = result.local_audit or {}
    network = result.network or {}

    files = "\n".join(f"- `{name}`" for name in result.files_created) or "- (aucun)"
    src_list = ", ".join(result.selected_source_ids) or "(aucun)"
    bytes_red = reduction.get("serialized_json_bytes", "n/a")

    return f"""# PHASE 3B.4.1 — ANTHROPIC SERVER GRAMMAR CANARY

## 1. Résultat

**{result.outcome}**

- SERVER GRAMMAR RESULT : {result.server_grammar_result}
- PIPELINE RESULT : {result.pipeline_result}
- stop_reason : {result.stop_reason or "(aucun)"}
- error_type : {result.error_type or "(aucun)"}
- classification : {result.classification or "(aucune)"}

## 2. Objectif

Vérifier, avec un seul petit appel réel, qu'Anthropic peut compiler et
utiliser le JSON Schema compact de production (Phase 3B.4). L'input est
réduit ; le schéma de réponse ne l'est pas.

## 3. Baseline

Commande : `.venv\\Scripts\\python.exe -m pytest -q`

Avant appel : {result.tests_before or "voir exécution opérateur"}

Après appel : {result.tests_after or "voir exécution opérateur"}

## 4. Protected artifacts

Avant :

{_sha_block(result.protected_before)}

Après :

{_sha_block(result.protected_after)}

Inchangés : {_yn(result.protected_unchanged)}

## 5. 3B.4 architecture verification

- canonical SourceMap inchangé : {_yn((result.architecture or {}).get("canonical_schema_unchanged"))}
- DTO compact distinct : {_yn((result.architecture or {}).get("compact_distinct_from_old"))}
- reconstruct_to_canonical_raw : {_yn((result.architecture or {}).get("reconstruct_to_canonical_raw"))}
- normalizer canonique : {_yn((result.architecture or {}).get("normalizer_canonical_unchanged"))}
- validator canonique : {_yn((result.architecture or {}).get("validator_canonical_unchanged"))}
- future analyzer utilise le compact : {_yn((result.architecture or {}).get("future_analyzer_uses_compact"))}

## 6. Compact schema

- SHA : `{result.compact_schema_sha256 or "n/a"}`
- serialized bytes : {compact_metrics.get("serialized_json_bytes", "n/a")}
- optional_properties : {compact_metrics.get("optional_properties", "n/a")}
- constraints : {compact_metrics.get("constraints", "n/a")}
- id_pattern_like_structures : {compact_metrics.get("id_pattern_like_structures", "n/a")}
- réduction old→compact (serialized bytes) : {bytes_red}

## 7. Anthropic adapted schema

- SHA : `{result.anthropic_schema_sha256 or "n/a"}`
- compatibility : {result.local_compatibility or "n/a"}
- additionalProperties_not_false : {len(audit.get("additionalProperties_not_false") or [])}
- minLength : {len(audit.get("minLength") or [])}
- unsupported_minItems : {len(audit.get("unsupported_minItems") or [])}
- recursive_refs : {audit.get("recursive_refs", "n/a")}
- known_incompatibilities : {audit.get("known_incompatibilities", "n/a")}

## 8. Canary selection

- rule : {result.selection_rule}
- SRC IDs : {src_list}
- segment count : {result.selected_segment_count}
- word count : {result.selected_word_count}
- estimated input tokens : {result.estimated_input_tokens}
- estimated output budget : {result.estimated_output_budget}
- référence appel global : {GLOBAL_ESTIMATED_TOKENS_REFERENCE}

## 9. Canary input integrity

- text unchanged : {_yn(result.text_unchanged)}
- real SRC preserved : {_yn(result.real_src_ids_preserved)}

## 10. Prompt

- version : {result.prompt_version or "n/a"}
- SHA : `{result.prompt_sha256 or "n/a"}`

Le prompt complet n'est pas reproduit.

## 11. Dry run

{"PASS" if result.dry_run and result.would_call_ai and result.actual_real_calls == 0 and result.outcome == "PASS" else ("N/A (real call)" if not result.dry_run else "FAIL")}

- would_call_ai : {_yn(result.would_call_ai)}
- actual_real_calls : {result.actual_real_calls}

## 12. Credential

- available : {_yn(result.credential_available)}

Aucune clé, aucun secret, aucun préfixe n'est publié.

## 13. Call guard

- max real calls : {result.max_real_calls}
- actual calls : {result.actual_real_calls}
- max attempts : {result.max_attempts}
- retry disabled : {_yn(result.retry_disabled)}
- fallback disabled : {_yn(result.fallback_disabled)}

## 14. Real Anthropic call

- executed : {_yn(result.real_call_executed)}
- provider : {result.provider or EXPECTED_PROVIDER}
- model : {result.model or EXPECTED_MODEL}

## 15. HTTP/server result

- request accepted : {_yn(result.request_accepted)}
- HTTP status : {result.http_status if result.http_status is not None else "n/a"}
- error type : {result.error_type or "(aucun)"}
- error message (tronqué) : {result.error_message or "(aucun)"}

## 16. COMPILED GRAMMAR

Anthropic a-t-il accepté et compilé le nouveau compact schema ?

**{result.server_grammar_result}**

C'est la question centrale de cette phase.

## 17. Native structured output

- output_config.format.type : {result.output_format_type or "n/a"}
- production compact schema utilisé : {_yn(result.uses_production_compact)}
- ancien gros schema absent du payload : {_yn(result.old_schema_absent_from_payload)}

## 18. Provider response

- received : {_yn(result.request_accepted is True and result.real_call_executed)}

## 19. Compact parse

{result.compact_parse}

## 20. Compact semantic validation

{result.compact_semantic}

## 21. Source refs

- all within selected canary set : {result.source_refs_in_canary}

## 22. Index validation

{result.index_validation}

## 23. Reconstruction

{result.reconstruction}

## 24. Normalization

{result.normalization}

## 25. Canonical validation

{result.canonical_validation}

## 26. Canonical IDs

- TOP : {", ".join(result.topic_ids) or "(aucun)"}
- IDEA : {", ".join(result.idea_ids) or "(aucun)"}
- EX : {", ".join(result.example_ids) or "(aucun)"}
- REF : {", ".join(result.reference_ids) or "(aucun)"}
- UNC : {", ".join(result.uncertainty_ids) or "(aucun)"}
- REP : {", ".join(result.repetition_ids) or "(aucun)"}

Reconstruits localement (jamais fournis par le provider).

## 27. Usage

- input : {result.input_tokens if result.input_tokens is not None else "n/a"}
- output : {result.output_tokens if result.output_tokens is not None else "n/a"}
- total : {result.total_tokens if result.total_tokens is not None else "n/a"}
- source : {result.usage_source or "n/a"}

## 28. Cost

- input : {result.input_cost if result.input_cost is not None else "n/a"}
- output : {result.output_cost if result.output_cost is not None else "n/a"}
- total : {result.total_cost if result.total_cost is not None else "n/a"}
- currency : {result.cost_currency or "n/a"}
- status : {result.cost_status or "n/a"}

## 29. Latency

{result.latency_ms if result.latency_ms is not None else "n/a"} ms

## 30. Request ID

{"présent" if result.request_id else "absent"}

## 31. Finish reason

{result.finish_reason or "n/a"}

## 32. Network

- Anthropic : {network.get("anthropic", 0)}
- OpenAI : {network.get("openai", 0)}
- Whisper : {network.get("whisper", 0)}
- Ollama : {network.get("ollama", 0)}
- LM Studio : {network.get("lm_studio", 0)}
- other : {network.get("other", 0)}

## 33. Production source_map

NOT CREATED : {_yn(not result.production_source_map_created)}

## 34. Project state

Global Source Analyzer marked SUCCESS : {_yn(result.global_source_analysis_success)}

## 35. report.json

Global source_analysis SUCCESS : {_yn(result.report_json_global_success)}

Le canary n'écrit pas report.json.

## 36. Tests before call

{result.tests_before or "voir exécution opérateur"}

## 37. Tests after call

{result.tests_after or "voir exécution opérateur"}

## 38. Protected integrity

{_yn(result.protected_unchanged)}

## 39. Files created/modified

{files}

## 40. Technical decision

- Le canary utilisait-il EXACTEMENT le compact schema de production ? {_yn(result.uses_production_compact)}
- L'ancien gros schema était-il absent du payload ? {_yn(result.old_schema_absent_from_payload)}
- Combien de SRC ? {result.selected_segment_count}
- Combien de mots ? {result.selected_word_count}
- Combien de tokens estimés ? {result.estimated_input_tokens}
- Combien d'appels réels Anthropic ? {result.actual_real_calls}
- Combien de tentatives ? {result.max_attempts}
- Anthropic a-t-il rejeté la grammaire ? {_yn(result.server_grammar_result == "REJECTED")}
- Anthropic a-t-il accepté la requête ? {_yn(result.request_accepted)}
- SERVER GRAMMAR ACCEPTANCE est-elle VERIFIED ? {_yn(result.server_grammar_result == "VERIFIED")}
- Une réponse structurée a-t-elle été obtenue ? {_yn(result.compact_parse == "PASS")}
- Compact parse a-t-il réussi ? {result.compact_parse}
- La reconstruction canonique a-t-elle réussi ? {result.reconstruction}
- La normalisation a-t-elle réussi ? {result.normalization}
- La validation canonique a-t-elle réussi ? {result.canonical_validation}
- Les source_refs sont-ils tous dans le canary ? {result.source_refs_in_canary}
- Combien de tokens réels ont été consommés ? {result.total_tokens if result.total_tokens is not None else "n/a"}
- Quel coût réel ? {result.total_cost if result.total_cost is not None else "n/a"} {result.cost_currency or ""}
- Quelle latence ? {result.latency_ms if result.latency_ms is not None else "n/a"} ms
- Un source_map de production a-t-il été créé ? {_yn(result.production_source_map_created)}
- Les artefacts protégés sont-ils intacts ? {_yn(result.protected_unchanged)}
- Les tests sont-ils verts ? {result.tests_after or "voir exécution opérateur"}
- Peut-on maintenant autoriser une tentative Source Analyzer globale sur le transcript clean ?

**NON — STOP. Attendre la revue humaine.** Même un canary PASS n'autorise
pas d'enchaîner automatiquement sur les 8298 segments.

Ancien schéma SHA : `{result.old_schema_sha256 or "n/a"}`
Ancien serialized bytes : {old_metrics.get("serialized_json_bytes", "n/a")}
Compact serialized bytes : {compact_metrics.get("serialized_json_bytes", "n/a")}
"""
