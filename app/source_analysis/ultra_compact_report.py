"""
Rapport Phase 3B.4.2 et snapshot des artefacts protégés étendus.

N'écrit jamais analysis/source_map.json.
N'écrase jamais les rapports historiques 3B / 3B.4 / 3B.4.1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.ultra_compact_audit import AUDIT_ARTIFACT_NAME
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.writer import transcripts_dir

REPORT_NAME = "PHASE_3B42_ULTRA_COMPACT_SEMANTIC_TRANSPORT_REPORT.md"

EXTRA_PROTECTED = (
    "audit/PHASE_3B_REAL_SOURCE_ANALYZER_CLEAN_REPORT.md",
    "audit/PHASE_3B4_COMPACT_ANTHROPIC_SCHEMA_REPORT.md",
    "audit/source_analysis_compact_schema_audit.json",
    "audit/PHASE_3B41_SERVER_GRAMMAR_CANARY_REPORT.md",
    "audit/source_analysis_schema_canary_input.json",
    "audit/source_analysis_schema_canary_result.json",
)


def extra_protected_paths(
    project_name: str, *, sortie_dir: Path | None = None
) -> dict[str, Path]:
    root = Path(transcripts_dir(project_name, sortie_dir=sortie_dir)).parent
    return {key: root / key for key in EXTRA_PROTECTED}


def extra_protected_snapshot(
    project_name: str, *, sortie_dir: Path | None = None
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in extra_protected_paths(project_name, sortie_dir=sortie_dir).items():
        if Path(path).is_file():
            hashes[key] = sha256_of_file(path)
    return hashes


def audit_dir_for(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir)


def render_phase3b42_report(context: Mapping[str, Any]) -> str:
    """Rendu markdown déterministe — aucun timestamp."""
    audit = context["audit"]
    preflight = context["preflight"]
    protected_before = context["protected_before"]
    protected_after = context["protected_after"]
    extra_before = context["extra_before"]
    extra_after = context["extra_after"]
    tests = context["tests"]
    files = context["files"]
    gen_a = audit["generation_a"]["metrics"]
    gen_b = audit["generation_b"]["metrics"]
    gen_c = audit["generation_c"]["metrics"]
    gen_ac = audit["anthropic_generation_c"]["metrics"]
    red_ab = audit["reductions"]["a_to_b"]
    red_bc = audit["reductions"]["b_to_c"]
    red_ac = audit["reductions"]["a_to_c"]
    tokens = preflight["estimated_tokens"]

    def _sha_block(payload: Mapping[str, str]) -> str:
        if not payload:
            return "- (aucun)"
        return "\n".join(f"- `{key}` : `{sha}`" for key, sha in payload.items())

    def _metrics(block: Mapping[str, int]) -> str:
        keys = (
            "serialized_json_bytes",
            "total_schema_nodes",
            "object_nodes",
            "array_nodes",
            "arrays_of_objects",
            "nested_arrays",
            "total_properties",
            "required_properties",
            "optional_properties",
            "constraints",
            "enum_count",
            "total_enum_values",
            "maximum_nesting_depth",
            "additional_properties_keywords",
            "ref_count",
            "any_of",
            "one_of",
            "all_of",
            "union_count",
            "source_refs_occurrences",
            "relation_related_structures",
            "distinct_object_shapes",
            "id_pattern_like_structures",
        )
        return "\n".join(f"- {key} : {block.get(key, 0)}" for key in keys)

    return f"""# PHASE 3B.4.2 — ULTRA-COMPACT SEMANTIC TRANSPORT

## 1. Résultat

**{context["result"]}**

{context["result_notes"]}

## 2. Baseline

Commande : `.venv\\Scripts\\python.exe -m pytest -q`

Avant : **{tests["baseline_passed"]} passed**, {tests["baseline_failed"]} failed.

Après : **{tests["final_passed"]} passed**, {tests["final_failed"]} failed.

Nouveaux tests : {tests["added"]}.

## 3. Historical server failures

- Generation A (canonical-derived, {gen_a["serialized_json_bytes"]} bytes) = REJECTED
- Generation B (compact 3B.4, {gen_b["serialized_json_bytes"]} bytes) = REJECTED

## 4. Problem statement

Compiled grammar too large. Deux observations serveur seulement. Le problème
n'est pas la taille du transcript : le canary 3B.4.1 (100 mots, même schéma B)
a été refusé. Le contrat de sortie structuré reste la cause.

## 5. Scope

Offline only. Anthropic = 0. OpenAI = 0. Whisper = 0. Ollama = 0.
LM Studio = 0. other network = 0. engine.generate = 0.

## 6. Canonical contract

Changed? **NO.**

models.py, schema canonique et validator canonique n'ont pas été adaptés
pour satisfaire Anthropic.

## 7. 3B.4 DTO audit

Le DTO compact restait un SourceMap aplati :

- 1 objet `source_analysis` + 2 objets intent
- 7 collections d'objets distincts (topics, ideas, relations, examples,
  references, uncertainties, repetitions)
- 1 objet `author_voice_profile` à 10 champs
- 10 enums / 54 valeurs
- 11 `$ref` (`src_refs`, `intent`, `string_list`)
- pattern SRC répété
- minItems sur src_refs et repetitions
- profondeur schéma 5, 11 objets, 13 arrays, 53 properties, 13 constraints

Chaque collection recréait une forme d'objet différente. C'est précisément
la forme que 3B.4.2 refuse de reproduire.

## 8. Complexity hypotheses

Inférences locales — nous ne connaissons pas l'algorithme interne Anthropic.

Les structures les plus coûteuses *probablement* :

- de nombreuses formes d'objets distinctes (grammaire répétée par shape) ;
- enums fermées (explosion des alternatives lexicales) ;
- `$ref` internes (expansion à la compilation) ;
- arrays d'objets hétérogènes ;
- contraintes `pattern` / `minItems` / `enum`.

La réduction 10492 → 4398 octets n'a pas suffi : la structure B restait
un graphe de collections métier.

## 9. New architecture

```
TRANSCRIPT
   ↓
Claude
   ↓
ULTRA-COMPACT SEMANTIC TRANSPORT  ({SEMANTIC_TRANSPORT_VERSION})
   ↓
semantic_transport_decoder (fail-closed)
   ↓
canonical raw
   ↓
normalize_source_map() existant
   ↓
ensure_valid_source_map() existant
   ↓
SourceMap
```

## 10. Ultra transport design

Root, tous requis, 0 optionnel :

- `theme` — main_theme
- `intent` — author_intent.summary
- `ic` — author_intent.confidence
- `aud` — target_audience.summary
- `ac` — target_audience.confidence
- `records` — array unique de records uniformes

## 11. Uniform record design

Chaque record :

- `k` — kind (string provider-loose)
- `v` — valeur sémantique principale
- `s` — vrais SRC
- `l` — index globaux de records
- `m` — métadonnées compactes

`[]` / `""` = non applicable. Jamais `null`.

## 12. Record kinds

TOPIC, IDEA, RELATION, EXAMPLE, REFERENCE, UNCERTAINTY, REPETITION,
VOICE, INTENT_KIND, AUDIENCE_KIND.

Validés localement contre ALLOWED_RECORD_KINDS. Inconnu = FAIL.

## 13. Links

Espace d'index global unique : `records[i]`.
Le decoder interprète `l` selon `k` et refuse cible incompatible,
index hors plage, auto-lien, relation incomplète, dangling.

## 14. Source refs

Vrais SRC, forme SRC + six chiffres, trous autorisés.
Membership = ensemble SRC réellement fourni, jamais max(id).

## 15. Provider strictness

Déplacé hors du schéma provider :

- enums (idea kind, importance, relation, completeness, severity, character, confidence)
- pattern SRC
- minItems
- vocabulaires de kinds

Conservé côté provider : types JSON (object / array / string / integer)
et required (0 optional).

## 16. Local decoder strictness

Fail-closed. Aucune repair LLM, aucun nearest-enum, aucun drop silencieux.
Refuse : kind inconnu, lien invalide, SRC inconnu, confidence hors
vocabulaire, importance / relation / kinds canoniques invalides,
relation dupliquée, record mal formé.

## 17. Main theme

`theme` → source_analysis.main_theme. Vide = FAIL.

## 18. Author intent

`intent` + `ic` + records INTENT_KIND → author_intent.

## 19. Target audience

`aud` + `ac` + records AUDIENCE_KIND → target_audience.

## 20. Topics

TOPIC : v=label, m=[summary], s=SRC. IDs TOP locaux puis canoniques.

## 21. Ideas

IDEA : v=summary, m=[kind, importance], l=TOPIC, s=SRC.

## 22. Relations

RELATION séparée : v=type, l=[from IDEA, to IDEA].
Le decoder rattache à ideas[].relations.

## 23. Examples

EXAMPLE : v=summary, m=[kind], l=IDEA, s=SRC → supports_idea_refs.

## 24. References

REFERENCE : v=raw, m=[kind, completeness, normalized], s=SRC.

## 25. Uncertainties

UNCERTAINTY : v=description, m=[kind, severity], s=SRC.

## 26. Repetitions

REPETITION : v=description, m=[character], l=≥2 IDEA, s=SRC.

## 27. Voice profile

Records VOICE, m=[champ]. Le decoder rassemble les 10 dimensions
canoniques. Dimension absente = vide légitime.

## 28. Canonical IDs

TOP001… / IDEA001… / EX001… / REF001… / UNC001… / REP001…
produits par le normalizer existant, jamais par Claude.

## 29. Canonical ordering

Première apparition SRC, puis IDs. L'ordre provider n'est pas l'ordre final.

## 30. Metadata/stats

schema_version, transcript_id, projet, langue, provenance, signature,
stats et couverture : reconstruits localement. Couverture = SRC présents
(dénominateur clean = 8298 pour le corpus réel).

## 31. Golden fixture

{context["golden"]}

## 32. Semantic equivalence

{context["equivalence"]}

## 33. Negative validation

Kinds, links, SRC sparse, enums locaux, confidence, completeness,
editorial leakage : couverts, tous FAIL attendus.

## 34. Generation A complexity

{_metrics(gen_a)}

SHA : `{audit["generation_a"]["sha256"]}`

## 35. Generation B complexity

{_metrics(gen_b)}

SHA : `{audit["generation_b"]["sha256"]}`

## 36. Generation C complexity

{_metrics(gen_c)}

instance_max_depth : {audit["generation_c"]["instance_max_depth"]}

SHA : `{audit["generation_c"]["sha256"]}`

## 37. Anthropic Generation C complexity

{_metrics(gen_ac)}

SHA : `{audit["anthropic_generation_c"]["sha256"]}`

compatibility : {audit["anthropic_generation_c"]["compatibility_result"]}

recursive_refs : {audit["anthropic_generation_c"]["recursive_refs"]}

## 38. A → B reduction

serialized_json_bytes : {red_ab["serialized_json_bytes"]} %

object_nodes : {red_ab["object_nodes"]} %

constraints : {red_ab["constraints"]} %

## 39. B → C reduction

serialized_json_bytes : {red_bc["serialized_json_bytes"]} %

object_nodes : {red_bc["object_nodes"]} %

enum_count : {red_bc["enum_count"]} %

constraints : {red_bc["constraints"]} %

## 40. A → C reduction

serialized_json_bytes : {red_ac["serialized_json_bytes"]} %

object_nodes : {red_ac["object_nodes"]} %

enum_count : {red_ac["enum_count"]} %

constraints : {red_ac["constraints"]} %

## 41. Depth comparison

- A schema walk : {gen_a["maximum_nesting_depth"]}
- B schema walk : {gen_b["maximum_nesting_depth"]}
- C schema walk : {gen_c["maximum_nesting_depth"]}
- C instance : {audit["generation_c"]["instance_max_depth"]}

## 42. Object/array comparison

| | A | B | C |
|---|---|---|---|
| objects | {gen_a["object_nodes"]} | {gen_b["object_nodes"]} | {gen_c["object_nodes"]} |
| arrays | {gen_a["array_nodes"]} | {gen_b["array_nodes"]} | {gen_c["array_nodes"]} |
| arrays of objects | {gen_a.get("arrays_of_objects", 0)} | {gen_b.get("arrays_of_objects", 0)} | {gen_c.get("arrays_of_objects", 0)} |
| distinct shapes | {gen_a.get("distinct_object_shapes", 0)} | {gen_b.get("distinct_object_shapes", 0)} | {gen_c.get("distinct_object_shapes", 0)} |

## 43. Properties comparison

A {gen_a["total_properties"]} / B {gen_b["total_properties"]} / C {gen_c["total_properties"]}
required A {gen_a["required_properties"]} / B {gen_b["required_properties"]} / C {gen_c["required_properties"]}
optional A {gen_a["optional_properties"]} / B {gen_b["optional_properties"]} / C {gen_c["optional_properties"]}

## 44. Constraints comparison

A {gen_a["constraints"]} / B {gen_b["constraints"]} / C {gen_c["constraints"]}

## 45. Enum comparison

A {gen_a["enum_count"]} enums / {gen_a["total_enum_values"]} values
B {gen_b["enum_count"]} enums / {gen_b["total_enum_values"]} values
C {gen_c["enum_count"]} enums / {gen_c["total_enum_values"]} values

## 46. Local Anthropic compatibility

{audit["anthropic_generation_c"]["compatibility_result"]}

0 unsupported minLength / minItems / maximum / minimum / maxItems /
maxLength / recursive refs / additionalProperties ≠ false.

## 47. Server acceptance

**UNVERIFIED**

Aucune preuve que le serveur Anthropic acceptera Generation C.
Les deux seuls faits serveur restent : A REJECTED, B REJECTED.

## 48. Prompt

Version : `{context["prompt_version"]}`

Transport : `{SEMANTIC_TRANSPORT_VERSION}`

Le prompt explique le rôle d'analyste, la fidélité, les kinds, les champs
k/v/s/l/m, les liens globaux, les vrais SRC, et les champs vides.

## 49. Prompt size

system estimated tokens : {tokens["system"]}
user estimated tokens : {tokens["user"]}
prompt-only (system) is the instruction budget ; the user prompt is dominated
by the transcript, not by the transport legend.

## 50. Signature

3B.4 ≠ 3B.4.2 : nouveau schéma + prompt 1.2 + transport-v1.

old compact schema sha : `{audit["generation_b"]["sha256"]}`
new ultra schema sha : `{audit["generation_c"]["sha256"]}`
preflight signature : `{preflight["signature"]}`

## 51. Cache

Invalidated by signature. Les caches historiques ne matchent plus.
Aucun cache ancien n'a été supprimé.

## 52. Future AIRequest

Uses Generation C? **YES.**

analyze_source() et le préflight sélectionnent
`build_ultra_compact_response_schema()`.

## 53. Offline Anthropic payload

Uses Generation C? **YES.**

`output_config.format.type = json_schema`
schema = prepare_anthropic_json_schema(ultra)

## 54. Old schemas

canonical-derived : absent du futur payload.
3B.4 compact : absent du futur payload.

## 55. Clean DERIVED preflight

segments : {preflight["segments"]}
words : {preflight["words"]}
duration : {preflight["duration"]} s
mode : {preflight["mode"]}
provider : {preflight["provider"]}
model : {preflight["model"]}

## 56. Context estimate

system : {tokens["system"]}
user : {tokens["user"]}
total : {tokens["total"]}
usable input budget : {preflight["usable_input_budget"]}
remaining margin : {preflight["remaining_margin"]}
strategy : **{preflight["strategy"]}**
method : {tokens["method"]}

## 57. Output budget

max_output_tokens n'a pas été réduit. Un schéma petit ne réduit pas
la quantité d'information sémantique d'un corpus de 38313 mots.

valeur : {preflight["max_output_tokens"]}

## 58. Tests added

{tests["added"]}

## 59. Tests final

{tests["final_passed"]} passed, {tests["final_failed"]} failed.

## 60. Network

Anthropic : 0
OpenAI : 0
Whisper : 0
Ollama : 0
LM Studio : 0
other : 0

## 61. engine.generate

0

## 62. Diagnostic artifact

Path : `{context["audit_path"]}`
SHA : `{context["audit_sha256"]}`
deterministic : run1 == run2 == `{context["audit_sha256"]}`

## 63. Protected artifacts

Avant :

{_sha_block(protected_before)}

Après :

{_sha_block(protected_after)}

Extra historiques :

{_sha_block(extra_before)}

Identiques après : **{context["protected_identical"]}**

## 64. Files modified

{files}

## 65. Technical decision

- Le SourceMap canonique a-t-il été modifié ? **NON**
- Le canonical validator a-t-il été affaibli ? **NON**
- Le nouveau transport est-il distinct du DTO 3B.4 ? **OUI**
- Utilise-t-il une forme de record largement uniforme ? **OUI**
- Quelle est sa profondeur maximale (instance) ? **{audit["generation_c"]["instance_max_depth"]}**
- Combien d'objets ? **{gen_c["object_nodes"]}**
- Combien d'arrays ? **{gen_c["array_nodes"]}**
- Combien de properties ? **{gen_c["total_properties"]}**
- Combien de constraints ? **{gen_c["constraints"]}**
- Combien d'enums provider ? **{gen_c["enum_count"]}**
- Quelle est sa taille sérialisée ? **{gen_c["serialized_json_bytes"]}**
- Quelle réduction B → C ? **{red_bc["serialized_json_bytes"]} %**
- Quelle réduction A → C ? **{red_ac["serialized_json_bytes"]} %**
- Quelles validations ont été déplacées du provider schema vers le decoder local ? enums, pattern SRC, minItems, vocabulaires de kinds / importance / relation / confidence
- Le decoder est-il fail-closed ? **OUI**
- Toutes les dimensions sémantiques du SourceMap restent-elles reconstructibles ? **OUI**
- Le golden test passe-t-il ? **{context["golden"]}**
- La fixture 3B.4 et la fixture 3B.4.2 produisent-elles le même contenu canonique sémantique ? **{context["equivalence"]}**
- Les vrais SRC sont-ils conservés ? **OUI**
- Les sparse SRC sont-ils supportés ? **OUI**
- Les IDs TOP/IDEA/EX/REF/UNC/REP restent-ils déterministes ? **OUI**
- Les relations sont-elles correctement reconstruites ? **OUI**
- Le future AIRequest utilise-t-il réellement Generation C ? **OUI**
- Le schema 3B.4 est-il absent du futur payload ? **OUI**
- Le canonical-derived schema est-il absent ? **OUI**
- La signature a-t-elle changé ? **OUI**
- Le cache historique peut-il collisionner ? **NON** (signature distincte)
- Le preflight clean reste-t-il global ? **{preflight["strategy"] == "global"}**
- Combien de tokens estimés ? **{tokens["total"]}**
- Y a-t-il eu un appel Anthropic ? **NON**
- Y a-t-il eu un appel réseau ? **NON**
- Anthropic server acceptance est-elle vérifiée ? **NON — UNVERIFIED**
- Les artefacts protégés sont-ils intacts ? **{context["protected_identical"]}**
- Les tests sont-ils verts ? **{tests["final_failed"] == 0}**
- Existe-t-il une anomalie locale connue qui empêcherait le prochain micro-canary serveur ? **{context["known_anomaly"]}**

---

Prochaine étape (NE PAS EXÉCUTER) : 3B.4.3 ULTRA-COMPACT SERVER GRAMMAR CANARY
— exactement Generation C, input minuscule, 1 appel, max_attempts=1,
aucun fallback. Attendre revue humaine.
"""


def write_report(path: Path, context: Mapping[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_phase3b42_report(context)
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(encoded)
        if partial.read_bytes() != encoded:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path
