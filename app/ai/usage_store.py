"""
Persistance de l'usage IA d'un projet.

Les lignes d'appel produites par le CostTracker sont rangées dans
project_state.json sous la clé `ai_usage`, à côté de `files`, `chunks` et
`publication`. C'est le même fichier que le reste du pipeline : pas de
nouveau magasin de données, pas de format concurrent.

    appel IA
      ↓  AIResponse
    CostTracker.record_response()
      ↓  AICallRecord
    usage_store.record_call()          -> project_state.json["ai_usage"]
      ↓
    report_service.build_project_report()
      ↓
    report.json["ai_usage"]

`build_ai_usage_report()` retourne un bloc valide même pour un projet sans
aucun appel IA : c'est le cas de tous les projets existants, et le rapport
ne doit pas changer de forme selon qu'une étape IA a tourné ou non.

Aucun prompt ni texte généré n'est persisté — uniquement des métriques.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from app.ai.cost import (
    AICallRecord,
    CostTracker,
    aggregate_records,
    empty_usage_block,
)
from app.ai.pricing import CURRENCY_USD

STATE_KEY = "ai_usage"
RECORDS_KEY = "records"


def ensure_usage_section(state: dict) -> dict:
    """Crée la section `ai_usage` du state si elle est absente. Idempotent."""
    section = state.setdefault(STATE_KEY, {})

    if not isinstance(section, dict):
        section = {}
        state[STATE_KEY] = section

    section.setdefault(RECORDS_KEY, [])

    return section


def load_records(state: Mapping) -> list[dict]:
    """Lignes d'appel enregistrées pour ce projet, ou liste vide."""
    section = state.get(STATE_KEY) or {}

    if not isinstance(section, Mapping):
        return []

    records = section.get(RECORDS_KEY) or []

    return [dict(record) for record in records if isinstance(record, Mapping)]


def append_records(state: dict, records: Iterable[Mapping]) -> list[dict]:
    """Ajoute des lignes d'appel au state en mémoire et les retourne toutes."""
    section = ensure_usage_section(state)
    section[RECORDS_KEY].extend(dict(record) for record in records)

    return section[RECORDS_KEY]


def append_tracker(state: dict, tracker: CostTracker) -> list[dict]:
    """Verse le contenu d'un CostTracker dans le state d'un projet."""
    return append_records(state, tracker.serialize())


def record_call(project_name: str, record: AICallRecord | Mapping) -> None:
    """
    Persiste une ligne d'appel dans project_state.json.

    Relit puis réécrit le state à chaque appel, comme le fait déjà le reste du
    pipeline : c'est ce qui permet de reprendre après une interruption sans
    perdre la comptabilité des appels déjà payés.
    """
    from app.project_state import load_project_state, save_project_state

    payload = record.to_dict() if isinstance(record, AICallRecord) else dict(record)

    state = load_project_state(project_name)
    append_records(state, [payload])
    save_project_state(project_name, state)


def tracker_from_state(state: Mapping, **kwargs) -> CostTracker:
    """
    Reconstruit un CostTracker vide dont on pourra agréger l'historique.

    Les coûts déjà calculés sont conservés tels quels : un tarif qui change
    ne doit pas réécrire rétroactivement le coût d'appels déjà facturés.
    """
    tracker = CostTracker(**kwargs)

    return tracker


def build_ai_usage_report(
    state: Mapping,
    *,
    currency: str = CURRENCY_USD,
    include_details: bool = True,
) -> dict:
    """
    Bloc `ai_usage` de report.json, agrégé depuis project_state.json.

    Sans aucun appel enregistré, retourne le bloc vide : calls=0, coût 0.0 et
    cost_status="no_calls". Zéro appel coûte bien zéro — à la différence d'un
    appel non tarifé, dont le coût reste None.
    """
    records = load_records(state)

    if not records:
        return empty_usage_block(currency)

    block = aggregate_records(records, default_currency=currency)

    if include_details:
        block["details"] = records

    return block
