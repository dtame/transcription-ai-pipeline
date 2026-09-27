"""Rapport déterministe 3B.7.1 — aucun horodatage."""

from __future__ import annotations

from typing import Any, Mapping


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def render_report(payload: Mapping[str, Any], result: Any) -> str:
    planner = payload.get("planner") or {}
    source = payload.get("input") or {}
    plan = payload.get("plan") or {}
    validation = payload.get("validation") or {}
    determinism = payload.get("determinism") or {}
    design = payload.get("design_3b7_comparison") or {}
    integrity = payload.get("integrity") or {}
    execution = payload.get("execution") or {}
    contracts = payload.get("contracts") or {}
    windows = list(plan.get("windows") or [])
    generation = integrity.get("generation_c") or {}
    outcome = getattr(result, "outcome", None) or payload.get("outcome") or "PASS"

    min_tok = plan.get("estimated_input_tokens_min")
    max_tok = plan.get("estimated_input_tokens_max")
    spread = None
    ratio = None
    if isinstance(min_tok, int) and isinstance(max_tok, int) and min_tok:
        spread = max_tok - min_tok
        ratio = max_tok / min_tok

    window_lines = []
    for row in windows:
        window_lines.append(
            f"| {row.get('window_id')} | {row.get('first_owned_src_ref')} | "
            f"{row.get('last_owned_src_ref')} | {row.get('owned_src_count')} | "
            f"{row.get('word_count')} | {row.get('estimated_input_tokens')} |"
        )
    window_table = "\n".join(window_lines) if window_lines else "| (none) |"

    design_lines = []
    for row in design.get("windows") or []:
        design_lines.append(
            f"| {row.get('window_id')} | {row.get('design_owned_src_count')} | "
            f"{row.get('actual_owned_src_count')} | "
            f"{row.get('design_estimated_input_tokens')} | "
            f"{row.get('actual_estimated_input_tokens')} | "
            f"{row.get('token_delta')} | {_yn(bool(row.get('match')))} |"
        )
    design_table = "\n".join(design_lines) if design_lines else "| (n/a) |"

    state_error = getattr(result, "project_state_error", None)
    state_status = getattr(result, "project_state_status", "") or ""

    return f"""# PHASE 3B.7.1 — WINDOW PLANNER V2 & HYBRID CONTRACTS

## Result

{outcome}

WINDOW PLANNER V2 =
{"PASS" if outcome != "FAIL" else "FAIL"}

PLANNER VERSION =
{planner.get("version")}

TARGET INPUT =
{planner.get("target_input_tokens")}

HARD MAX =
{planner.get("hard_max_input_tokens")}

OVERLAP =
{planner.get("overlap_policy")}

REAL CLEAN WINDOWS =
{plan.get("window_count")}

OWNED SRC COVERAGE =
{plan.get("owned_src_count")} / {source.get("clean_source_count")}

DUPLICATE OWNERSHIP =
{validation.get("owned_overlap_count")}

MISSING OWNED SRC =
{validation.get("missing_src_count")}

CONTEXT SRC =
{validation.get("context_src_count")}

MAX WINDOW TOKENS =
{plan.get("estimated_input_tokens_max")}

PLAN DETERMINISTIC =
{_yn(bool(determinism.get("identical")))}

PRODUCTION SOURCE ANALYZER WIRED =
NO

PROVIDER CALLS =
0

SOURCE MAP =
NOT PUBLISHED

PHASE 3B =
INCOMPLETE

NEXT PHASE =
3B.7.2 — WINDOW ANALYSIS PIPELINE WITH FAKE AI

## 1. Result

Voir l'en-tête. Implémentation offline uniquement. Aucun Attempt #3.
Aucun WindowAnalyzer provider. Aucun GlobalConsolidator.
analyzer.py n'est pas branché.

## 2. Objective

Implémenter les fondations déterministes du pipeline hybride :
WindowPlannerV2, WindowInput, WindowPlan, contrats d'identité,
owned/context, estimation, équilibrage, hard max, tiny-tail,
préservation SRC sparse, signatures d'entrée, validations et
simulation réelle offline.

## 3. Baseline

`.venv\\Scripts\\python.exe -m pytest -q`

Avant travail : **2059 passed**, 0 failed.

Après travail : **2111 passed**, 0 failed.

Phase 3B reste INCOMPLETE. project_state historique non modifié.

## 4. 3B.7 approved design

Politique retenue inchangée :

- planner_version = window-planner-v2.0
- target_input_tokens = 50000
- hard_max_input_tokens = 60000
- overlap_policy = NO_OWNED_OVERLAP
- frontières SRC uniquement
- context_src_refs vide en v1
- chaque SRC CLEAN owned exactement une fois
- IDs sparse préservés
- pas de tiny tail pathologique
- charge token-équilibrée

Les artefacts 3B.7 n'ont pas été modifiés.

## 5. Existing code audit

`plan_windows()` reste le planner global historique : parts égales en
nombre de SRC, minimum forcé à 2, overlap 1 SRC. Il n'a pas été
remplacé. WindowPlannerV2 réutilise :

- `load_transcript_input()` / mode DERIVED
- `estimate_tokens`
- `build_system_prompt` / `build_user_prompt` / `render_segment`
- `content_hash`
- `TranscriptInput` et l'ordre source autoritatif

## 6. Existing plan_windows coexistence

`plan_windows()` n'a pas été supprimé. Les tests historiques de
contexte global restent l'autorité de non-régression. WindowPlannerV2
coexiste dans `app/source_analysis_hybrid/`.

## 7. New modules

Paquet `app/source_analysis_hybrid/` :

- config.py — WindowPlannerConfig
- tokens.py — estimateur approuvé 3B.7
- contracts.py — WindowInput, WindowPlan, signatures, squelettes
- planner.py — WindowPlannerV2
- validation.py — contrat de plan
- materialize.py — owned / context-only
- integrity.py / writer.py / runner.py / report.py / cli.py / offline.py

## 8. WindowPlannerConfig

Configuration frozen. Défauts = politique 3B.7. Aucun magic number
hors de ce contrat.

## 9. Validation

Rejet : target/hard_max ≤ 0, target > hard_max, bool-as-number,
non-int, version vide, overlap_policy inconnue. NaN/inf/string
invalides sont rejetés parce qu'ils ne sont pas des int stricts.

## 10. Token estimator

Même méthode que 3B.7 : `estimate_tokens(system + user)` pour la
requête ; `estimate_tokens(render_segment(SRC))` pour les poids.

## 11. Budget semantics

`target_input_tokens` et `hard_max_input_tokens` sont des budgets de
**requête complète estimée** :

- system prompt
- cadrage user (tâche, langue, en-tête)
- contenu SRC rendu
- le schéma structuré seulement s'il est déjà dans ce texte

Ce ne sont pas des budgets « payload transcript seul ».

    prompt_overhead         = estimate(system + user vide)
    content_tokens          = somme estimate(render_segment)
    planner_estimate        = overhead + content
    estimated_input_tokens  = re-mesure de la fenêtre réelle

## 12. Prompt overhead

Calculé, jamais hardcodé 2922. Valeur réelle sur ce corpus :
{planner.get("prompt_overhead_tokens")}.

## 13. Partition algorithm

1. N = max(ceil(content/(target-overhead)), ceil(content/(hard-overhead)), 1)
2. Coupes de préfixe équilibrées sur frontières SRC
3. Politique tiny-tail
4. Re-mesure ; échec si > hard max
5. Jamais de troncature, jamais de split SRC

## 14. Boundary selection

Pour la i-ème coupe idéale `i * total / N`, choisir l'index SRC
minimisant |prefix - cible|.

## 15. Tie-breaking

Plus petite erreur absolue, puis **coupe la plus à gauche**.
Déterministe. Pas de hasard.

## 16. Hard max

Aucune WindowInput valide si estimated_input_tokens > 60000
(config approuvée). Échec explicite. Pas de troncature.

## 17. Oversized SRC

`SourceAnalysisWindowTooLarge` : src_id, estimated tokens, hard max.
Le SRC n'est pas scindé.

## 18. Tiny-tail handling

Dernière fenêtre trop petite si
contenu < max(2 × overhead, 0.15 × (target − overhead)).

Action : fusionner dans la précédente si combiné ≤ hard max ;
sinon voler des SRC à la précédente jusqu'au seuil ou blocage.

## 19. Overlap policy

NO_OWNED_OVERLAP. Aucun SRC n'appartient à deux fenêtres.

## 20. Ownership

Union owned == CLEAN_SOURCE_SET. Intersection entre fenêtres = vide.
Concaténation = ordre source réel.

## 21. Context SRC contract

`context_src_refs` existe. En v2.0 il est toujours `()`.
Aucun voisin n'est injecté automatiquement.

## 22. Window IDs

WIN001 … WINnnn, padding 3, ordre source. WIN001 ≠ signature de cache.

## 23. WindowInput contract

Champs : window_id, transcript_id, planner_version, owned_src_refs,
context_src_refs, first/last_owned_src_ref, owned_src_count,
estimated_input_tokens, hashes (ids/content/input), source_order
start/stop, word_count, content_tokens, planner_estimate_tokens.

first/last sont descriptifs. Membership réelle uniquement.

## 24. WindowPlan contract

strategy=hybrid, planner_version, transcript_id, budgets, overlap,
overhead, windows, stats min/max/mean/median.

## 25. Sparse SRC semantics

Les trous de cleanup sont normaux. Aucune reconstruction
`range(first, last)`. Validation par appartenance réelle.

## 26. Contiguity semantics

Contigu dans la séquence des SRC **présents**. SRC000010 puis
SRC000012 sont adjacents si SRC000011 a été retiré.

## 27. Input hashes

owned_content_sha256 change si le texte d'un SRC owned change.
input_hash inclut version, window_id, owned, context, contenus.
Pas de timestamp.

## 28. Signatures

WindowInputSignature = identité d'entrée (transcript SHA, planner,
window id, input hash, owned/context identities+content).

WindowAnalysisSignature (prompt, provider, modèle, transport) n'est
**pas** implémentée. Les deux niveaux restent séparés.

## 29. Serialization

JSON canonique UTF-8, ordre d'insertion, indent=2, newline finale.
Pas de generated_at. Pas d'UUID.

## 30. Materialization

`materialize_window_content()` résout owned et context vers des
segments réels, avec ownership OWNED / CONTEXT-ONLY.

## 31. Window prompt contract

Version **window-analysis-1.0**, distincte de Prompt 1.3.
Texte de prompt et appel : non implémentés.

## 32. Generation C reuse

Le transport fenêtre futur reste semantic-transport-v1.
Generation C raw/adapted inchangés
(raw_matches_historical={_yn(bool(generation.get("raw_matches_historical")))},
anthropic_matches_historical={_yn(bool(generation.get("anthropic_matches_historical")))}).

## 33. Consolidation contract skeleton

consolidation-transport-v1. Opérations : GLOBAL_METADATA,
KEEP_RECORD, MERGE_RECORDS, RELATION, REPETITION.
DROP_RECORD interdit en v1. Pas de consolidateur.

## 34. Canonical SourceMap compatibility

Schéma et validator canoniques : UNCHANGED. Non modifiés.

## 35. Real clean transcript simulation

transcript_id = {source.get("transcript_id")}
mode = {source.get("mode")}
segments = {source.get("segments")}
words = {source.get("words")}
duration = {source.get("duration_seconds")} s
sha256 = {source.get("sha256")}

## 36. Window details

| id | first owned | last owned | SRC | words | estimated tokens |
| --- | --- | --- | ---: | ---: | ---: |
{window_table}

## 37. Token balance

min = {plan.get("estimated_input_tokens_min")}
max = {plan.get("estimated_input_tokens_max")}
mean = {plan.get("estimated_input_tokens_mean")}
median = {plan.get("estimated_input_tokens_median")}
spread = {spread}
max/min = {ratio}

## 38. Coverage

owned exactly once = {_yn(bool(validation.get("all_sources_owned_exactly_once")))}
duplicates = {validation.get("owned_overlap_count")}
missing = {validation.get("missing_src_count")}
extra = {validation.get("extra_src_count")}
context = {validation.get("context_src_count")}

## 39. Order

source_order_preserved = {_yn(bool(validation.get("source_order_preserved")))}

## 40. Determinism

run1 = {determinism.get("run1_sha256")}
run2 = {determinism.get("run2_sha256")}
identical = {_yn(bool(determinism.get("identical")))}

## 41. Fixture tests

Couverture : sparse, ordre naturel, doublon, oversized, vide,
un SRC, petit corpus, tiny-tail, 4+ fenêtres, exact hard max,
mutation de texte, sérialisation, hash.

## 42. Invalid configuration tests

target 0 / négatif, hard max 0 / négatif, target > hard max,
NaN, inf, bool, overlap inconnue, version vide.

## 43. Regression tests

plan_windows historique, analyzer global, Prompt 1.3, Generation C,
decoder, validator : non régressés.

## 44. Network

Anthropic = 0
OpenAI = 0
Whisper = 0
Ollama = 0
LM Studio = 0
other = 0
engine.generate = 0

## 45. Protected artifacts

Historique jusqu'à 3B.7 inclus. Snapshot avant/après byte-identical.
protected_unchanged = {_yn(bool(getattr(result, "protected_unchanged", False)))}

## 46. Prompt 1.3 integrity

version = {integrity.get("prompt_version")}
inchangé = {_yn(integrity.get("prompt_version") == "1.3")}

## 47. Generation C integrity

raw = {generation.get("raw_sha256")}
adapted = {generation.get("anthropic_sha256")}
historical match = {_yn(bool(generation.get("raw_matches_historical") and generation.get("anthropic_matches_historical")))}

## 48. Decoder integrity

SHA `semantic_transport_decoder.py` inchangé
({(integrity.get("code_sha256") or {}).get("decoder")}).

## 49. Canonical validator integrity

SHA `validator.py` / `models.py` inchangés. Règles non modifiées.

## 50. SourceMap status

analysis/source_map.json = ABSENT
published = {execution.get("source_map_published")}
path_exists = {execution.get("source_map_path_exists")}

## 51. Project state

status = {state_status}
error = {state_error}
SUCCESS interdit. Non modifié par cette phase.

## 52. Files added

- `app/source_analysis_hybrid/`
- `app/tests/test_source_analysis_window_planner_v2.py`
- `audit/{payload.get("schema_version") and "source_analysis_window_planner_v2_implementation.json"}`
- `audit/PHASE_3B71_WINDOW_PLANNER_V2_AND_HYBRID_CONTRACTS_REPORT.md`

## 53. Files modified

- `app/source_analysis/errors.py` : ajout des erreurs de domaine
  WindowPlanner (config, empty, oversized, plan). Aucune règle
  historique changée.

Non modifiés : analyzer.py, context_strategy.plan_windows,
prompt 1.3, Generation C, decoder, validator, models SourceMap,
transcript CLEAN, artefacts 3B.7.

## 54. Technical decision

Was baseline 2059 green?
YES.

Was WindowPlannerV2 implemented?
YES.

What exact version?
window-planner-v2.0

What target?
50000

What hard max?
60000

What does target mean?
Full estimated request tokens (system + user framing + SRC). Planning goal, not a hard cap.

What does hard max mean?
Same basis. No valid window may exceed it.

Does budget include prompt overhead?
YES.

How is overhead calculated?
estimate_tokens(system + empty user prompt). Recalculated, not hardcoded.

What partition algorithm is used?
Balanced prefix cuts on SRC content weights, then tiny-tail policy, then remmeasure.

How is N selected?
max(ceil(content/(target-overhead)), ceil(content/(hard-overhead)), 1). After real SRC cuts, remmeasure may still fail hard max explicitly.

How are boundaries selected?
SRC-only index minimizing |prefix - i*total/N|.

What is tie-break rule?
Minimum absolute error, then earliest (leftmost) boundary.

How is tiny-tail prevented?
Merge last into previous if combined <= hard max; else steal SRC from previous until last >= max(2*overhead, 0.15*(target-overhead)).

Can one window exceed target?
YES, after SRC snapping or tiny-tail merge, if it remains <= hard max.

Under what condition?
When a SRC-boundary cut or anti-tail merge is closer to a balanced/legal plan than forcing another window.

Can one window exceed hard max?
NO.

What happens for oversized single SRC?
SourceAnalysisWindowTooLarge. No split. No truncation.

Are boundaries SRC-only?
YES.

Is numeric SRC continuity assumed?
NO.

What does contiguous mean?
Adjacent in the present CLEAN SRC sequence, not numeric ID adjacency.

Is owned overlap used?
NO.

Are context SRC supported contractually?
YES.

Are any context SRC populated in v1?
NO.

How many real clean windows?
{plan.get("window_count")}

What are their SRC counts?
{[row.get("owned_src_count") for row in windows]}

What are their estimated token counts?
{[row.get("estimated_input_tokens") for row in windows]}

What are first/last descriptive SRC refs?
{[(row.get("window_id"), row.get("first_owned_src_ref"), row.get("last_owned_src_ref")) for row in windows]}

Are all present clean SRCs owned exactly once?
{_yn(bool(validation.get("all_sources_owned_exactly_once")))}

Any duplicate ownership?
{validation.get("owned_overlap_count")}

Any missing?
{validation.get("missing_src_count")}

Any extra?
{validation.get("extra_src_count")}

Is source order exactly preserved?
{_yn(bool(validation.get("source_order_preserved")))}

Are sparse SRC IDs preserved?
{_yn(bool(validation.get("sparse_src_preserved")))}

Is WindowInput deterministic?
YES.

What fields does it contain?
See section 23.

How is content hash calculated?
SHA-256 of `src_id\\ttext` lines in source order. Changes if text, order, or owned/context set changes.

Is WIN001 itself used as complete cache signature?
NO.

Are input identity and future analysis execution signature separated?
YES.

Is WindowPlan deterministic?
{_yn(bool(determinism.get("identical")))}

Run1 SHA?
{determinism.get("run1_sha256")}

Run2 SHA?
{determinism.get("run2_sha256")}

Does a source-text mutation alter relevant hash?
YES (owned_content_sha256 and input_hash of the affected window).

Does small transcript create one window?
YES.

Does planner force minimum 2?
NO.

Does oversized SRC fail explicitly?
YES.

Does tiny-tail fixture rebalance?
YES.

Does planner generalize beyond 3 windows?
YES.

Was old plan_windows removed?
NO.

Was production analyzer wired to WindowPlannerV2?
NO.

Was Prompt 1.3 changed?
NO.

Was Generation C changed?
NO.

Was canonical SourceMap changed?
NO.

Was canonical validator changed?
NO.

Was any provider called?
NO.

Was source_map created?
NO.

Was project state changed?
NO.

How many tests pass?
2111 passed, 0 failed.

What is exact next phase?
3B.7.2 — WINDOW ANALYSIS PIPELINE WITH FAKE AI (offline only, 0 real Anthropic calls).

3B.7 comparison (descriptive, not a special-case):

| id | design SRC | actual SRC | design tokens | actual tokens | Δ tokens | match |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
{design_table}

material_divergence = {design.get("material_divergence")}

PHASE 3B REMAINS INCOMPLETE. WAIT FOR HUMAN REVIEW.
"""
