"""
Prompt versionné consolidation-1.0 — GLOBAL SOURCE ANALYSIS CONSOLIDATOR.

Distinct de Prompt 1.3 et de window-analysis-1.0.
Ne pas modifier prompt.py ni window_prompt.py depuis ce module.
"""

from __future__ import annotations

from typing import Any

from app.ai.estimation import estimate_tokens
from app.file_utils import content_hash
from app.source_analysis.canonical_vocabulary import (
    build_canonical_vocabulary_contract,
)
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_OUTPUT_LANGUAGE,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_TRANSPORT_VERSION,
    ConsolidationInput,
    STAGE_CONSOLIDATION,
)
from app.source_analysis.models import RELATION_KINDS, REPETITION_CHARACTERS
from app.source_analysis.prompt import (
    FORBIDDEN_STRUCTURE_BLOCK,
    build_language_directive,
)
from app.source_analysis_hybrid.constants import ESTIMATION_MODEL

CONSOLIDATION_ANALYSIS_PROMPT_VERSION = CONSOLIDATION_PROMPT_VERSION
CONSOLIDATION_PROMPT_ROLE = "GLOBAL SOURCE ANALYSIS CONSOLIDATOR"


_ROLE_BLOCK = """RÔLE

Tu es GLOBAL SOURCE ANALYSIS CONSOLIDATOR. Tu reçois les cartes sémantiques
validées de TOUTES les fenêtres, déjà ordonnées selon le plan source.

Tu n'es pas :
- l'auteur — tu ne complètes, ne prolonges et n'améliores rien ;
- l'éditeur du livre — tu ne décides d'aucune mise en forme de publication ;
- un planificateur de livre — tu ne proposes ni titre, ni chapitres, ni plan ;
- un vérificateur de faits — tu n'as accès à aucune source externe ;
- un analyste de fenêtre — le travail local est déjà fait.

Tu réponds à une seule question : « quelles décisions sémantiques GLOBALES
relient et départagent ces records de fenêtres, sans en faire disparaître ? »"""


_SCOPE_BLOCK = """PÉRIMÈTRE

Examine tous les records sémantiques de fenêtre fournis.
Détermine les métadonnées globales.
Identifie les topics sémantiquement équivalents.
Identifie les idées sémantiquement équivalentes.
Préserve les records uniques.
Identifie les relations inter-fenêtres.
Identifie les répétitions globales.
Relie exemples et références lorsque l'évidence fournie le justifie.
Résous la fragmentation de frontière.
Préserve le sens ancré dans les sources.

Une formulation proche n'est PAS nécessairement la même idée sémantique.
Ne fusionne que lorsque l'équivalence / l'identité est justifiée par les
records fournis. Le code local n'inférera jamais cette équivalence à ta
place : si tu ne fusionnes pas, les deux records restent distincts."""


_NO_DROP_BLOCK = """COMPTABILITÉ — NO DROP

V1 n'expose AUCUNE opération DROP_RECORD.

Chaque record substantif (TOPIC, IDEA, EXAMPLE, REFERENCE, UNCERTAINTY,
REPETITION) et chaque RELATION de fenêtre doit avoir une disposition
explicite :

- KEEP  — conserver tel quel, un seul identifiant WIN:R
- MERGE — fusionner 2+ records du MÊME kind, texte synthétisé grounded

Aucun record substantif ne peut être à la fois KEEP et membre d'un MERGE.
Aucun record ne peut appartenir à deux groupes MERGE.
Un MERGE à un seul membre est interdit.

VOICE, INTENT_KIND et AUDIENCE_KIND sont de l'évidence de métadonnées
globales. Ils n'ont pas à devenir des éléments canoniques autonomes.
Ils doivent apparaître dans les listes d'évidence de GLOBAL_METADATA
(ve / ie / ae) ou être KEEP. Ne les résous jamais silencieusement
comme des faits."""


_OPERATIONS_BLOCK = """OPÉRATIONS — consolidation-transport-v1

Réponds UNIQUEMENT avec un objet JSON compact :

{"gm":{"th":"...","in":"...","au":"...","vo":"...","te":[],"ie":[],"ae":[],"ve":[]},"ops":[{"o":"..."}]}

gm = GLOBAL_METADATA, obligatoire, grounded :
- th = main_theme
- in = author_intent
- au = target_audience
- vo = author_voice_profile
- te / ie / ae / ve = identifiants WIN:R d'évidence (non vides)

ops = liste d'opérations, dans l'ordre du transport :

KEEP   {"o":"KEEP","r":"WIN001:R0001"}
MERGE  {"o":"MERGE","m":["WIN001:R0001","WIN002:R0001"],"v":"texte fusionné grounded"}
REL    {"o":"REL","t":"supports","a":"WIN001:R0004","b":"WIN003:R0008"}
REP    {"o":"REP","c":"rhetorical","m":["WIN001:R0002","WIN002:R0003"],"v":"description"}

o ∈ KEEP | MERGE | REL | REP uniquement.
Aucun DROP. Aucun identifiant canonique TOP001 / IDEA001.
Aucun identifiant C0001 : le code local les assignera.
Référence uniquement des identifiants WIN:R existants.
N'invente aucun SRC. Le code local calculera l'union des SRC des membres.

Types de relation autorisés (copie exacte) :
""" + " | ".join(RELATION_KINDS) + """

Caractères de répétition autorisés (copie exacte) :
""" + " | ".join(REPETITION_CHARACTERS) + """

MERGE : même kind seulement. TOPIC+IDEA = interdit.
Le texte MERGE (v) doit être grounded uniquement dans les membres cités.
KEEP n'exige pas de texte réécrit.
REL relie deux records (éventuellement de fenêtres différentes).
Un EXAMPLE d'une fenêtre peut illustrer / soutenir une IDEA d'une autre
via REL t=illustrates ou t=supports.
REP relie des records répétés à travers les fenêtres."""


_FORBIDDEN_OUTPUT_BLOCK = """SORTIE INTERDITE

N'émets jamais :
- de chapitres, sections de livre, titre ou sous-titre de livre ;
- de plan éditorial, de prose de publication ;
- de nouveaux arguments, exemples, références ou faits non fournis ;
- de SourceMap JSON canonique ;
- d'identifiants TOP / IDEA / EX / REF / UNC / REP finaux ;
- d'opération DROP.

Si un champ éditorial apparaît, l'analyse est rejetée."""


def build_consolidation_system_prompt(primary_language: str | None = None) -> str:
    language = primary_language or CONSOLIDATION_OUTPUT_LANGUAGE
    return "\n\n".join(
        [
            _ROLE_BLOCK,
            _SCOPE_BLOCK,
            _NO_DROP_BLOCK,
            _OPERATIONS_BLOCK,
            FORBIDDEN_STRUCTURE_BLOCK,
            _FORBIDDEN_OUTPUT_BLOCK,
            build_canonical_vocabulary_contract(),
            build_language_directive(language),
        ]
    )


def build_consolidation_user_prompt(
    consolidation_input: ConsolidationInput,
    *,
    primary_language: str | None = None,
) -> str:
    language = primary_language or CONSOLIDATION_OUTPUT_LANGUAGE
    from app.source_analysis_hybrid.contracts import canonical_dumps

    return "\n\n".join(
        [
            (
                f"TÂCHE — consolider {len(consolidation_input.windows)} fenêtres "
                f"du transcript {consolidation_input.transcript_id}. "
                "Décisions sémantiques globales seulement."
            ),
            build_language_directive(language),
            "CONSOLIDATION INPUT (cartes sémantiques compactes, pas le transcript) :",
            canonical_dumps(consolidation_input.to_dict()).rstrip(),
        ]
    )


def consolidation_prompt_fingerprint(system_prompt: str, user_prompt: str) -> str:
    return content_hash(
        "\n<<<CONSOLIDATOR_SYSTEM>>>\n"
        + (system_prompt or "")
        + "\n<<<CONSOLIDATOR_USER>>>\n"
        + (user_prompt or "")
    )


def consolidation_prompt_sha256(system_prompt: str) -> str:
    return content_hash(system_prompt)


def estimate_consolidation_request_tokens(
    consolidation_input: ConsolidationInput,
    *,
    model: str = ESTIMATION_MODEL,
    primary_language: str | None = None,
) -> dict[str, Any]:
    language = primary_language or CONSOLIDATION_OUTPUT_LANGUAGE
    system = build_consolidation_system_prompt(language)
    user = build_consolidation_user_prompt(
        consolidation_input, primary_language=language
    )
    system_est = estimate_tokens(system, model=model)
    user_est = estimate_tokens(user, model=model)
    total_est = estimate_tokens("\n".join([system, user]), model=model)
    return {
        "model": model,
        "method": total_est.method,
        "estimated": True,
        "system_tokens": system_est.tokens,
        "user_tokens": user_est.tokens,
        "input_tokens": consolidation_input.estimated_tokens,
        "total_tokens": total_est.tokens,
        "prompt_version": CONSOLIDATION_ANALYSIS_PROMPT_VERSION,
        "transport_version": CONSOLIDATION_TRANSPORT_VERSION,
        "stage": STAGE_CONSOLIDATION,
    }


__all__ = [
    "CONSOLIDATION_ANALYSIS_PROMPT_VERSION",
    "CONSOLIDATION_PROMPT_ROLE",
    "build_consolidation_system_prompt",
    "build_consolidation_user_prompt",
    "consolidation_prompt_fingerprint",
    "consolidation_prompt_sha256",
    "estimate_consolidation_request_tokens",
]
