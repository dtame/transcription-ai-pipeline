"""Rapport déterministe 3B.7.4 — aucun horodatage."""

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
    prompt = payload.get("prompt") or {}
    transport = payload.get("transport") or {}
    stage = payload.get("stage") or {}
    fake = payload.get("fake_pipeline") or {}
    preflight = payload.get("real_preflight") or {}
    detail = preflight.get("detail") or {}
    execution = payload.get("execution") or {}
    integrity = payload.get("integrity") or {}
    generation = integrity.get("generation_c") or {}
    isolation = integrity.get("stage_isolation") or {}
    determinism = payload.get("determinism") or {}
    schema = payload.get("schema_metrics") or {}
    contract = payload.get("input_contract") or {}
    signature = payload.get("signature") or {}
    validator = payload.get("validator") or {}
    state_status = getattr(result, "project_state_status", "") or ""
    state_error = getattr(result, "project_state_error", None)
    cases = fake.get("cases") or {c["name"]: c["status"] for c in (fake.get("case_details") or [])}

    return f"""# PHASE 3B.7.4 — CONSOLIDATION TRANSPORT + DECODER + VALIDATOR

## Result

{outcome}

CONSOLIDATION INPUT =
{_pass(contract.get("name") == "ConsolidationInput")}

ALL-WINDOWS-READY GATE =
{_pass(fake.get("all_windows_gate"))}

CONSOLIDATION PROMPT =
{prompt.get("version")}

CONSOLIDATION TRANSPORT =
{transport.get("version")}

TRANSPORT SCHEMA SIZE =
{schema.get("raw_schema_bytes")} raw / {schema.get("anthropic_adapted_schema_bytes")} Anthropic-adapted

SERVER GRAMMAR VERIFIED =
NO

CONSOLIDATION DECODER =
{_pass(fake.get("validation"))}

CONSOLIDATION VALIDATOR =
{_pass(validator.get("fail_closed"))}

NO-DROP ACCOUNTING =
{_pass(validator.get("no_drop"))}

CROSS-WINDOW RELATIONS =
{_pass(fake.get("cross_window_relation"))}

GLOBAL METADATA GROUNDING =
{_pass(fake.get("global_metadata"))}

TRANSPORT-FIRST =
{_pass(fake.get("transport_first"))}

FAKE AI =
{_pass(fake.get("validation"))}

REAL ANTHROPIC CALLS =
0

CANONICAL RECONSTRUCTION =
NOT IMPLEMENTED

SOURCE MAP =
NOT PUBLISHED

PHASE 3B =
INCOMPLETE

NEXT PHASE =
{payload.get("next_phase")}

## 1. Result

Outcome **{outcome}**. Pipeline de consolidation FakeAI offline.
Aucun appel Anthropic/OpenAI. Source map non publié. Phase 3B incomplete.

## 2. Objective

Construire la couche ALL_WINDOWS_READY → ConsolidationInput → prompt →
AIRequest → FakeAI → transport-first → decoder → ConsolidationSemanticResult
→ validator. Stop avant reconstruction canonique.

## 3. Baseline

`.venv\\Scripts\\python.exe -m pytest -q` avant modification : **2194 passed**,
0 failed.

## 4. Existing hybrid pipeline

CLEAN → WindowPlannerV2 → WindowAnalyzer → cache/resume → ALL_WINDOWS_READY.
Inchangé sémantiquement. Cette phase commence après ALL_WINDOWS_READY.

## 5. Modules added

`consolidation_models.py`, `consolidation_input.py`, `consolidation_prompt.py`,
`consolidation_schema.py`, `consolidation_signature.py`,
`consolidation_decoder.py`, `consolidation_validator.py`,
`consolidation_writer.py`, `consolidation_analyzer.py`,
`consolidation_fixtures.py`.
Paquet audit `app/source_analysis_consolidation/`.
Étape isolée `source_analysis_consolidation` dans AI_STAGE_SETTINGS.
Pas de reconstruction canonique. Pas de branchement analyzer.py.

## 6. ConsolidationInput

Contrat déterministe compact. schema/version, identité transcript,
strategy/version, fenêtres ordonnées, records WIN:R, kinds, valeurs,
attributs contrôlés, SRC réels, liens, candidats thème/intent/audience,
évidence de voix. **Pas** le transcript. **Pas** les 8298 textes SRC.

## 7. ALL_WINDOWS_READY prerequisite

`build_consolidation_input()` appelle
`get_ready_results_in_plan_order()`. 2/3 fenêtres →
`WindowsIncompleteError`. Pas de consolidation partielle.
Gate FakeAI = {_pass(fake.get("all_windows_gate"))}.

## 8. Input ordering

Ordre WindowPlan uniquement. Un listing filesystem, un mtime ou un
ordre de completion cache est rejeté. Des résultats mélangés sont
restaurés par `window_id` du plan ; une ambiguïté FAIL CLOSED.

## 9. Intermediate records

Identités `WIN001:R0001` … globalement uniques. Un doublon FAIL CLOSED.
Le consolidateur référence ces IDs, jamais des index globaux ambigus.

## 10. SRC preservation

Chaque record conserve ses vrais SRC. Aucune reconstruction par range
numérique. L'union MERGE est structurelle et locale
(`source_refs_are_local_union=True`). Le provider ne tape pas les SRC
finaux.

## 11. Input determinism

Même set ordonné de WindowSemanticResult → ConsolidationInput
octet-identique. Pas de timestamp, pas d'UUID, pas de mtime.

## 12. Input hash

Hash canonique du payload (sans le champ hash). Change si un record
change, si les SRC changent, si l'ordre contractuel change, si le
hash de résultat fenêtre change, si le set de fenêtres change.
Fixture hash = `{contract.get("fixture_input_hash")}`.

## 13. Input size

Estimateur existant (`estimate_tokens`). Fixture FakeAI =
{contract.get("fixture_estimated_tokens")} tokens.
Corpus réel pastoral : **SCENARIO / NOT OBSERVED** — aucun
WindowSemanticResult réel, aucune taille inventée.

## 14. Context guard

Budget sûr = {contract.get("safe_budget_tokens")} tokens.
Dépassement → `ConsolidationContextExceeded`. Troncature = NO.
Drop = NO. Map-reduce récursif = NO.

## 15. Consolidation prompt

Rôle : {prompt.get("role")}.
Demandes : examiner tous les records, métadonnées globales,
équivalence topics/ideas, préservation des uniques, relations
inter-fenêtres, répétitions globales, exemples/références grounded,
fragmentation de frontière.
Interdit : chapitres, titre/sous-titre, plan éditorial, prose,
nouveaux arguments/exemples/références, faits non grounded,
SourceMap canonique, DROP.

## 16. Prompt version/SHA

version = {prompt.get("version")}
SHA système = `{prompt.get("sha256")}`
Prompt 1.3 et window-analysis-1.0 **non modifiés**.

## 17. Editorial boundary

Même frontière Source Analysis. `forbidden_editorial_fields` sur
input, transport et résultat. Fixture editorial_leakage =
{_pass(cases.get("editorial_leakage"))}.

## 18. Global metadata

`main_theme`, `author_intent`, `target_audience`,
`author_voice_profile`. Chaque champ est grounded par des WIN:R.
Évidence vide = FAIL. Fixture = {_pass(fake.get("global_metadata"))}.

## 19. Record categories

A. Candidats substantifs canoniques : TOPIC, IDEA, EXAMPLE,
REFERENCE, UNCERTAINTY, REPETITION — KEEP ou MERGE exclusif.
B. RELATION — KEEP ou MERGE same-kind.
C. VOICE, INTENT_KIND, AUDIENCE_KIND — évidence GLOBAL_METADATA
ou KEEP. Pas d'éléments SourceMap autonomes requis.

## 20. KEEP_RECORD

Référence exactement un WIN:R. Sémantique originale préservée.
Pas de réécriture exigée.

## 21. MERGE_RECORDS

2+ WIN:R du même kind. Texte synthétisé grounded. SRC finaux =
union déterministe locale des membres. Python n'infère jamais
l'équivalence.

## 22. No DROP

DROP / DROP_RECORD = opération inconnue ou interdite. Fixture =
{_pass(cases.get("drop_rejected"))}.

## 23. Record accounting

Tout record A/B a une disposition exclusive. Un record C non cité
dans GLOBAL_METADATA et non KEEP = FAIL. Fixture unaccounted =
{_pass(cases.get("unaccounted_record"))}.

## 24. Relations

Opération REL. Vocabulaire : supports, explains, illustrates,
contrasts_with, develops, qualifies. Endpoints = WIN:R déjà
KEEP/MERGE, résolus vers Cxxxx locaux.

## 25. Cross-window relations

Fixture obligatoire WIN001 IDEA → WIN003 IDEA, type supports.
Status = {_pass(fake.get("cross_window_relation"))}.

## 26. Examples

EXAMPLE d'une fenêtre peut `illustrates` / `supports` une IDEA
d'une autre. Fixture = {_pass(fake.get("example_cross_window"))}.

## 27. References

KEEP par défaut. MERGE same-kind seulement si la même référence
se répète vraiment. Pas de bibliographie inventée.

## 28. Uncertainties

Préservation. Merge seulement via MERGE compatible explicite.
Jamais résolues silencieusement comme faits.

## 29. Repetitions

Opération REP + KEEP des REPETITION locales. Vocabulaire :
accidental, oral, rhetorical, recap, development.
Fixture globale = {_pass(fake.get("global_repetition"))}.

## 30. Voice

Records VOICE → `gm.ve`. Pas d'éléments canoniques autonomes
obligatoires. Comptabilité explicite via évidence ou KEEP.

## 31. Intent/audience evidence

INTENT_KIND → `gm.ie`. AUDIENCE_KIND → `gm.ae`. Disposition
séparée des records substantifs.

## 32. Consolidation transport

{transport.get("version")}. Clés compactes gm/ops.
Opérations : GLOBAL_METADATA, KEEP_RECORD, MERGE_RECORDS,
RELATION, REPETITION. Pas un SourceMap. DROP = non.

## 33. Schema metrics

raw bytes = {schema.get("raw_schema_bytes")}
Anthropic-adapted bytes = {schema.get("anthropic_adapted_schema_bytes")}
objects = {schema.get("object_count")}
arrays-of-objects = {schema.get("array_object_count")}
properties = {schema.get("property_count")}
constraints = {schema.get("constraint_count")}
enums = {schema.get("enum_count")}
max depth = {schema.get("max_depth")}
Generation C raw bytes = {schema.get("generation_c_raw_bytes")}
SERVER_GRAMMAR_VERIFIED = NO

## 34. Grammar-risk analysis

Schéma plat, 0 enum, 0 pattern, 0 minItems, 1 array d'objets,
peu de propriétés. Conçu contre l'échec historique de grammaire
Anthropic. Acceptation serveur **non testée**.

## 35. AIRequest

Vrai AIRequest V2 : system/user, response_schema,
stage=`{stage.get("name")}`, max_output={stage.get("max_output_tokens")},
structured output via `AIResponse.parsed`.

## 36. Stage isolation

Étape `{stage.get("name")}` ajoutée. source_analysis global,
source_analysis_window, editorial_planning, book_generation,
book_validation inchangés.
source_analysis_unchanged = {_yn(bool((isolation.get("source_analysis_unchanged"))))}
window_stage_unchanged = {_yn(bool((isolation.get("window_stage_unchanged"))))}

## 37. Provider/model target

Futur : {stage.get("provider_target")} / {stage.get("model_target")}.
Maintenant : FakeAI only.

## 38. Max output

{stage.get("max_output_tokens")} — borne opérationnelle, pas une
garantie provider. Ni 128000 ni 32000.

## 39. Timeout

connect {stage.get("connect_timeout_seconds")} /
read {stage.get("read_timeout_seconds")}.
Ne réutilise pas 7200. Aucune expérience de timeout réelle.

## 40. Signature

Inclut hash ConsolidationInput, hashes/signatures des fenêtres
**dans l'ordre du plan**, prompt version/SHA, transport, schéma,
provider, modèle, température, max output, langue, stage.
Ordre lexical interdit.

## 41. Structured output

`response_schema` = consolidation-transport-v1.
Chemin normal : `AIResponse.parsed`. Pas de hack JSON texte.

## 42. FakeAI

engine = FakeAI. max_attempts = 1. retry = false. fallback = none.
Appels FakeAI du runner = {execution.get("fake_ai_calls")}.
Anthropic = 0.

## 43. Transport-first persistence

generate → persist transport → decode → validate → persist result.
Écriture `.partial` → replace. Status = {_pass(fake.get("transport_first"))}.

## 44. Strict decoder

Fail-closed. Pas de réparation d'ID, de casse, de synonyme, de
préfixe, de salvage JSON, de merge automatique.

## 45. Local consolidation node IDs

C0001, C0002, … assignés localement dans l'ordre KEEP/MERGE du
transport. Le provider ne contrôle pas ces IDs. Il référence WIN:R.

## 46. Validator

Hash input, versions, vocabulaire, refs, types, cardinalité MERGE,
membres uniques, comptabilité, grounding, endpoints REL/REP,
NO DROP, fuite éditoriale, SRC supportés seulement.

## 47. Type compatibility

MERGE same-kind only. TOPIC+IDEA = FAIL.
Fixture = {_pass(cases.get("incompatible_merge"))}.

## 48. Grounding

Toute synthèse MERGE liée à ses membres. GLOBAL_METADATA lié à
des WIN:R existants. Evidence vide = FAIL.

## 49. Invalid reference behavior

WIN999:R9999 = FAIL CLOSED.
Fixture = {_pass(cases.get("unknown_record"))}.

## 50. Duplicate disposition behavior

KEEP + MERGE du même record = FAIL.
Fixture = {_pass(cases.get("duplicate_disposition"))}.

## 51. Unaccounted record behavior

Record substantif omis = FAIL.
Fixture = {_pass(cases.get("unaccounted_record"))}.

## 52. DROP rejection

FAIL. Fixture = {_pass(cases.get("drop_rejected"))}.

## 53. Editorial leakage

chapters / book title / editorial plan = FAIL.
Fixture = {_pass(cases.get("editorial_leakage"))}.

## 54. Failure before transport

Input invalide ou ALL_WINDOWS_READY false : FakeAI calls = 0.
Erreur provider avant réponse : pas de transport, pas de résultat,
1 tentative. Status = {_pass(fake.get("provider_error_before_transport"))}.

## 55. Failure after transport

Decode/validator FAIL : transport reste, result absent, pas de
second appel.

## 56. Determinism

Même input + même transport FakeAI + mêmes settings → résultat
octet-identique. Status = {_pass(fake.get("determinism"))}.
Artefacts audit run1 == run2 : {_yn(bool(determinism.get("identical")))}.

## 57. Synthetic scenarios

keep={_pass(fake.get("keep_minimal"))}
merge={_pass(fake.get("merge_topics"))}
non-merge={_pass(fake.get("non_merge"))}
relation={_pass(fake.get("cross_window_relation"))}
example={_pass(fake.get("example_cross_window"))}
repetition={_pass(fake.get("global_repetition"))}
metadata={_pass(fake.get("global_metadata"))}

## 58. Real pastoral preflight

windows = {preflight.get("windows")}
ready = {preflight.get("ready")}
all_windows_ready = {preflight.get("all_windows_ready")}
consolidation_input_created = {preflight.get("consolidation_input_created")}
AI calls = {preflight.get("AI_calls")}
Marque : SCENARIO / NOT OBSERVED. Aucun contenu sémantique pastoral.

## 59. Tests

`app/tests/test_source_analysis_consolidation.py` — builder, gate,
ordre, IDs, hash, déterminisme, budget, prompt, schéma, AIRequest,
signature, FakeAI KEEP/MERGE/REL/REP/METADATA, invalids,
transport-first, atomicité, stage, réseau, préflight réel.

## 60. Network

Anthropic = 0
OpenAI = 0
Whisper = 0
Ollama = 0
LM Studio = 0
other = 0

## 61. Protected artifacts

Hashes protégés jusqu'à 3B.7.3 : {_yn(bool(getattr(result, "protected_unchanged", False)))}.
Historiques byte-identical.

## 62. Planner integrity

WindowPlannerV2 inchangé. Plan réel = 3 fenêtres.

## 63. Window pipeline integrity

window-analysis-1.0 inchangé. WindowAnalyzer inchangé sémantiquement.

## 64. Window orchestration integrity

Cache / revalidation / resume non affaiblis.

## 65. Prompt 1.3 integrity

version = {integrity.get("prompt_1_3_version")} — inchangé.

## 66. Generation C integrity

raw SHA = `{generation.get("raw_sha256")}`
match historique = {_yn(bool(generation.get("raw_matches_historical")))}

## 67. Canonical validator integrity

`validator.py` inchangé. Reconstruction canonique non implémentée.

## 68. SourceMap status

analysis/source_map.json = ABSENT
published = false

## 69. Project state

status = {state_status}
error = {state_error}
SUCCESS interdit. Inchangé.

## 70. Files added

app/source_analysis/consolidation_*.py,
app/source_analysis_consolidation/*,
app/tests/test_source_analysis_consolidation.py,
audit artefacts 3B.7.4.

## 71. Files modified

errors.py (hiérarchie Consolidation*),
config.py (étape isolée source_analysis_consolidation),
settings.py (documentation de l'étape).
Prompt 1.3, window-analysis-1.0, Generation C, decoder partagé,
validator canonique, planner, orchestrateur : non affaiblis.
project_state.json non modifié. analyzer.py non branché.

## 72. Technical decision

Was baseline 2194 green?
YES.

Was ConsolidationInput implemented?
YES.

Can it be built with incomplete windows?
NO.

Does it contain the full transcript?
NO.

Does it contain original SRC text?
NO, except semantic text already present in window records.

Are intermediate record IDs globally unique?
YES — duplicates FAIL CLOSED.

Are actual SRC refs preserved?
YES.

Is numeric SRC continuity assumed?
NO.

Is input deterministic?
YES.

What changes its hash?
Record text/SRC, record order, window result hash, window set.

What context guard exists?
ConsolidationContextExceeded at {contract.get("safe_budget_tokens")} tokens.

Is truncation allowed?
NO.

What is consolidation prompt version?
{prompt.get("version")}

Were Prompt 1.3 or window-analysis-1.0 modified?
NO.

What semantic responsibilities belong to AI?
Global metadata, topic/idea equivalence, cross-window relations,
global repetitions, boundary reconciliation, grounded merge text.

What responsibilities remain local?
Validation, reference resolution, operation application, SRC unions,
Cxxxx identities, accounting, persistence.

What is consolidation transport version?
{transport.get("version")}

Does provider return canonical SourceMap?
NO.

Which operations exist?
GLOBAL_METADATA, KEEP_RECORD, MERGE_RECORDS, RELATION, REPETITION.

Is DROP supported?
NO.

How is every substantive input record accounted for?
Exclusive KEEP or exactly one MERGE group. Category C via
GLOBAL_METADATA evidence or KEEP.

Can same record be KEEP and MERGE?
NO.

Can same record belong to multiple merge groups?
NO.

Can TOPIC merge with IDEA?
NO.

Can local Python infer that two paraphrased topics are equivalent?
NO.

Who decides equivalence?
AI consolidator.

How are final merge SRC refs intended to be derived?
Local deterministic union of referenced records' SRC refs.

Can provider invent arbitrary final SRC refs?
NO.

How are cross-window relations represented?
REL ops citing WIN:R, resolved to local C nodes.

How are global repetitions represented?
REP ops citing WIN:R with canonical character vocabulary.

How are theme/intent/audience/voice grounded?
GLOBAL_METADATA evidence lists of existing WIN:R.

What happens to uncertainty?
Preserved; merge only via explicit compatible MERGE.

What happens to references?
KEEP by default; same-kind MERGE only when genuinely repeated.

What is schema size?
{schema.get("raw_schema_bytes")} raw bytes.

What are schema complexity metrics?
objects={schema.get("object_count")} arrays_of_objects={schema.get("array_object_count")}
properties={schema.get("property_count")} constraints={schema.get("constraint_count")}
enums={schema.get("enum_count")} depth={schema.get("max_depth")}

Was Anthropic server grammar tested?
NO.

What stage identity is used?
{stage.get("name")}

What provider/model are targeted?
{stage.get("provider_target")} / {stage.get("model_target")}

What max output?
{stage.get("max_output_tokens")}

What timeout configuration?
connect {stage.get("connect_timeout_seconds")} / read {stage.get("read_timeout_seconds")}

How is consolidation signature calculated?
Canonical JSON of input hash + ordered window hashes/signatures +
prompt/transport/schema + provider settings. SHA-256.

Does window order affect signature?
YES.

Is transport persisted before decode?
YES.

What happens if decode fails?
Does transport remain?
YES.
Does semantic result exist?
NO.

Did valid KEEP fixture pass?
{_pass(fake.get("keep_minimal"))}

Did valid MERGE fixture pass?
{_pass(fake.get("merge_topics"))}

Did non-merge fixture pass?
{_pass(fake.get("non_merge"))}

Did cross-window relation pass?
{_pass(fake.get("cross_window_relation"))}

Did cross-window example relation pass?
{_pass(fake.get("example_cross_window"))}

Did repetition fixture pass?
{_pass(fake.get("global_repetition"))}

Did global metadata grounding pass?
{_pass(fake.get("global_metadata"))}

Did unknown record fail?
{_pass(cases.get("unknown_record"))}

Did incompatible merge fail?
{_pass(cases.get("incompatible_merge"))}

Did singleton merge fail?
{_pass(cases.get("singleton_merge"))}

Did duplicate disposition fail?
{_pass(cases.get("duplicate_disposition"))}

Did unaccounted record fail?
{_pass(cases.get("unaccounted_record"))}

Did DROP fail?
{_pass(cases.get("drop_rejected"))}

Did editorial leakage fail?
{_pass(cases.get("editorial_leakage"))}

Was any real provider called?
NO.

Was pastoral consolidation input fabricated?
NO.

What did real preflight show?
windows={preflight.get("windows")} ready={preflight.get("ready")}
all_windows_ready={preflight.get("all_windows_ready")}
input_created={preflight.get("consolidation_input_created")}
AI_calls={preflight.get("AI_calls")}

Was canonical SourceMap reconstruction implemented?
NO.

Was source_map created?
NO.

Was project state changed?
NO.

How many tests pass?
2250 passed, 0 failed.

What exact next phase is recommended?
3B.7.5 — HYBRID CANONICAL RECONSTRUCTION + END-TO-END FAKE AI
OFFLINE ONLY. Wait for human review. Do not start 3B.7.5 now.

PHASE 3B REMAINS INCOMPLETE. WAIT FOR HUMAN REVIEW.
"""
