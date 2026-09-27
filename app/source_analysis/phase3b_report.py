"""Rendu markdown du rapport Phase 3B — Source Analyzer réel sur transcript clean."""

from __future__ import annotations

from app.source_analysis.real_run import Phase3BResult


def _yn(value) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "n/a"
    return str(value)


def _passfail(value: str | None) -> str:
    return value or "n/a"


def render_phase3b_report(result: Phase3BResult) -> str:
    provenance = result.provenance or {}
    tokens = result.estimated_tokens or {}
    audit = result.schema_audit or {}
    network = result.network or {}

    hashes_before = "\n".join(
        f"- `{key}` : `{sha}`" for key, sha in result.protected_before.items()
    ) or "- (aucun)"
    hashes_after = "\n".join(
        f"- `{key}` : `{sha}`" for key, sha in result.protected_after.items()
    ) or "- (aucun)"

    files = "\n".join(f"- `{name}`" for name in result.files_created_or_modified) or "- (aucun)"
    editorial = ", ".join(result.editorial_leakage) if result.editorial_leakage else "(aucun)"
    intent_kinds = ", ".join(result.author_intent_kinds) if result.author_intent_kinds else "(aucun)"
    audience_kinds = (
        ", ".join(result.target_audience_kinds) if result.target_audience_kinds else "(aucun)"
    )
    violations = (
        ", ".join(result.protected_violations) if result.protected_violations else "(aucune)"
    )

    min_length = len(audit.get("minLength") or [])
    unsupported_min_items = len(audit.get("unsupported_minItems") or [])
    additional_not_false = len(audit.get("additionalProperties_not_false") or [])
    external_ref = len(audit.get("external_ref") or [])
    known_incompat = sum(len(v) for v in audit.values())

    return f"""# PHASE 3B — REAL SOURCE ANALYZER ON CLEAN DERIVED TRANSCRIPT

## 1. Résultat

**{result.outcome}**

- PIPELINE RESULT : {result.pipeline_result}
- REAL CALL RESULT : {result.real_call_result}
- stop_reason : {result.stop_reason or "(aucun)"}
- error_type : {result.error_type or "(aucun)"}
- error_message : {result.error_message or "(aucun)"}

## 2. Baseline

Commande : `.venv\\Scripts\\python.exe -m pytest -q`

Avant exécution : **1659 passed**, 0 failed, 2 warnings historiques (`app.chunk_service` RuntimeWarning).

Après exécution : {result.tests_after or "voir section 29."}

## 3. Input

- path : `{result.input_path}`
- mode : {result.mode}
- transcript_id : {result.transcript_id}
- segments : {result.segment_count}
- words : {result.word_count}
- duration : {result.duration_seconds} s
- SHA : `{result.clean_sha256}`

## 4. Provenance

- cleanup audit SHA : `{result.cleanup_application_sha256}`
- original segments : {provenance.get("original_segments", "n/a")}
- clean segments : {provenance.get("clean_segments", "n/a")}
- removed : {provenance.get("removed_segments", "n/a")}
- removed_set_matches : {_yn(provenance.get("removed_set_matches"))}
- survivors_unchanged : {_yn(provenance.get("survivors_unchanged"))}
- policy : {provenance.get("policy", "n/a")}
- validation : {"PASS" if provenance.get("valid") else "FAIL / n/a"}

## 5. Protected sources

Hash before :

{hashes_before}

## 6. Preflight

- provider : {result.provider}
- model : {result.model}
- credential available : {_yn(result.credential_available)}
- strategy : {result.strategy}
- estimated tokens system : {tokens.get("system", "n/a")}
- estimated tokens user : {tokens.get("user", "n/a")}
- estimated tokens total : {tokens.get("total", "n/a")}
- method : {tokens.get("method", "n/a")}
- usable input budget : {result.usable_input_budget}
- remaining margin : {result.remaining_margin}
- temperature : {result.temperature}
- max_output_tokens : {result.max_output_tokens}
- context_safety_ratio : {result.context_safety_ratio}

## 7. Signature

- clean signature : `{result.clean_signature}`
- original signature : `{result.original_signature}`
- different : {_yn(result.signatures_differ)}

## 8. Cache

- hit : {_yn(result.cache_hit)}
- source_map existed before : {_yn(result.source_map_existed_before)}

## 9. Prompt

- version : {result.prompt_version}
- SHA : `{result.prompt_sha256}`
- real SRC IDs preserved : {_yn(result.real_src_ids_preserved)}
- removed SRC absent : {_yn(result.removed_src_absent_from_prompt)}

Le prompt complet n'est pas reproduit ici.

## 10. Canonical schema

- version : {result.canonical_schema_version}
- SHA : `{result.canonical_schema_sha256}`

## 11. Anthropic provider schema

- SHA : `{result.provider_schema_sha256}`
- additionalProperties_not_false : {additional_not_false}
- minLength provider : {min_length}
- unsupported minItems : {unsupported_min_items}
- unsupported recursive / external refs : {external_ref}
- known incompatibilities : {known_incompat}
- audit clean : {_yn(result.schema_audit_clean)}

## 12. Real call guard

- max calls = {result.max_real_calls}
- actual real calls = {result.real_call_count}
- max attempts = {result.max_attempts}

## 13. Real Anthropic call

- executed : {_yn(result.real_call_executed)}
- HTTP/provider result : {result.real_call_result}
- latency_ms : {result.latency_ms}
- request id : {result.request_id or "(absent — non bloquant)"}
- finish reason : {result.finish_reason or "n/a"}

## 14. Usage

- input_tokens : {result.input_tokens}
- output_tokens : {result.output_tokens}
- total_tokens : {result.total_tokens}
- usage_source : {result.usage_source or "n/a"}
- provider usage : {_yn(result.provider_usage)}

## 15. Cost

- input : {result.input_cost}
- output : {result.output_cost}
- total : {result.total_cost}
- currency : {result.cost_currency or "n/a"}
- status : {result.cost_status or "n/a"}
- pricing source : {result.pricing_version or "n/a"}
- effective date : {result.pricing_effective_date or "n/a"}

## 16. Structured output

- native output_config active : {_yn(result.native_output_config)}
- provider parse result : {_passfail(result.provider_parse)}

## 17. Canonical parse

{_passfail(result.canonical_parse)}

## 18. Normalization

{_passfail(result.normalization)}

## 19. SourceMap validation

{_passfail(result.source_map_validation)}

## 20. Source refs

- total referenced : {result.referenced_source_count}
- all exist in clean : {_yn(result.all_refs_in_clean)}
- any removed SRC referenced : {_yn(result.any_removed_referenced)}

## 21. Coverage

- referenced source count : {result.referenced_source_count}
- clean source count (population) : {result.clean_source_count}
- coverage ratio : {result.coverage_ratio}

## 22. SourceMap contents

- topics : {result.topic_count}
- ideas : {result.idea_count}
- examples : {result.example_count}
- references : {result.reference_count}
- uncertainties : {result.uncertainty_count}
- repetitions : {result.repetition_count}
- author intent kinds : {intent_kinds}
- target audience kinds : {audience_kinds}
- main theme non-empty : {_yn(result.main_theme_present)}
- voice profile present : {_yn(result.voice_profile_present)}

Aucune critique éditoriale approfondie n'est faite ici.

## 23. Completeness

{_passfail(result.completeness)}

## 24. Editorial leakage

forbidden fields = {editorial}

## 25. Output artifact

- source_map path : `{result.source_map_path}`
- exists : {_yn(result.source_map_exists)}
- size : {result.source_map_size}
- SHA : `{result.source_map_sha256}`

## 26. Atomicity

partial leftovers : {_yn(result.partial_leftovers)}

## 27. report.json

- updated : {_yn(result.report_json_updated)}
- status : {result.report_json_status or "n/a"}

## 28. project_state

status : {result.project_state_status or "n/a"}

## 29. Tests after

{result.tests_after or "Exécutés hors processus d'analyse ; voir le complément de cette section après pytest."}

## 30. Network

- Anthropic = {network.get("anthropic", 0)}
- OpenAI = {network.get("openai", 0)}
- Whisper = {network.get("whisper", 0)}
- Ollama = {network.get("ollama", 0)}
- LM Studio = {network.get("lm_studio", 0)}
- other = {network.get("other", 0)}

## 31. Protected source integrity

Hash after :

{hashes_after}

- violations : {violations}
- all unchanged : {_yn(result.protected_unchanged)}

## 32. Files created/modified

{files}

## 33. Technical decision

- Le vrai appel Anthropic a-t-il été effectué ? {_yn(result.real_call_executed)}
- Combien d'appels ? {result.real_call_count}
- Quel modèle ? {result.model}
- Le provider a-t-il accepté le native structured output ? {_yn(result.native_output_config)}
- La réponse provider était-elle structurellement parseable ? {_passfail(result.provider_parse)}
- La validation canonique a-t-elle réussi ? {_passfail(result.canonical_parse)}
- La normalisation a-t-elle réussi ? {_passfail(result.normalization)}
- Le SourceMap final a-t-il réussi tous les invariants ? {_passfail(result.source_map_validation)}
- Tous les source_refs appartiennent-ils au transcript clean ? {_yn(result.all_refs_in_clean)}
- Un SRC supprimé a-t-il été référencé ? {_yn(result.any_removed_referenced)}
- Combien de SRC sont couverts ? {result.referenced_source_count}
- Quel est le ratio de coverage ? {result.coverage_ratio}
- Combien de topics ? {result.topic_count}
- Combien d'ideas ? {result.idea_count}
- Combien d'examples ? {result.example_count}
- Combien de references ? {result.reference_count}
- Combien d'uncertainties ? {result.uncertainty_count}
- Combien de repetitions ? {result.repetition_count}
- Le main_theme est-il présent ? {_yn(result.main_theme_present)}
- Le author_voice_profile est-il présent ? {_yn(result.voice_profile_present)}
- Y a-t-il une fuite éditoriale ? {editorial}
- Combien de tokens réels ? input={result.input_tokens} output={result.output_tokens} total={result.total_tokens}
- Quel coût ? {result.total_cost} {result.cost_currency} (status={result.cost_status or "n/a"})
- Quelle latence ? {result.latency_ms} ms
- source_map.json a-t-il été publié ? {_yn(result.source_map_exists)}
- Les artefacts protégés sont-ils inchangés ? {_yn(result.protected_unchanged)}
- Les tests sont-ils verts ? {result.tests_after or "voir section 29"}
- Existe-t-il encore une anomalie technique empêchant Phase 4 ? {result.remaining_anomaly or ("non — revue humaine requise avant Phase 4" if result.outcome == "PASS" else "oui — voir stop_reason / error")}
"""
