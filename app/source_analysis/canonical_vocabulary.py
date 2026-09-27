"""
Contrat lexical du Source Analyzer — Phase 3B.4.4.

Les vocabulaires fermés vivent déjà dans models.py et ultra_compact_schema.py.
Ce module ne les recopie pas : il les EXPOSE dans un ordre déterministe pour
le prompt, et documente le repli légitime de chaque champ.

    PROVIDER SCHEMA  = structure minimale (Generation C, 0 enums)
    PROMPT           = identifiants canoniques exacts (ce module)
    DECODER          = validation locale stricte / fail-closed
    VALIDATOR        = contrat métier final

Aucune table de synonymes. Aucune normalisation floue.
Si Claude produit un jeton absent de la liste : FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.source_analysis.models import (
    CONFIDENCE_LEVELS,
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    REPETITION_CHARACTERS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis.ultra_compact_schema import (
    ALLOWED_RECORD_KINDS,
    KIND_AUDIENCE_KIND,
    KIND_EXAMPLE,
    KIND_IDEA,
    KIND_INTENT_KIND,
    KIND_REFERENCE,
    KIND_RELATION,
    KIND_REPETITION,
    KIND_TOPIC,
    KIND_UNCERTAINTY,
    KIND_VOICE,
    RECORD_KIND_SEMANTICS,
    VOICE_FIELDS,
    VOICE_LIST_FIELDS,
    VOICE_SCALAR_FIELDS,
)

PREVIOUS_PROMPT_VERSION = "1.2"
CURRENT_PROMPT_VERSION = "1.3"

# Capturés offline sur le prompt 1.2 + transcript clean DERIVED, avant 3B.4.4.
PREVIOUS_PROMPT_SHA256 = (
    "98e841fbd9bd19e05a8b00260ffaeb8d8831e9463d5a2affa7cba28cf49ca865"
)
PREVIOUS_SIGNATURE = (
    "0bc4dc3219870c9b02366364ef3a08ab2809ad43281b5c5b4519f9d012fda2f3"
)
PREVIOUS_SYSTEM_CHARS = 4191
PREVIOUS_USER_CHARS = 562908
PREVIOUS_SYSTEM_TOKENS = 1048
PREVIOUS_USER_TOKENS = 140727
PREVIOUS_TOTAL_TOKENS = 141775

# Generation C — identique à 3B.4.3 (ne pas modifier le schéma).
GENERATION_C_RAW_SHA256_3B43 = (
    "90885d692bf56695e33f6205013a7f81d21b6b520e90b59338f43113fc17b0f9"
)
GENERATION_C_ANTHROPIC_SHA256_3B43 = (
    "5e54bc73257ee7d6c68ac74818974973bc7ece506556a8e975c56ef3ada18ae1"
)

OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS = (
    "transcription_artifact",
    "ambiguous_reference",
    "incomplete_thought",
)

# Exemples courts : jetons inventés en 3B.4.3 → identifiant canonique réel.
# Ce n'est PAS une table de réparation : le decoder refuse toujours la colonne
# WRONG. Le prompt montre seulement le jeton à copier.
EXACT_IDENTIFIER_EXAMPLES = (
    ("transcription_artifact", "ambiguous_transcription"),
    ("ambiguous_reference", "incomplete_reference"),
    ("incomplete_thought", "interrupted_thought"),
)

VOCABULARY_BLOCK_BEGIN = "CONTROLLED_VOCABULARY_BEGIN"
VOCABULARY_BLOCK_END = "CONTROLLED_VOCABULARY_END"

# Ordre fixe des catégories dans le prompt — jamais un set Python.
VOCABULARY_CATEGORY_ORDER = (
    "record.kind",
    "idea.kind",
    "idea.importance",
    "relation.type",
    "example.kind",
    "reference.kind",
    "reference.completeness",
    "uncertainty.kind",
    "uncertainty.severity",
    "repetition.character",
    "voice.field",
    "confidence",
)


@dataclass(frozen=True)
class ControlledVocabulary:
    """Un vocabulaire fermé, lu depuis sa source de vérité canonique."""

    key: str
    source: str
    values: tuple[str, ...]
    fallback: str
    usage: str
    empty_allowed: bool = False


def _vocabularies() -> dict[str, ControlledVocabulary]:
    """Construit l'inventaire depuis les tuples canoniques — ordre déclaré."""
    return {
        "record.kind": ControlledVocabulary(
            key="record.kind",
            source="app.source_analysis.ultra_compact_schema.ALLOWED_RECORD_KINDS",
            values=tuple(ALLOWED_RECORD_KINDS),
            fallback="n'émets pas le record",
            usage="records[].k",
        ),
        "idea.kind": ControlledVocabulary(
            key="idea.kind",
            source="app.source_analysis.models.IDEA_KINDS",
            values=tuple(IDEA_KINDS),
            fallback=(
                "n'émets pas l'IDEA ; si le phénomène est un doute, "
                "émets UNCERTAINTY avec un kind listé"
            ),
            usage="IDEA m[0]",
        ),
        "idea.importance": ControlledVocabulary(
            key="idea.importance",
            source="app.source_analysis.models.IMPORTANCE_LEVELS",
            values=tuple(IMPORTANCE_LEVELS),
            fallback="n'émets pas l'IDEA",
            usage="IDEA m[1] — poids DANS LA SOURCE",
        ),
        "relation.type": ControlledVocabulary(
            key="relation.type",
            source="app.source_analysis.models.RELATION_KINDS",
            values=tuple(RELATION_KINDS),
            fallback="n'émets pas la RELATION",
            usage="RELATION v — l=[from IDEA, to IDEA]",
        ),
        "example.kind": ControlledVocabulary(
            key="example.kind",
            source="app.source_analysis.models.EXAMPLE_KINDS",
            values=tuple(EXAMPLE_KINDS),
            fallback="n'émets pas l'EXAMPLE",
            usage="EXAMPLE m[0]",
        ),
        "reference.kind": ControlledVocabulary(
            key="reference.kind",
            source="app.source_analysis.models.REFERENCE_KINDS",
            values=tuple(REFERENCE_KINDS),
            fallback="other",
            usage="REFERENCE m[0]",
        ),
        "reference.completeness": ControlledVocabulary(
            key="reference.completeness",
            source="app.source_analysis.models.REFERENCE_COMPLETENESS",
            values=tuple(REFERENCE_COMPLETENESS),
            fallback=(
                "choisis le jeton qui décrit la référence TELLE QUE DITE ; "
                "si elle n'est pas locatable, vague"
            ),
            usage="REFERENCE m[1]",
        ),
        "uncertainty.kind": ControlledVocabulary(
            key="uncertainty.kind",
            source="app.source_analysis.models.UNCERTAINTY_KINDS",
            values=tuple(UNCERTAINTY_KINDS),
            fallback="n'émets pas l'UNCERTAINTY",
            usage="UNCERTAINTY m[0]",
        ),
        "uncertainty.severity": ControlledVocabulary(
            key="uncertainty.severity",
            source="app.source_analysis.models.SEVERITY_LEVELS",
            values=tuple(SEVERITY_LEVELS),
            fallback="n'émets pas l'UNCERTAINTY",
            usage="UNCERTAINTY m[1]",
        ),
        "repetition.character": ControlledVocabulary(
            key="repetition.character",
            source="app.source_analysis.models.REPETITION_CHARACTERS",
            values=tuple(REPETITION_CHARACTERS),
            fallback="n'émets pas la REPETITION",
            usage="REPETITION m[0]",
        ),
        "voice.field": ControlledVocabulary(
            key="voice.field",
            source="app.source_analysis.ultra_compact_schema.VOICE_FIELDS",
            values=tuple(VOICE_FIELDS),
            fallback="n'émets pas ce VOICE",
            usage="VOICE m[0] — le champ, pas la valeur",
        ),
        "confidence": ControlledVocabulary(
            key="confidence",
            source="app.source_analysis.models.CONFIDENCE_LEVELS",
            values=tuple(CONFIDENCE_LEVELS),
            fallback="low si l'inférence est incertaine",
            usage="ic / ac — chaînes, pas un nombre",
        ),
    }


def controlled_vocabularies() -> dict[str, ControlledVocabulary]:
    """Inventaire déterministe : ordre = VOCABULARY_CATEGORY_ORDER."""
    raw = _vocabularies()
    return {key: raw[key] for key in VOCABULARY_CATEGORY_ORDER}


def canonical_allowed_vocabulary() -> dict[str, tuple[str, ...]]:
    """Valeurs acceptées par decoder / validator / contrat canonique."""
    return {key: item.values for key, item in controlled_vocabularies().items()}


def prompt_controlled_vocabulary() -> dict[str, tuple[str, ...]]:
    """Valeurs exposées au prompt — mêmes tuples, même ordre."""
    return canonical_allowed_vocabulary()


def vocabulary_fallbacks() -> dict[str, str]:
    return {key: item.fallback for key, item in controlled_vocabularies().items()}


def vocabulary_sources() -> dict[str, str]:
    return {key: item.source for key, item in controlled_vocabularies().items()}


def free_text_fields() -> tuple[str, ...]:
    """Champs sémantiques libres — pas des jetons de protocole."""
    return (
        "theme",
        "intent",
        "aud",
        "TOPIC.v (label)",
        "TOPIC.m[0] (summary)",
        "IDEA.v (summary)",
        "EXAMPLE.v (summary)",
        "REFERENCE.v (raw_reference)",
        "REFERENCE.m[2] (normalized_reference, vide autorisé)",
        "UNCERTAINTY.v (description)",
        "REPETITION.v (description)",
        "VOICE.v (valeur observée)",
        "INTENT_KIND.v (étiquette libre author_intent.kinds)",
        "AUDIENCE_KIND.v (étiquette libre target_audience.kinds)",
    )


def intent_audience_kinds_are_free_text() -> bool:
    """Pas d'enum canonique pour author_intent.kinds / target_audience.kinds."""
    return True


def record_field_contract() -> tuple[dict[str, object], ...]:
    """
    Table k / v / s / l / m alignée sur semantic_transport_decoder.

    Ordre = ALLOWED_RECORD_KINDS. Rien n'est inventé ici.
    """
    return (
        {
            "kind": KIND_TOPIC,
            "v": "label — texte libre, non vide",
            "s": "SRC réels, non vide",
            "l": "[] obligatoire",
            "m": "m[0]=summary — texte libre, non vide",
            "m_controlled": (),
            "empty_m_allowed": False,
            "link_rule": "aucun lien",
            "src_rule": "requis",
        },
        {
            "kind": KIND_IDEA,
            "v": "summary — texte libre, non vide",
            "s": "SRC réels, non vide",
            "l": "index globaux de TOPIC (vide autorisé)",
            "m": "m[0]=idea.kind ; m[1]=idea.importance",
            "m_controlled": ("idea.kind", "idea.importance"),
            "empty_m_allowed": False,
            "link_rule": "seulement TOPIC",
            "src_rule": "requis",
        },
        {
            "kind": KIND_RELATION,
            "v": "relation.type — jeton contrôlé",
            "s": "[] obligatoire",
            "l": "[from IDEA, to IDEA] — exactement 2, distincts",
            "m": "[] obligatoire",
            "m_controlled": (),
            "empty_m_allowed": True,
            "link_rule": "seulement IDEA ; pas d'auto-lien ; pas de doublon (from,to,type)",
            "src_rule": "interdit",
        },
        {
            "kind": KIND_EXAMPLE,
            "v": "summary — texte libre, non vide",
            "s": "SRC réels, non vide",
            "l": "index globaux de IDEA (vide autorisé)",
            "m": "m[0]=example.kind",
            "m_controlled": ("example.kind",),
            "empty_m_allowed": False,
            "link_rule": "seulement IDEA",
            "src_rule": "requis",
        },
        {
            "kind": KIND_REFERENCE,
            "v": "raw_reference — texte libre, non vide",
            "s": "SRC réels, non vide",
            "l": "[] obligatoire",
            "m": "m[0]=reference.kind ; m[1]=completeness ; m[2]=normalized (texte libre, vide autorisé)",
            "m_controlled": ("reference.kind", "reference.completeness"),
            "empty_m_allowed": False,
            "link_rule": "aucun lien",
            "src_rule": "requis",
        },
        {
            "kind": KIND_UNCERTAINTY,
            "v": "description — texte libre, non vide",
            "s": "SRC réels, non vide",
            "l": "[] obligatoire",
            "m": "m[0]=uncertainty.kind ; m[1]=severity",
            "m_controlled": ("uncertainty.kind", "uncertainty.severity"),
            "empty_m_allowed": False,
            "link_rule": "aucun lien",
            "src_rule": "requis",
        },
        {
            "kind": KIND_REPETITION,
            "v": "description — texte libre, non vide",
            "s": "SRC réels, non vide",
            "l": "au moins deux index IDEA",
            "m": "m[0]=repetition.character",
            "m_controlled": ("repetition.character",),
            "empty_m_allowed": False,
            "link_rule": "seulement IDEA ; ≥ 2",
            "src_rule": "requis",
        },
        {
            "kind": KIND_VOICE,
            "v": "valeur observée — texte libre ; vide seulement si champ scalaire non observé",
            "s": "[] (pas de SRC métier)",
            "l": "[] obligatoire",
            "m": "m[0]=voice.field (jeton contrôlé). Listes="
            + ",".join(VOICE_LIST_FIELDS)
            + " ; scalaires="
            + ",".join(VOICE_SCALAR_FIELDS),
            "m_controlled": ("voice.field",),
            "empty_m_allowed": False,
            "link_rule": "aucun lien",
            "src_rule": "non requis",
        },
        {
            "kind": KIND_INTENT_KIND,
            "v": "étiquette libre author_intent.kinds — pas un enum",
            "s": "[] obligatoire",
            "l": "[] obligatoire",
            "m": "[] obligatoire",
            "m_controlled": (),
            "empty_m_allowed": True,
            "link_rule": "aucun lien",
            "src_rule": "interdit",
        },
        {
            "kind": KIND_AUDIENCE_KIND,
            "v": "étiquette libre target_audience.kinds — pas un enum",
            "s": "[] obligatoire",
            "l": "[] obligatoire",
            "m": "[] obligatoire",
            "m_controlled": (),
            "empty_m_allowed": True,
            "link_rule": "aucun lien",
            "src_rule": "interdit",
        },
    )


def build_canonical_vocabulary_contract() -> str:
    """
    Section de prompt déterministe : jetons contrôlés + règle + repli.

    Deux appels : byte-identiques. Ordre = VOCABULARY_CATEGORY_ORDER,
    puis valeurs dans l'ordre déclaré de la source de vérité.
    """
    lines: list[str] = [
        "IDENTIFIANTS CONTRÔLÉS — JETONS DE PROTOCOLE",
        "",
        "Ce ne sont pas des libellés en langue naturelle.",
        "Pour chaque champ contrôlé :",
        "- n'utilise qu'un identifiant explicitement listé ;",
        "- copie l'identifiant exactement ;",
        "- n'invente aucun synonyme ;",
        "- ne le traduis pas ;",
        "- ne le paraphrase pas ;",
        "- n'en change pas le singulier ni le pluriel ;",
        "- ne remplace pas les underscores ;",
        "- ne crée pas de catégorie plus descriptive.",
        "",
        "Si aucun identifiant listé ne convient, suis la règle de repli "
        "du champ. N'invente jamais un jeton absent de la liste "
        "(pas de catégorie de secours improvisée).",
        "",
        "Les identifiants de protocole restent des jetons exacts : "
        "ils ne se traduisent pas, même si la langue de sortie change.",
        "",
        "TEXTE LIBRE (pas un enum) :",
    ]
    for field in free_text_fields():
        lines.append(f"- {field}")

    lines.extend(
        [
            "",
            VOCABULARY_BLOCK_BEGIN,
            "",
        ]
    )

    for key, item in controlled_vocabularies().items():
        lines.append(f"{key}:")
        for value in item.values:
            lines.append(f"- {value}")
        lines.append(f"repli: {item.fallback}")
        lines.append("")

    lines.append(VOCABULARY_BLOCK_END)
    lines.extend(
        [
            "",
            "RÈGLE : un seul identifiant listé par champ contrôlé. "
            "Jamais inventé, traduit, paraphrasé, plurielisé, abrégé "
            "ou synonymisé.",
            "",
            "EXEMPLES (identifiant exact, pas une table de synonymes) :",
        ]
    )
    for wrong, valid in EXACT_IDENTIFIER_EXAMPLES:
        lines.append(f'WRONG: "{wrong}"')
        lines.append(f'VALID IDENTIFIER: "{valid}"')

    return "\n".join(lines)


def build_record_field_contract() -> str:
    """Documentation k/v/s/l/m par kind, alignée sur le decoder."""
    lines = [
        "CONTRAT DES RECORDS (k, v, s, l, m)",
        "",
        "l = index globaux 0-based dans records, cible du bon type.",
        "s = vrais SRC du transcript (SRC + six chiffres, trous autorisés).",
        "m = métadonnées positionnelles selon k. "
        "N'émets aucun identifiant métier (pas de topic_id, idea_id, "
        "example_id, reference_id, uncertainty_id, repetition_id).",
        "",
    ]
    for row in record_field_contract():
        kind = row["kind"]
        lines.append(f"{kind} ({RECORD_KIND_SEMANTICS[kind]})")
        lines.append(f"  v: {row['v']}")
        lines.append(f"  s: {row['s']}")
        lines.append(f"  l: {row['l']}")
        lines.append(f"  m: {row['m']}")
        lines.append("")

    lines.append(
        "VOICE listes : un record par élément. "
        "VOICE scalaires : un record par champ. "
        "INTENT_KIND / AUDIENCE_KIND : répéter le record pour chaque étiquette ; "
        "omettre le record si aucune étiquette utile."
    )
    return "\n".join(lines)


def extract_prompt_controlled_vocabularies(prompt: str) -> dict[str, tuple[str, ...]]:
    """
    Relit le bloc marqué du prompt.

    Sert au test de parité : ce que le prompt ANNONCE doit égaler
    ce que le decoder ACCEPTE.
    """
    start = prompt.find(VOCABULARY_BLOCK_BEGIN)
    end = prompt.find(VOCABULARY_BLOCK_END)
    if start < 0 or end < 0 or end <= start:
        return {}

    block = prompt[start + len(VOCABULARY_BLOCK_BEGIN) : end]
    extracted: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("repli:"):
            continue
        if line.endswith(":") and not line.startswith("-"):
            current = line[:-1]
            extracted.setdefault(current, [])
            continue
        if line.startswith("- ") and current is not None:
            extracted[current].append(line[2:])

    return {key: tuple(values) for key, values in extracted.items()}


def prompt_decoder_parity() -> dict[str, dict[str, list[str]]]:
    """missing_from_prompt / extra_in_prompt par vocabulaire."""
    advertised = extract_prompt_controlled_vocabularies(
        build_canonical_vocabulary_contract()
    )
    allowed = canonical_allowed_vocabulary()
    report: dict[str, dict[str, list[str]]] = {}
    keys = list(VOCABULARY_CATEGORY_ORDER)
    for key in keys:
        prompt_values = tuple(advertised.get(key, ()))
        decoder_values = tuple(allowed.get(key, ()))
        report[key] = {
            "prompt_values": list(prompt_values),
            "decoder_values": list(decoder_values),
            "missing_from_prompt": [
                value for value in decoder_values if value not in prompt_values
            ],
            "extra_in_prompt": [
                value for value in prompt_values if value not in decoder_values
            ],
        }
    return report


def all_controlled_values() -> tuple[tuple[str, str], ...]:
    """(vocab_key, value) dans l'ordre canonique — pour la couverture."""
    pairs: list[tuple[str, str]] = []
    for key, item in controlled_vocabularies().items():
        for value in item.values:
            pairs.append((key, value))
    return tuple(pairs)


def controlled_value_count() -> int:
    return len(all_controlled_values())
