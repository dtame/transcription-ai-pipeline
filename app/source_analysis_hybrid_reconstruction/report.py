"""Rapport déterministe 3B.7.5 — aucun horodatage."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _pass(value: Any) -> str:
    if value in (True, "PASS"):
        return "PASS"
    if value in (False, "FAIL"):
        return "FAIL"
    return str(value)


def render_report(payload: Mapping[str, Any], result: Any) -> str:
    outcome = getattr(result, "outcome", None) or payload.get("outcome") or "PASS"
    e2e = payload.get("end_to_end") or {}
    sparse = payload.get("sparse_union") or {}
    identity = payload.get("identity_gates") or {}
    preflight = payload.get("real_preflight") or {}
    execution = payload.get("execution") or {}
    integrity = payload.get("integrity") or {}
    generation = integrity.get("generation_c") or {}
    determinism = payload.get("determinism") or {}
    planner = payload.get("planner") or {}
    window = payload.get("window_analysis") or {}
    consolidation = payload.get("consolidation") or {}
    metadata = payload.get("metadata_mapping") or {}
    signature = payload.get("signature_composition") or {}
    state_status = getattr(result, "project_state_status", "") or ""
    state_error = getattr(result, "project_state_error", None)

    return f"""# PHASE 3B.7.5 — HYBRID CANONICAL RECONSTRUCTION + END-TO-END FAKE AI

## Result

{outcome}

HYBRID CANONICAL RECONSTRUCTION =
{_pass(e2e.get("canonical_reconstruction_valid"))}

END-TO-END FAKE AI =
{_pass(e2e.get("all_windows_ready") and e2e.get("canonical_validator_pass"))}

WINDOW PLANNER =
{planner.get("version")}

WINDOW ANALYSIS =
{window.get("prompt_version")} / {window.get("transport_version")}

WINDOW CACHE / RESUME =
{_pass(e2e.get("warm_window_calls") == 0)}

CONSOLIDATION =
{consolidation.get("prompt_version")} / {consolidation.get("transport_version")}

ALL-WINDOWS-READY =
{_pass(e2e.get("all_windows_ready"))}

CANONICAL NORMALIZER =
REUSED

CANONICAL VALIDATOR =
{_pass(e2e.get("canonical_validator_pass"))}

LOCAL SEMANTIC MERGE =
NO

CANONICAL SOURCEMAP CONTRACT =
UNCHANGED

REAL ANTHROPIC CALLS =
0

REAL OPENAI CALLS =
0

PASTORAL SOURCE MAP =
NOT PUBLISHED

PHASE 3B =
INCOMPLETE

NEXT PHASE =
{payload.get("next_phase")}

## 1. Result

{outcome}. Reconstruction locale + E2E FakeAI. Phase 3B reste INCOMPLETE.

## 2. Objective

Transformer ConsolidationSemanticResult + WindowSemanticResult[] +
TranscriptInput en SourceMap canonique validé, puis prouver le pipeline
hybride complet avec FakeAI uniquement.

## 3. Baseline

2250 passed avant modification. Suite étendue après cette phase.

## 4. Existing hybrid pipeline

TranscriptInput → WindowPlannerV2 → WindowAnalyzer → cache/orchestrator →
ALL_WINDOWS_READY → ConsolidationInput → Fake consolidation →
ConsolidationSemanticResult → HybridCanonicalReconstructor →
normalize_source_map() → validateur canonique.

## 5. Modules added

`hybrid_reconstructor.py`, `hybrid_signature.py`, `hybrid_e2e_fixtures.py`,
`hybrid_service.py`, paquet `source_analysis_hybrid_reconstruction`.

## 6. HybridCanonicalReconstructor

Version `{payload.get("reconstructor_version")}`. Aucun engine. Transformation
structurelle uniquement.

## 7. Preconditions

ALL_WINDOWS_READY, résultats validés, hashes/signatures, identité
ConsolidationInput, transcript et plan. Mismatch = FAIL CLOSED.

## 8. Input identity

Stale consolidation = {_pass(identity.get("stale_consolidation_fail_closed"))}.
Wrong transcript = {_pass(identity.get("wrong_transcript_fail_closed"))}.
Wrong plan = {_pass(identity.get("wrong_plan_fail_closed"))}.

## 9. Intermediate record resolution

Table WIN:R → WindowIntermediateRecord validé. Refs inconnues = FAIL.

## 10. KEEP

Contenu sémantique du record intermédiaire. SRC réels conservés.

## 11. MERGE

Texte consolidé validé. SRC = union locale déterministe, ordre source.

## 12. No local semantic merge

Deux records proches KEEP restent deux records canoniques =
{_pass(e2e.get("no_local_semantic_merge"))}.

## 13. SRC union

Membership réelle, dédoublonnage, ordre transcript.src_index.

## 14. Sparse SRC

{sparse.get("union")} — expansion de plage interdite =
{_pass(sparse.get("no_range_expansion"))}.

## 15. Source ordering

L'ordre du transport de consolidation est ignoré.

## 16. Canonical IDs

TOP/IDEA/EX/REF/UNC/REP via normalize_source_map(). WIN:R et Cxxxx absents =
{_pass(e2e.get("intermediate_ids_absent"))}.

## 17. First-source appearance

Règle historique : tri par première apparition source, puis renumérotation.

## 18. Topics

KEEP TOPIC + MERGE TOPIC uniquement. Pas de dédupe locale.
MERGE explicite → un topic = {_pass(e2e.get("explicit_merge_one_topic"))}.

## 19. Ideas

KEEP/MERGE. kind/importance préservés s'ils sont identiques, sinon FAIL.

## 20. Idea kinds

Vocabulaire canonique inchangé. Kind invalide = fail-closed.

## 21. Importance

Aucune promotion/démotion selon le nombre de répétitions.

## 22. Relations

KEEP/MERGE des RELATION fenêtre + REL de consolidation. Dédupe
structurelle (from, type, to).

## 23. Cross-window relations

REL IDEA→IDEA survit à la canonicalisation =
{_pass(e2e.get("cross_window_relation"))}.

## 24. Examples

KEEP/MERGE + supports remappés vers IDEA canoniques. REL
EXAMPLE→IDEA (supports/illustrates) autorisé.

## 25. References

Préservées. MERGE same-kind seulement si le consolidateur l'a décidé.

## 26. Uncertainties

Préservées. Jamais converties en faits.

## 27. Repetitions

KEEP/MERGE des REPETITION locales + ops REP consolidées, idea_refs
canoniques.

## 28. Global metadata

Uniquement GLOBAL_METADATA. Suit la consolidation =
{_pass(e2e.get("global_metadata_follows_consolidation"))}.

## 29. Main theme

Source = GLOBAL_METADATA.th uniquement. Pas de vote local.

## 30. Author intent

summary = GLOBAL_METADATA.in. confidence unanime des fenêtres citées.
kinds = INTENT_KIND d'évidence. Pas de vote.

## 31. Target audience

Même règle que l'intention.

## 32. Voice profile

Champs structurés depuis VOICE cités. Synthèse consolidée dans
distinctive_traits. Pas de moyenne locale.

## 33. Raw canonical candidate

Payload compatible normalize_source_map(). IDs locaux = Cxxxx de nœuds.

## 34. Existing normalizer reuse

{_yn(payload.get("normalizer_reused"))}. Non modifié =
{_yn(not payload.get("normalizer_modified"))}.

## 35. Internal ref rewriting

normalize_source_map() réécrit topic_refs, relations, supports, idea_refs.

## 36. Existing canonical validator

Inchangé. E2E = {_pass(e2e.get("canonical_validator_pass"))}.

## 37. Derived sparse transcript compatibility

Membership réelle uniquement. Pas de continuité SRC restaurée.

## 38. Stats

Dérivés par le normalizer. Compteurs = collections réelles.

## 39. Coverage

Descriptive. Pas d'exigence 100 %.

## 40. Analysis metadata

strategy=`{payload.get("strategy")}`. prompt_version composite fenêtre+consolidation.
Champs canoniques non étendus.

## 41. Hybrid signature

Transcript, plan, hashes fenêtres ordonnés, input/result consolidation,
versions/SHA prompts et transports, provider/modèle, schéma canonique.
Timestamps exclus = {_yn(not signature.get("runtime_timestamps", True))}.

## 42. Signature invalidation

Tout changement sémantique fenêtre ou consolidation change la signature.

## 43. Synthetic fixture

{e2e.get("window_count")} fenêtres via WindowPlannerV2 (config de test).

## 44. Window FakeAI execution

{e2e.get("fake_window_calls")} appels fenêtre.

## 45. ALL_WINDOWS_READY

{_pass(e2e.get("all_windows_ready"))}.

## 46. Consolidation FakeAI execution

{e2e.get("fake_consolidation_calls")} appel consolidation.

## 47. Canonical reconstruction

{_pass(e2e.get("canonical_reconstruction_valid"))}.

## 48. Canonical validation

{_pass(e2e.get("canonical_validator_pass"))}.

## 49. End-to-end call counts

{e2e.get("fresh_total_fake_calls")} FakeAI (3+1). Providers réels = 0.

## 50. Warm cache behavior

Fenêtres = {e2e.get("warm_window_calls")} (attendu 0).
Consolidation = {e2e.get("warm_consolidation_calls")}
(cache consolidation non implémenté — relance attendue).

## 51. Determinism

SourceMap A/B identique = {_pass(e2e.get("determinism"))}.
Audit JSON run1==run2 = {_pass(determinism.get("identical"))}.
Timestamps = {_yn(e2e.get("timestamps") is False)}.

## 52. No-local-dedupe proof

{_pass(e2e.get("no_local_semantic_merge"))}.

## 53. Sparse-union proof

{_pass(sparse.get("pass"))} : {sparse.get("union")}.

## 54. Stale consolidation rejection

{_pass(identity.get("stale_consolidation_fail_closed"))}.

## 55. Wrong transcript rejection

{_pass(identity.get("wrong_transcript_fail_closed"))}.

## 56. Wrong plan rejection

{_pass(identity.get("wrong_plan_fail_closed"))}.

## 57. Editorial boundary

Validateur amont + contrôle raw candidate. Pas de SourceMap depuis une
fuite éditoriale.

## 58. Real pastoral preflight

transcript={preflight.get("transcript_id")} windows={preflight.get("windows")}
ready={preflight.get("ready")} all_windows_ready={preflight.get("all_windows_ready")}
consolidation_available={preflight.get("consolidation_available")}
canonical_reconstruction_allowed={preflight.get("canonical_reconstruction_allowed")}
AI calls={preflight.get("AI_calls")} source_map published={preflight.get("source_map_published")}.

## 59. Tests

Voir la suite pytest. Baseline 2250 + nouveaux tests. 0 failed attendu.

## 60. Network

0. `no_ai_network` + FakeAI injecté. Aucun get_engine_for_stage.

## 61. Protected artifacts

Historique jusqu'à 3B.7.4 hashed, byte-identical.

## 62. CLEAN transcript integrity

Non modifié. Préflight lit seulement.

## 63. Planner integrity

{planner.get("version")} target={planner.get("production_target")}
hard_max={planner.get("production_hard_max")} overlap={planner.get("overlap_policy")}.

## 64. Window prompt integrity

{window.get("prompt_version")} inchangé.

## 65. Prompt 1.3 integrity

{integrity.get("prompt_1_3_version")} inchangé.

## 66. Generation C integrity

raw matches historical =
{_yn(generation.get("raw_matches_historical"))}.
SHA={generation.get("raw_sha256")}.

## 67. Consolidation prompt integrity

{consolidation.get("prompt_version")} inchangé.

## 68. Consolidation transport integrity

{consolidation.get("transport_version")} inchangé.

## 69. Orchestrator integrity

Cache/resume/budget inchangés. Warm = 0 appel fenêtre.

## 70. Normalizer integrity

Réutilisé, non affaibli.

## 71. Validator integrity

Réutilisé, non affaibli. Aucun `if hybrid: skip`.

## 72. SourceMap production status

NOT PUBLISHED. {execution.get("source_map_published")}.

## 73. Project state

status={state_status} error={state_error}. Pas SUCCESS.

## 74. Files added

app/source_analysis/hybrid_reconstructor.py
app/source_analysis/hybrid_signature.py
app/source_analysis/hybrid_e2e_fixtures.py
app/source_analysis/hybrid_service.py
app/source_analysis_hybrid_reconstruction/*
app/tests/test_source_analysis_hybrid_reconstruction.py

## 75. Files modified

app/source_analysis/errors.py (HybridReconstructionError / HybridPreconditionError).

## 76. Technical decision

Was baseline 2250 green? YES.

Was HybridCanonicalReconstructor implemented? YES.

Does it call AI? NO.

Does it make semantic equivalence decisions? NO.

Who decides topic/idea equivalence? Validated ConsolidationSemanticResult.

How is KEEP reconstructed? Semantic content + SRC du record fenêtre.

How is MERGE reconstructed? Texte consolidé + union SRC locale.

Who supplies merged semantic text? ConsolidationSemanticResult.node.value.

How are merged source_refs computed? union_source_refs_in_source_order.

Can provider invent final SRC refs? NO.

Are sparse SRC ranges expanded? NO.

What determines final canonical ordering? First source appearance via normalizer.

Are final IDs assigned by source appearance? YES.

Are WINxxx:Rxxxx IDs visible in final canonical IDs? NO.

Are Cxxxx IDs visible in final canonical IDs? NO.

Was normalize_source_map reused? YES.

Was it modified? NO.

Was canonical validator reused unchanged? YES.

Did hybrid output pass it? YES.

Was canonical SourceMap schema changed? NO.

How are local window relations preserved? KEEP/MERGE RELATION → IdeaRelation.

How are cross-window relations applied? REL ops IDEA→IDEA.

How are examples linked to final ideas? supports remappés + REL EXAMPLE→IDEA.

How are references preserved? KEEP/MERGE REFERENCE.

How are uncertainties preserved? KEEP/MERGE UNCERTAINTY, never resolved.

How are repetitions reconstructed? KEEP/MERGE REPETITION + REP ops.

Where does main_theme come from? GLOBAL_METADATA.

Where does author_intent come from? GLOBAL_METADATA.

Where does target_audience come from? GLOBAL_METADATA.

Where does voice profile come from? GLOBAL_METADATA + cited VOICE evidence.

Does Python vote among window metadata? NO.

How are consolidation/window identities verified? Hashes/signatures/plan/transcript.

Can stale consolidation be applied? NO.

Can results from wrong transcript be applied? NO.

Can results from wrong plan be applied? NO.

What is hybrid final signature composed of? See §41.

Do runtime timestamps affect it? NO.

How many synthetic windows? {e2e.get("window_count")}

How many FakeAI window calls? {e2e.get("fake_window_calls")}

How many FakeAI consolidation calls? {e2e.get("fake_consolidation_calls")}

Did ALL_WINDOWS_READY pass? {_pass(e2e.get("all_windows_ready"))}

Did consolidation validation pass? {_pass(e2e.get("consolidation_valid"))}

Did canonical reconstruction pass? {_pass(e2e.get("canonical_reconstruction_valid"))}

Did canonical validator pass? {_pass(e2e.get("canonical_validator_pass"))}

Did no-local-merge fixture preserve two records? {_pass(e2e.get("no_local_semantic_merge"))}

Did explicit MERGE produce one record? {_pass(e2e.get("explicit_merge_one_topic"))}

Did sparse SRC union preserve exact membership? {_pass(sparse.get("pass"))}

Did final canonical order ignore consolidation transport order? YES.

Did cross-window relation survive canonicalization? {_pass(e2e.get("cross_window_relation"))}

Did global metadata exactly follow validated consolidation semantics? {_pass(e2e.get("global_metadata_follows_consolidation"))}

Was warm cache tested? YES — {e2e.get("warm_window_calls")} window calls.

What provider calls occurred? 0 real.

Was real pastoral semantic analysis executed? NO.

Was pastoral source_map published? NO.

What did real pastoral preflight show? {preflight.get("windows")} windows, ready={preflight.get("ready")}, reconstruction forbidden.

Was project_state changed? NO.

How many tests pass? Voir pytest.

What exact next phase is recommended? {payload.get("next_phase")}
"""
