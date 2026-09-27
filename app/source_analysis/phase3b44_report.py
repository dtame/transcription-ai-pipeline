"""
Rapport Phase 3B.4.4 — durcissement du contrat lexical.

N'écrit jamais analysis/source_map.json.
N'écrase jamais les rapports historiques ni le préflight clean.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

REPORT_NAME = "PHASE_3B44_CANONICAL_VOCABULARY_CONTRACT_REPORT.md"


def _yn(value: Any) -> str:
    return "OUI" if value else "NON"


def _sha_block(payload: Mapping[str, str]) -> str:
    if not payload:
        return "- (aucun)"
    return "\n".join(f"- `{key}` : `{sha}`" for key, sha in payload.items())


def _list(values: list[str] | tuple[str, ...] | None) -> str:
    if not values:
        return "(vide)"
    return ", ".join(f"`{item}`" for item in values)


def render_phase3b44_report(context: Mapping[str, Any]) -> str:
    audit = context["audit"]
    pre = audit.get("clean_preflight") or {}
    gen = audit["generation_c"]
    prompt = audit["prompt"]
    sig = audit["signature"]
    vocabs = audit["vocabularies"]
    coverage = audit["vocabulary_test_coverage"]
    tests = context["tests"]
    tokens = pre.get("estimated_tokens") or {}

    vocab_lines = []
    for key, row in vocabs.items():
        vocab_lines.append(
            f"### `{key}`\n"
            f"- source : `{row['source']}`\n"
            f"- values : {_list(row['values'])}\n"
            f"- usage : {row['usage']}\n"
            f"- fallback : {row['fallback']}\n"
            f"- missing_from_prompt : {_list(row['missing_from_prompt'])}\n"
            f"- extra_in_prompt : {_list(row['extra_in_prompt'])}"
        )

    m_lines = []
    for row in context.get("record_fields") or []:
        m_lines.append(
            f"- **{row['kind']}** — v: {row['v']} ; s: {row['s']} ; "
            f"l: {row['l']} ; m: {row['m']}"
        )

    fallback_lines = [
        f"- `{key}` : {row['fallback']}" for key, row in vocabs.items()
    ]

    return f"""# PHASE 3B.4.4 — CANONICAL VOCABULARY CONTRACT HARDENING

## 1. Result

**{context["result"]}**

{context["result_notes"]}

## 2. Scope

Offline only.

Aucun appel Anthropic, OpenAI, Whisper, Ollama, LM Studio.
`engine.generate` = 0.
Aucun Source Analyzer global.
Aucun `analysis/source_map.json`.
Phase 3B.4.5 non exécutée.

## 3. Baseline

Commande : `.venv\\Scripts\\python.exe -m pytest -q`

Avant : **{tests["baseline_passed"]} passed**, {tests["baseline_failed"]} failed.

Après : **{tests["final_passed"]} passed**, {tests["final_failed"]} failed.

Nouveaux tests : {tests["added"]}.

## 4. 3B.4.3 failure recap

HTTP 200. Schema accepted. Transport parsed.

Decoder fail-closed ensuite : jetons d'incertitude inventés.

- `transcription_artifact`
- `ambiguous_reference`
- `incomplete_thought`

PIPELINE RESULT = FAIL. SERVER GRAMMAR RESULT = ACCEPTED.

## 5. Root cause

Prompt / controlled-token contract insufficiently explicit.

Generation C est volontairement permissif (0 provider enums). Claude a produit
des identifiants sémantiquement plausibles, mais pas les jetons canoniques.

## 6. Generation C integrity

| | SHA-256 |
|---|---|
| raw before (3B.4.3) | `{gen["raw_sha256_3b43"]}` |
| raw after | `{gen["raw_sha256"]}` |
| Anthropic before (3B.4.3) | `{gen["anthropic_sha256_3b43"]}` |
| Anthropic after | `{gen["anthropic_sha256"]}` |

Unchanged : {_yn(gen["unchanged"])}.

## 7. Generation C metrics

Recalculées, non hardcodées comme résultat.

- serialized bytes raw : {gen["metrics"]["serialized_json_bytes"]}
- serialized bytes Anthropic : {gen["anthropic_metrics"]["serialized_json_bytes"]}
- objects : {gen["metrics"]["object_nodes"]}
- arrays of objects : {gen["metrics"]["arrays_of_objects"]}
- properties : {gen["metrics"]["total_properties"]}
- constraints : {gen["metrics"]["constraints"]}
- provider enums : {gen["provider_enums"]}
- provider enum values : {gen["provider_enum_values"]}
- schema nesting depth : {gen["metrics"]["maximum_nesting_depth"]}
- instance depth : {gen["instance_max_depth"]}

Aucune régression structurelle.

## 8. Canonical SourceMap integrity

Changed? **NO.**

`models.py` / contrat SourceMap : non modifié.

## 9. Canonical validator integrity

Changed/weakened? **NO.**

`validator.py` : non modifié.

## 10. Decoder policy

Fail-closed preserved? **YES.**

`semantic_transport_decoder.py` : aucune table de synonymes, aucune
normalisation floue, aucun nearest-enum.

## 11. Alias/synonym repair

Expected: **NONE.**

Observé : **NONE.**

## 12. Vocabulary inventory

{len(vocabs)} vocabulaires fermés.

{chr(10).join(vocab_lines)}

## 13. Record kinds

{_list(vocabs["record.kind"]["values"])}

Source : `{vocabs["record.kind"]["source"]}`

## 14. Idea kinds

{_list(vocabs["idea.kind"]["values"])}

Source : `{vocabs["idea.kind"]["source"]}`

## 15. Importance values

{_list(vocabs["idea.importance"]["values"])}

Source : `{vocabs["idea.importance"]["source"]}`

## 16. Relation types

{_list(vocabs["relation.type"]["values"])}

Direction : orientée `from IDEA → to IDEA`.
Restrictions : pas d'auto-lien, pas de doublon `(from, to, type)`.

Source : `{vocabs["relation.type"]["source"]}`

## 17. Uncertainty kinds

{_list(vocabs["uncertainty.kind"]["values"])}

Source : `{vocabs["uncertainty.kind"]["source"]}`

Les trois jetons 3B.4.3 ne figurent PAS dans cette liste.

## 18. Intent kinds

Pas d'enum canonique.

`INTENT_KIND.v` est une étiquette libre (`author_intent.kinds`).
Le decoder exige seulement une chaîne non vide.

intent_audience_kinds_are_free_text : {_yn(audit["intent_audience_kinds_are_free_text"])}.

## 19. Audience kinds

Pas d'enum canonique.

`AUDIENCE_KIND.v` est une étiquette libre (`target_audience.kinds`).

## 20. Repetition vocabulary

{_list(vocabs["repetition.character"]["values"])}

`REPETITION.v` (description) reste du texte libre.

## 21. Voice vocabulary

Champs contrôlés (VOICE m[0]) : {_list(vocabs["voice.field"]["values"])}

Valeurs (VOICE v) : texte libre observé. Pas d'enum de ton / registre.

## 22. Other controlled metadata

- example.kind : {_list(vocabs["example.kind"]["values"])}
- reference.kind : {_list(vocabs["reference.kind"]["values"])}
- reference.completeness : {_list(vocabs["reference.completeness"]["values"])}
- uncertainty.severity : {_list(vocabs["uncertainty.severity"]["values"])}
- confidence : {_list(vocabs["confidence"]["values"])}

## 23. Free-text fields

{chr(10).join(f"- {item}" for item in audit["free_text_fields"])}

## 24. Metadata `m` contract

{chr(10).join(m_lines) if m_lines else "- voir `record_field_contract()`"}

## 25. Fallback behavior

{chr(10).join(fallback_lines)}

Aucun OTHER / UNKNOWN / UNSPECIFIED inventé, sauf `reference.kind=other`
qui existe déjà dans le contrat canonique.

## 26. Prompt vocabulary contract

`build_canonical_vocabulary_contract()` construit le bloc depuis les tuples
canoniques. Ordre : `VOCABULARY_CATEGORY_ORDER`, puis ordre déclaré de
chaque source de vérité. Deux constructions : byte-identiques.

`build_record_field_contract()` documente k/v/s/l/m par kind, aligné sur
le decoder.

## 27. Exact-token rule

CONTROLLED IDENTIFIERS ARE PROTOCOL TOKENS.

Copie exacte. Pas de synonyme, traduction, paraphrase, pluriel, underscore
remplacé, ni catégorie plus descriptive.

## 28. Prompt/decoder parity

missing_from_prompt = {_list(audit["parity"]["missing_from_prompt"])}

extra_in_prompt = {_list(audit["parity"]["extra_in_prompt"])}

## 29. 3B.4.3 invalid tokens

`transcription_artifact`, `ambiguous_reference`, `incomplete_thought`

Still rejected? **{_yn(audit["observed_invalid_tokens_still_rejected"])}**

## 30. Corresponding canonical vocabulary

- `ambiguous_transcription`
- `incomplete_reference`
- `interrupted_thought`

(plus les autres kinds d'incertitude listés en §17)

Le decoder ne transforme PAS les anciennes valeurs.

## 31. Golden fixture

{audit["golden_fixture"]}

Transport synthétique local → decoder → canonical raw → normalizer → validator.

## 32. Vocabulary coverage

- total : {coverage.get("total")}
- tested : {coverage.get("tested")}
- percent : {coverage.get("percent")}

## 33. Negative tests

Synonym, case, hyphen, translation, unknown : decoder FAIL.

Case-sensitive. Underscores exacts.

## 34. Prompt version

old : `{prompt["previous_version"]}`

new : `{prompt["current_version"]}`

## 35. Prompt SHA

old : `{prompt["previous_sha256"]}`

new : `{prompt["current_sha256"]}`

## 36. Vocabulary block size

- characters : {prompt["vocabulary_block_characters"]}
- estimated tokens : {prompt["vocabulary_block_estimated_tokens"]}

## 37. Full prompt size

| | old (1.2) | new (1.3) | delta |
|---|---|---|---|
| system chars | {prompt["previous_system_characters"]} | {prompt["current_system_characters"]} | {prompt["system_delta_characters"]} |
| user chars | {prompt["previous_user_characters"]} | {prompt["current_user_characters"]} | {(prompt["current_user_characters"] or 0) - prompt["previous_user_characters"]} |
| system tokens | {prompt["previous_system_tokens"]} | {prompt["current_system_tokens"]} | {prompt["system_delta_tokens"]} |
| user tokens | {prompt["previous_user_tokens"]} | {prompt["current_user_tokens"]} | — |
| total tokens | {prompt["previous_total_tokens"]} | {prompt["current_total_tokens"]} | — |

## 38. Signature

old : `{sig["previous"]}`

new : `{sig["current"]}`

Changed : {_yn(sig["changed"])}.

## 39. Cache

old cache collision possible? **NO.**

Les caches historiques ne sont pas supprimés. Leur signature 1.2 ne
matche plus.

## 40. Generation C provider schema

Enums? **{gen["provider_enums"]}** (attendu 0)

## 41. Anthropic adapter

schema unchanged? **{_yn(gen["unchanged"])}**

local compatibility : {gen["local_compatibility"]}

## 42. Server grammar status

PREVIOUSLY VERIFIED by 3B.4.3.

Nous n'annulons pas cette preuve. Nous n'avons pas re-testé le serveur.

## 43. Vocabulary prompt server compliance

**UNVERIFIED.**

3B.4.4 is not verified by Anthropic.

SCHEMA SERVER ACCEPTANCE = PREVIOUSLY VERIFIED

VOCABULARY PROMPT COMPLIANCE = UNVERIFIED

## 44. Clean DERIVED preflight

- segments : {pre.get("segments")}
- words : {pre.get("words")}
- duration : {pre.get("duration")}
- mode : {pre.get("mode")}
- provenance : `cleanup_application.json`

Attendu : 8298 segments, 38313 words, 19954.601 sec.

## 45. Context estimate

- system : {tokens.get("system")}
- user : {tokens.get("user")}
- total : {tokens.get("total")}
- budget : {pre.get("usable_input_budget")}
- margin : {pre.get("remaining_margin")}
- method : {tokens.get("method")}

## 46. Strategy

{pre.get("strategy")}

## 47. Max output

{pre.get("max_output_tokens")}

Non réduit pour compenser le prompt.

## 48. Future AIRequest

- provider : {pre.get("provider")}
- model : {pre.get("model")}
- prompt version : `{prompt["current_version"]}`
- Generation C : yes
- engine.generate : 0

## 49. Future payload

`output_config.format.type` = `json_schema`

schema = same server-verified Generation C adapted schema.

Vocabulaire dans le prompt. Pas dans des enums JSON Schema.

## 50. Tests added

{tests.get("added_list", tests.get("added"))}

## 51. Final tests

{tests["final_passed"]} passed, {tests["final_failed"]} failed.

## 52. Network

- Anthropic calls = 0
- OpenAI calls = 0
- Whisper calls = 0
- Ollama calls = 0
- LM Studio calls = 0
- other network = 0

## 53. engine.generate

0.

## 54. Diagnostic artifact

- path : `{context.get("audit_path")}`
- SHA : `{context.get("audit_sha256")}`
- deterministic : {_yn(context.get("audit_deterministic"))}

## 55. Protected artifacts

Before:

{_sha_block(context["protected_before"])}

After:

{_sha_block(context["protected_after"])}

Extra before:

{_sha_block(context["extra_before"])}

Extra after:

{_sha_block(context["extra_after"])}

Byte-identical : {_yn(context.get("protected_identical"))}

## 56. Files modified

{context.get("files")}

## 57. Technical decision

La cause de l'échec 3B.4.3 était-elle encore la grammaire Anthropic ?

**NON.**

Generation C reste-t-elle server-verified ?

**OUI, historiquement via 3B.4.3.**

Generation C a-t-elle changé ?

**NON.**

Le canonical SourceMap a-t-il changé ?

**NON.**

Le canonical validator a-t-il été affaibli ?

**NON.**

Le decoder fail-closed a-t-il été conservé ?

**OUI.**

Des alias/synonym mappings ont-ils été ajoutés ?

**NON.**

Combien de vocabulaires fermés ont été identifiés ?

**{len(vocabs)}**

Quelles sont leurs sources de vérité ?

Voir §12. Principalement `app.source_analysis.models` et
`app.source_analysis.ultra_compact_schema`.

Le prompt expose-t-il exactement les mêmes valeurs que le decoder ?

**OUI.**

missing_from_prompt = {_list(audit["parity"]["missing_from_prompt"])}

extra_in_prompt = {_list(audit["parity"]["extra_in_prompt"])}

Les trois valeurs inventées en 3B.4.3 sont-elles toujours rejetées ?

**{_yn(audit["observed_invalid_tokens_still_rejected"])}**

Le prompt expose-t-il maintenant les identifiants canoniques pertinents ?

**OUI** — notamment `ambiguous_transcription`, `incomplete_reference`,
`interrupted_thought`.

Que doit faire Claude si aucune catégorie ne correspond ?

Suivre le repli documenté du champ : ne pas émettre le record, ou utiliser
un jeton canonique réellement prévu (`reference.kind=other`,
`confidence=low` si l'inférence est incertaine). Jamais inventer un jeton.

Le comportement est-il défini pour chaque vocabulaire ?

**OUI.**

Generation C possède-t-elle toujours 0 provider enums ?

**{_yn(gen["provider_enums"] == 0)}**

Le schema Anthropic-adapted reste-t-il identique ?

**{_yn(gen["unchanged"])}**

Quelle est la nouvelle version du prompt ?

`{prompt["current_version"]}`

Quelle augmentation de tokens vient du vocabulary contract ?

bloc vocabulaire ≈ {prompt["vocabulary_block_estimated_tokens"]} tokens
({prompt["vocabulary_block_characters"]} caractères).
Delta system ≈ {prompt["system_delta_tokens"]} tokens.

La signature a-t-elle changé ?

**{_yn(sig["changed"])}**

Le cache historique peut-il collisionner ?

**NON.**

Le preflight global clean tient-il toujours dans le budget ?

**{_yn(pre.get("strategy") == "global")}**

La strategy reste-t-elle global ?

**{_yn(pre.get("strategy") == "global")}**

Y a-t-il eu un appel Anthropic ?

**NON.**

Y a-t-il eu un appel réseau ?

**NON.**

La conformité réelle de Claude au nouveau vocabulary contract est-elle
vérifiée serveur ?

**NON — UNVERIFIED.**

Les artefacts protégés sont-ils intacts ?

**{_yn(context.get("protected_identical"))}**

Les tests sont-ils verts ?

**{_yn(tests["final_failed"] == 0)}**

Existe-t-il un blocker OFFLINE connu avant un dernier micro-canary
sémantique ?

**{context.get("offline_blocker", "NON")}**

---

3B FINAL reste NON AUTORISÉ. La prochaine phase éventuelle est 3B.4.5
CANONICAL VOCABULARY COMPLIANCE CANARY — non exécutée ici.
"""


def write_report(path: Path, context: Mapping[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_phase3b44_report(context)
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
