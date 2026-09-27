"""Rapport markdown déterministe — Phase 3B.7. Aucun timestamp."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_hybrid_design.constants import (
    BASELINE_FAILED,
    BASELINE_PASSED,
    FINAL_FAILED,
    FINAL_PASSED,
    CANONICAL_SOURCEMAP_CONTRACT,
    CANONICAL_VALIDATOR,
    CONSOLIDATION_SAFE_INPUT_TOKENS,
    EXPECTED_MODEL,
    EXPECTED_PROMPT_VERSION,
    EXPECTED_PROVIDER,
    HARD_MAX_INPUT_TOKENS,
    NEXT_PHASE_LABEL,
    OVERLAP_POLICY,
    PHASE_3B_STATUS,
    PLANNER_VERSION,
    TARGET_INPUT_TOKENS,
    WINDOW_TRANSPORT_VERSION,
)


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _window_table(windows: list[Mapping[str, Any]]) -> str:
    lines = [
        "| id | first owned | last owned | SRC | words | estimated tokens |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for window in windows:
        lines.append(
            "| {window_id} | {first} | {last} | {src} | {words} | {tokens} |".format(
                window_id=window.get("window_id"),
                first=window.get("first_owned_src") or window.get("first_src"),
                last=window.get("last_owned_src") or window.get("last_src"),
                src=window.get("owned_src_count") or window.get("segment_count"),
                words=window.get("word_count", ""),
                tokens=window.get("estimated_input_tokens"),
            )
        )
    return "\n".join(lines)


def render_report(
    *,
    simulation: Mapping[str, Any],
    window: Mapping[str, Any],
    consolidation: Mapping[str, Any],
    architecture: Mapping[str, Any],
) -> str:
    selected = simulation["selected_policy"]
    expected = selected["expected_windows"]
    global_est = simulation["global_estimate"]
    transcript = simulation["transcript"]
    current = simulation["current_planner_audit"]["results"]
    v2_rows = simulation["results"]
    boundaries = simulation["boundary_signals"]
    scenarios = consolidation["size_scenarios"]["scenarios"]
    calls = expected + 1

    current_lines = [
        "| budget | windows | min tokens | max tokens | tiny tail SRC |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in current:
        current_lines.append(
            "| {budget} | {n} | {mn} | {mx} | {tail} |".format(
                budget=row["budget_tokens"],
                n=row["window_count"],
                mn=row["token_estimates"]["min"],
                mx=row["token_estimates"]["max"],
                tail=row["tiny_tail_src_count"],
            )
        )

    v2_lines = [
        "| target | hard max | windows | min | max | owned once | hard-max viol | tail ratio |",
        "| ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for row in v2_rows:
        v2_lines.append(
            "| {t} | {h} | {n} | {mn} | {mx} | {own} | {viol} | {tail:.3f} |".format(
                t=row["target_input_tokens"],
                h=row["hard_max_input_tokens"],
                n=row["window_count"],
                mn=row["token_estimates"]["min"],
                mx=row["token_estimates"]["max"],
                own=_yn(row["all_present_owned_exactly_once"]),
                viol=_yn(row["any_hard_max_violation"]),
                tail=row["tail_ratio"],
            )
        )

    scenario_lines = [
        "| scenario | records/window | tok/record | estimated consolidation input |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in scenarios:
        scenario_lines.append(
            "| {name} | {rec} | {tok} | {est} |".format(
                name=row["name"],
                rec=row["assumed_records_per_window"],
                tok=row["assumed_tokens_per_record"],
                est=row["estimated_consolidation_input_tokens"],
            )
        )

    return f"""# PHASE 3B.7 — HYBRID WINDOW PLUS GLOBAL CONSOLIDATION DESIGN

## Result

PASS

HYBRID ARCHITECTURE DESIGN =
PASS

WINDOW PLANNER V2 POLICY =
{PLANNER_VERSION} / target {TARGET_INPUT_TOKENS} / hard max {HARD_MAX_INPUT_TOKENS} / {OVERLAP_POLICY}

TARGET WINDOW INPUT =
{TARGET_INPUT_TOKENS}

HARD MAX WINDOW INPUT =
{HARD_MAX_INPUT_TOKENS}

EXPECTED WINDOWS =
{expected}

OVERLAP POLICY =
{OVERLAP_POLICY}

WINDOW TRANSPORT =
{WINDOW_TRANSPORT_VERSION}

GLOBAL CONSOLIDATION =
REQUIRED

CANONICAL SOURCEMAP CONTRACT =
{CANONICAL_SOURCEMAP_CONTRACT}

REAL PROVIDER CALLS =
0

SOURCE MAP =
NOT PUBLISHED

PHASE 3B =
{PHASE_3B_STATUS}

NEXT PHASE =
{NEXT_PHASE_LABEL}

## 1. Result

Voir l'en-tête. Design offline uniquement. Aucun Attempt #3.
Aucune implémentation de production du pipeline hybride.

## 2. Objective

Concevoir HYBRID WINDOW PLUS GLOBAL CONSOLIDATION avant toute
implémentation : contrats de fenêtres, planner V2, ownership, cache/resume,
consolidation sémantique, reconstruction canonique, échecs, tests et
sous-phases.

## 3. Baseline

`.venv\\Scripts\\python.exe -m pytest -q`

Avant travail : **{BASELINE_PASSED} passed**, {BASELINE_FAILED} failed.

Après travail : **{FINAL_PASSED} passed**, {FINAL_FAILED} failed.

## 4. 3B.6 decision

La stratégie retenue reste **HYBRID_WINDOW_PLUS_GLOBAL_CONSOLIDATION**.
Aucun concours d'architectures n'est rouvert. Aucune contradiction
fondamentale n'a été trouvée.

## 5. Constraints

OFFLINE_DESIGN_ONLY. Anthropic/OpenAI/Whisper/Ollama/LM Studio = 0.
engine.generate = 0. Prompt 1.3, Generation C, decoder, validator et
transcript CLEAN inchangés. source_map absent. État historique failed.

## 6. Existing planner audit

`plan_windows()` existe, est déterministe, coupe sur frontières SRC et
préserve les SRC sparses. Il n'est **pas** production-ready pour
l'exécution hybride.

Formule : `parts = max(2, ceil(estimated_global / budget))` puis parts
égales en nombre de SRC. Overlap défaut = 1 SRC technique. Les tokens
par fenêtre ne sont pas re-estimés dans le planner.

## 7. Existing planner pathology

{chr(10).join(current_lines)}

Cause : overlap fait avancer `start = stop - overlap`. Après N parts
égales, 2–3 SRC restent et forment une fenêtre-stub (~2975 tokens, presque
entièrement du prompt overhead). Les budgets 75k–200k forcent encore
`parts >= 2`, donc reproduisent le même motif deux grandes fenêtres +
stub. Ce n'est pas une coupe sémantique.

## 8. WindowPlannerV2 goals

Bornage d'entrée, couverture SRC complète, déterminisme, frontières
stables, préservation sparse, pas de stub pathologique, charge équilibrée,
cache/resume, localité sémantique seulement si un signal fiable existe,
aucune renumérotation SRC.

## 9. Candidate budgets

Cibles simulées : 40000, 50000, 60000, 75000.

{chr(10).join(v2_lines)}

## 10. Selected target budget

**{TARGET_INPUT_TOKENS}**.

Sur ce corpus : 3 fenêtres ~équilibrées sous 50k. 40k ajoute un 4e appel
et plus de coutures. 60k reste à 3 fenêtres mais relâche le bornage.
75k retombe vers 2 très grandes fenêtres, trop proches du problème
opérationnel global.

## 11. Selected hard max

**{HARD_MAX_INPUT_TOKENS}**.

Cible ≠ plafond. 60k laisse une marge d'estimation/rebalance sans
autoriser une fenêtre de 73k. Un SRC unique de ce corpus (~2973 tokens
prompt inclus) ne viole pas ce plafond.

## 12. Balanced partitioning

Le planner estime le contenu par SRC, calcule N = ceil(contenu /
(target − overhead)), coupe sur les préfixes les plus proches des
cibles cumulatives, puis re-mesure chaque fenêtre avec le vrai prompt.

## 13. Tiny-tail policy

Dernière fenêtre trop petite si contenu < max(2 × overhead,
0.15 × (target − overhead)). Action : fusionner dans la précédente si
le hard max le permet, sinon voler des SRC à la précédente. Sur le
corpus réel avec la politique retenue, le stub 2–3 SRC disparaît.

## 14. Boundary policy

Coupe uniquement sur frontières SRC. Jamais au milieu d'un SRC. Pas de
troncature. Un SRC unique > hard max → FAIL OVERSIZED_SRC.

## 15. Overlap options

Analysées : NO OVERLAP ; 1 SRC overlap ; overlap borné en tokens ;
contexte de frontière séparé.

## 16. Selected overlap policy

**{OVERLAP_POLICY}**.

Le 1-SRC overlap historique est trop petit pour la continuité
discursive et a créé le stub. Le consolidateur existe précisément pour
la cohérence inter-fenêtres. `context_src_refs` reste dans le contrat
(vide en v1) pour une extension ultérieure.

## 17. Ownership

Chaque SRC CLEAN a exactement une fenêtre propriétaire. Aucun SRC ne
produit deux ownerships sémantiques. Les SRC de contexte, s'ils
existaient, ne créeraient pas d'éléments substantifs.

## 18. Window IDs

`WIN001` … `WINnnn` dans l'ordre d'apparition source. L'identité de
cache n'est pas le numéro seul : `input_hash` inclut contenu et contrat.

## 19. WindowInput contract

Champs : window_id, transcript_id, planner_version, owned_src_refs,
context_src_refs, first/last owned SRC, estimated tokens, hashes.
Aucun timestamp dans le contrat canonique.

## 20. Window prompt

Nouveau prompt versionné **window-analysis-1.0**. Prompt 1.3 n'est pas
modifié et reste le prompt global historique.

## 21. Generation C reuse

**YES.** `semantic-transport-v1` suffit pour extraire les records d'une
fenêtre. Generation D n'est pas nécessaire. theme/intent/aud/voice
deviennent des candidats, pas la vérité globale.

## 22. Window semantic output

Records TOPIC/IDEA/EXAMPLE/REFERENCE/UNCERTAINTY/REPETITION/RELATION/VOICE
avec vrais SRC. Relations `l[]` = index locaux, remappés vers WIN:R.
Pas de structure de livre.

## 23. Window validation

Schéma, version de transport, identité, SRC autorisés, owned/context,
vocabulaire contrôlé, liens locaux, fuite éditoriale. Fail-closed.

## 24. Window completeness

Ne pas réutiliser la règle globale « une source substantielle doit avoir
au moins une idée » par fenêtre. Une fenêtre peut n'avoir ni exemple ni
référence. Interdit de forcer l'hallucination.

## 25. Window record identity

Identité intermédiaire `WIN001:R0001`. Les IDs finaux restent TOP / IDEA
/ EX / REF / UNC / REP.

## 26. Window artifact layout

Production future : `analysis/hybrid/windows/WIN00N/{{input,transport,result}}.json`.
Audit : `audit/`. Publication : `analysis/source_map.json` seulement.

## 27. Window cache

Une entrée par fenêtre. Un échec n'invalide pas les autres fenêtres
sauf changement de contrat partagé.

## 28. Window signature

Transcript SHA, planner, window id, hashes owned/context, prompt
fenêtre, schéma, provider/model, température, max output, langue.

## 29. Resume

Plan déterministe → signatures → charger/valider le cache → n'exécuter
que le manquant → exiger toutes les fenêtres valides → consolidation.

## 30. Window failure

Persister les succès. États WINDOW_PENDING / SUCCESS / FAILED. Retry
non autorisé automatiquement.

## 31. Sequential execution

V1 **SEQUENTIAL**. Coût, garde d'appel, debug, rate-limit, déterminisme
opérationnel. Parallélisme possible plus tard, pas maintenant.

## 32. Consolidation input

Représentation compacte des records validés. **Pas** le transcript
intégral. Pas de recopies SRC brutes.

## 33. Consolidation size scenarios

SCENARIO ONLY — les sorties fenêtre n'existent pas.

{chr(10).join(scenario_lines)}

Budget sûr = {CONSOLIDATION_SAFE_INPUT_TOKENS}. Dense (90000) dépasse :
échec explicite, pas de troncature.

## 34. Consolidation semantic responsibilities

Thème/intent/audience/voix globaux ; équivalence topics/ideas ;
relations et exemples inter-fenêtres ; répétitions globales ;
fragmentation de frontière.

## 35. Local responsibilities

Validation, lookup, union SRC, application des merges, IDs canoniques,
ordre, stats, coverage, schéma, sérialisation, publication atomique.

## 36. Consolidation transport

**consolidation-transport-v1**. Generation C n'est pas réutilisé
directement. Le provider ne renvoie pas le SourceMap canonique.
Opérations : GLOBAL_METADATA, KEEP_RECORD, MERGE_RECORDS, RELATION,
REPETITION. DROP interdit en v1.

## 37. Global metadata

Décidés seulement en consolidation. Les thèmes/intent/audience/voix
fenêtre sont des preuves.

## 38. Topics

Candidats locaux avec SRC. IDs TOP assignés localement après merge/keep.

## 39. Ideas

Candidats avec SRC. Python ne fusionne pas les paraphrases.

## 40. Examples

Gardent SRC et lien de support. Un exemple W2 peut soutenir une idée W1
via le consolidateur.

## 41. References

Ancrées source. Keep individuel en v1. Dédup structurale exacte seulement
si sûre.

## 42. Uncertainties

Keep individuel. Incertitude de frontière distinguable ; le consolidateur
peut la résoudre s'il a les deux côtés.

## 43. Repetitions

In-window : Window Analyzer. Inter-fenêtres distantes : consolidateur.
Une idée répétée ne disparaît pas : elle devient REP.

## 44. Relations

Les index locaux ne sont jamais l'identité globale. Remap WIN:R puis
IDEA canoniques.

## 45. Cross-window references

Relation(W1:R4, W3:R7) dans le transport de consolidation. Le
reconstructeur résout les identités.

## 46. Merge semantics

MERGE_RECORDS cite des WIN:R existants. Texte synthétisé grounded.
source_refs finaux = union structurelle des SRC des records cités.

## 47. Traceability

Élément final → décision de consolidation → records fenêtre → SRC réels
→ transcript CLEAN.

## 48. Source refs

Tout élément substantiel final a de vrais SRC. WIN:R ne suffit pas.

## 49. Completeness

Couverture finale contre CLEAN_SOURCE_SET. Pas de numérotation SRC
continue inventée. Toutes les fenêtres doivent réussir.

## 50. Consolidation validation

Références existantes, types compatibles, vocabulaire, grounding,
aucune fuite éditoriale. Fail-closed.

## 51. Fail-closed behavior

Pas de table de synonymes. Pas de correction floue d'ID. Pas de
références devinées.

## 52. Canonical reconstruction

Après consolidation : reconstruction locale → normalize_source_map() →
validator → fuite éditoriale → sérialisation déterministe → publication
atomique.

## 53. Canonical validator

**{CANONICAL_VALIDATOR}.** Aucun changement proposé.

## 54. Final SourceMap compatibility

`analysis/source_map.json` reste indistinguable au contrat canonique
d'un résultat global valide. Phase 4 n'a pas besoin de savoir que
l'origine est hybride.

## 55. Hybrid signature

Doit inclure strategy=hybrid, planner, prompts fenêtre/consolidation et
hashes de toutes les fenêtres. Collision avec le cache global interdite.

## 56. Consolidation cache

Hash de toutes les sorties fenêtre validées dans l'ordre source + prompt
et transport de consolidation + modèle. Toute fenêtre changée invalide
la consolidation.

## 57. Crash recovery

Appel fenêtre : WINDOW_FAILED, les autres restent. Transport persisté
avant decode. Consolidation séparée. source_map jamais partiel.

## 58. Atomic writes

Tous les artefacts importants : `.partial` → replace.

## 59. Usage

Usage réel par fenêtre et consolidation. Unknown reste unknown. Jamais
inférer zéro.

## 60. Cost

Stages `{architecture["cost"]["window_stage"]}` et
`{architecture["cost"]["consolidation_stage"]}`, agrégés en
`{architecture["cost"]["aggregate_stage"]}`. Coûts partiels conservés.

## 61. Reporting

report.json futur : strategy=hybrid, compteurs fenêtres, statut
consolidation, usage/coût agrégés, publication. Non implémenté.

## 62. Golden fixtures

Deux fenêtres même topic / même idée / idées distinctes proches /
relation inter-fenêtres / exemple W2→idée W1 / répétition globale /
incertitude de frontière / référence unique / voix globale / ref
invalide / merge de types incompatibles / claim non grounded.

## 63. Equivalence testing

Petit corpus synthétique analysable en global-fixture et hybrid-fixture.
Équivalence sémantique/canonique attendue. Pas d'égalité octet avec un
SourceMap global historique (il n'existe pas).

## 64. Planner V2 simulation

SHA simulation = `{simulation.get("determinism", {}).get("run1_sha256", "")}`

Transcript {transcript["transcript_id"]} : {transcript["segments"]} SRC,
{transcript["words"]} mots, {transcript["duration_seconds"]} s.
Estimate globale {global_est["estimated_input_tokens"]} ;
overhead {global_est["prompt_overhead_tokens"]} ;
contenu {global_est["content_tokens_sum"]}.

## 65. Current corpus expected windows

{expected} fenêtres.

{_window_table(selected["windows"])}

## 66. Expected future call count

{expected} window calls + 1 consolidation = **{calls}**. Aucun maintenant.

## 67. Implementation sequence

3B.7.1 WindowPlannerV2 + contracts (offline) → 3B.7.2 window FakeAI →
3B.7.3 cache/resume → 3B.7.4 consolidation transport → 3B.7.5 e2e FakeAI
→ 3B.7.6 one real window canary → 3B.7.7 remaining windows → 3B.7.8
consolidation → 3B FINAL HYBRID publication.

## 68. Real-call authorization gates

Un canary fenêtre → revue → lot borné → revue → consolidation.
1 tentative par autorisation. Pas d'autorisation maintenant.

## 69. Tests

Tests offline : planner V2, couverture SRC, ownership unique, sparse,
hard max, tiny-tail, contrats, absence de réseau, absence de source_map,
artefacts protégés, Prompt 1.3 / Generation C inchangés.

## 70. Network

Anthropic = 0
OpenAI = 0
Whisper = 0
Ollama = 0
LM Studio = 0
other = 0
engine.generate = 0

## 71. Protected artifacts

Historique jusqu'à 3B.6 : snapshot SHA avant/après, byte-identical.
Prompt 1.3, Generation C, decoder, validator, transcript CLEAN
inchangés.

## 72. SourceMap status

analysis/source_map.json = ABSENT
published = false

## 73. Project state

source_analysis.status reste failed / AITimeoutError.
SUCCESS interdit.

## 74. Files added

- `app/source_analysis_hybrid_design/`
- `app/tests/test_source_analysis_hybrid_design.py`
- `audit/source_analysis_hybrid_window_design.json`
- `audit/source_analysis_hybrid_consolidation_design.json`
- `audit/source_analysis_window_planner_v2_simulation.json`
- `audit/source_analysis_hybrid_architecture_design.json`
- `audit/PHASE_3B7_HYBRID_WINDOW_PLUS_GLOBAL_CONSOLIDATION_DESIGN_REPORT.md`

## 75. Files modified

Aucun artefact historique. Aucun contrat protégé. `project_state.json`
non modifié. `analyzer.py` non branché.

## 76. Technical decision

Why is hybrid being designed?
Because two global synchronous requests produced no body. Windows bound
the heavy semantic work; consolidation restores global coherence.

Is context capacity the reason?
NO.

What is the actual operational reason?
GLOBAL_SYNCHRONOUS_REQUEST_NOT_OPERATIONALLY_VIABLE.

Why is the current planner not adopted unchanged?
Equal SRC parts + forced min-2 + 1-SRC overlap create a 2–3 SRC stub
and do not balance token workload for hierarchical analysis.

What causes the tiny tail?
`start = stop - overlap` after equal parts leaves leftover SRC.

What planner policy is selected?
{PLANNER_VERSION}, balanced token partition, SRC boundaries, anti-tiny-tail.

What target input budget?
{TARGET_INPUT_TOKENS}

What hard max?
{HARD_MAX_INPUT_TOKENS}

How many windows on the real clean corpus?
{expected}

What are their estimated token sizes?
See section 65.

Are all 8298 SRC covered exactly as owned content?
{_yn(selected["all_present_owned_exactly_once"])}

Are sparse SRC IDs preserved?
{_yn(selected["sparse_ids_preserved"])}

Is overlap used?
NO owned overlap.

Why?
See section 16.

If overlap exists, how is ownership distinguished from context?
N/A for owned overlap. Contract still has empty context_src_refs.

Can any SRC produce duplicate semantic ownership?
NO.

What is WindowInput?
Deterministic per-window contract; see section 19.

Can Generation C be reused for windows?
YES.

Is Prompt 1.3 modified?
NO.

What new window prompt is proposed?
window-analysis-1.0

Which global fields are deferred to consolidation?
main_theme, author_intent, target_audience, author_voice_profile.

How are local topics represented?
Generation C TOPIC candidates with real SRC; no final TOP ids.

How are ideas represented?
Generation C IDEA candidates with real SRC.

How are window records identified?
WIN001:R0001

How are real SRC refs preserved?
Copied from validated window records; unions are structural.

Can local Python semantically merge paraphrased topics?
NO.

Why is global consolidation required?
Cross-window equivalence and global metadata are semantic decisions.

What exactly does AI decide during consolidation?
See section 34.

What exactly does local code decide?
See section 35.

What does consolidation input contain?
Compact validated window records and candidates. Not the transcript.

Does it resend the full transcript?
NO.

Does consolidation output directly reproduce canonical SourceMap?
NO.

How are merged source refs derived?
Union of referenced WIN:R SRC sets.

How are cross-window relations represented?
RELATION ops citing WIN:R identities.

How are repetitions across windows handled?
Consolidator REPETITION ops; not silent drop.

How are global theme/intent/audience/voice produced?
GLOBAL_METADATA from window evidence.

What happens if consolidation input is too large?
ConsolidationContextExceeded.

Is truncation allowed?
NO.

How does cache work per window?
One signature/entry per semantic window.

What invalidates a window cache?
Prompt/schema/planner/model/content/settings change.

What invalidates consolidation cache?
Any window result change or consolidation contract change.

Can successful windows survive another window's failure?
YES.

Can execution resume?
YES.

What is initial execution order?
SEQUENTIAL.

How many future provider calls are expected for this corpus?
{calls}

What is the staged authorization plan?
Canary → review → remaining windows → review → consolidation.

Does canonical SourceMap contract change?
NO.

Does canonical validator change?
NO.

Will Phase 4 need to know hybrid was used?
NO.

What are the next implementation subphases?
Start with {NEXT_PHASE_LABEL}.

Was any provider called?
NO.

Was source_map created?
NO.

Was state marked SUCCESS?
NO.

How many tests pass?
{FINAL_PASSED} passed, {FINAL_FAILED} failed.

Boundary signals inventoried: {boundaries["distinct_source_id_count"]} AUDIO
source_ids, {boundaries["audio_source_change_count"]} source changes,
{boundaries["long_pause_count"]} pauses ≥ {boundaries["long_pause_threshold_seconds"]}s.
Used for v1 cuts: {_yn(boundaries["used_for_v1_cuts"])}.

Provider/model remain {EXPECTED_PROVIDER}/{EXPECTED_MODEL}.
Historical Prompt {EXPECTED_PROMPT_VERSION} unchanged.

PHASE 3B REMAINS INCOMPLETE. WAIT FOR HUMAN REVIEW.
"""
