"""
Fixtures synthétiques 3B.7.5 — transcript + transports FakeAI.

Pas le corpus réel. Planner de test uniquement via WindowPlannerConfig
injectée (production 50k/60k inchangée).
"""

from __future__ import annotations

from pathlib import Path

from app.ai.errors import AIError
from app.ai.providers.base import ProviderResult
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.consolidation_models import STAGE_CONSOLIDATION
from app.source_analysis.transcript_input import (
    SourceSegment,
    TranscriptInput,
    TranscriptInputMode,
)
from app.source_analysis.window_fixtures import make_transcript, window_for, window_plan_from_inputs
from app.source_analysis.window_models import (
    STAGE_WINDOW,
    WindowIntermediateRecord,
)
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.contracts import WindowInput, WindowPlan
from app.source_analysis_hybrid.planner import plan_windows_v2

TEST_PLANNER_TARGET = 300
TEST_PLANNER_HARD_MAX = 600
TEST_CONTENT_WEIGHT = 100
E2E_SEGMENT_COUNT = 9

CONSOLIDATION_THEME = "Faith changes how trials are crossed"
CONSOLIDATION_INTENT = "Teach believers to keep walking through hardship by faith."
CONSOLIDATION_AUDIENCE = "Believers facing adversity."
CONSOLIDATION_VOICE = "Didactic oral teaching, direct address."
MERGED_TOPIC_VALUE = "Faith during trials and adversity"
MERGED_IDEA_VALUE = "Faith changes how a trial is crossed."


def _record(kind, value, source_refs=None, links=None, metadata=None):
    return {
        "k": kind,
        "v": value,
        "s": list(source_refs or []),
        "l": list(links or []),
        "m": list(metadata or []),
    }


def test_planner_config() -> WindowPlannerConfig:
    """Config de test uniquement — ne change pas la politique production."""
    return WindowPlannerConfig(
        target_input_tokens=TEST_PLANNER_TARGET,
        hard_max_input_tokens=TEST_PLANNER_HARD_MAX,
    )


def e2e_segment_texts() -> tuple[str, ...]:
    return (
        "Faith during trials changes how a crossing is endured.",
        "Prayer is not optional when the valley is dark.",
        "The night is long but it is not empty.",
        "Faith changes the crossing of hardship in the same way.",
        "A man still prayed each morning before the work began.",
        "The night remains long yet it is inhabited.",
        "Keep walking through the valley even when the path is thin.",
        "The walk itself becomes the teaching of persistence.",
        "Those who limp are still called to take the next step.",
    )


def make_e2e_transcript(
    *,
    transcript_id: str = "TR-HYB-001",
    content_sha256: str = "c" * 64,
    src_ids: tuple[str, ...] | None = None,
    texts: tuple[str, ...] | None = None,
) -> TranscriptInput:
    chosen = texts or e2e_segment_texts()
    segments: list[SourceSegment] = []
    for index, text in enumerate(chosen):
        src_id = src_ids[index] if src_ids is not None else f"SRC{index + 1:06d}"
        segments.append(
            SourceSegment(
                src_id=src_id,
                source_id="AUD001",
                start=float(index),
                end=float(index + 1),
                text=text,
                source_order=index + 1,
            )
        )
    return TranscriptInput(
        project_name="hybrid-e2e",
        transcript_id=transcript_id,
        primary_language="en",
        detected_languages=("en",),
        segments=tuple(segments),
        path=Path("hybrid-e2e.json"),
        content_sha256=content_sha256,
        schema_version="1.0",
        duration_seconds=float(len(segments)),
        mode=TranscriptInputMode.SOURCE,
    )


def plan_e2e_windows(transcript: TranscriptInput | None = None) -> tuple[TranscriptInput, WindowPlan]:
    """WindowPlannerV2 avec config de test — 3 fenêtres, politique prod inchangée."""
    payload = transcript or make_e2e_transcript()
    weights = tuple(TEST_CONTENT_WEIGHT for _ in payload.segments)
    plan = plan_windows_v2(
        payload,
        config=test_planner_config(),
        content_weights=weights,
        overhead=0,
        remeasure=False,
    )
    if plan.window_count < 3:
        raise RuntimeError(
            f"fixture E2E attend 3+ fenêtres, obtenu {plan.window_count}."
        )
    return payload, plan


def _owned_triple(window: WindowInput) -> tuple[str, str, str]:
    owned = list(window.owned_src_refs)
    first = owned[0]
    second = owned[1] if len(owned) > 1 else first
    third = owned[2] if len(owned) > 2 else first
    return first, second, third


def win001_transport(window: WindowInput) -> dict:
    src_a, src_b, src_c = _owned_triple(window)
    return {
        "theme": "Faith during trials",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("INTENT_KIND", "enseigner"),
            _record("AUDIENCE_KIND", "croyants"),
            _record("TOPIC", "Faith during trials", [src_a], [], ["What faith changes."]),
            _record(
                "IDEA",
                "Faith changes how a trial is crossed.",
                [src_a],
                [2],
                ["claim", "central"],
            ),
            _record(
                "IDEA",
                "Prayer is not optional in the valley.",
                [src_b],
                [2],
                ["instruction", "supporting"],
            ),
            _record(
                "IDEA",
                "The night is long but not empty.",
                [src_c],
                [2],
                ["observation", "minor"],
            ),
            _record("RELATION", "supports", [], [4, 3], []),
            _record(
                "REFERENCE",
                "Paul says somewhere",
                [src_a],
                [],
                ["biblical", "vague", ""],
            ),
            _record(
                "UNCERTAINTY",
                "The Pauline reference is not located.",
                [src_a],
                [],
                ["incomplete_reference", "medium"],
            ),
            _record("VOICE", "didactic", [], [], ["tone"]),
            _record("VOICE", "oral accessible", [], [], ["register"]),
        ],
    }


def win002_transport(window: WindowInput) -> dict:
    src_a, src_b, src_c = _owned_triple(window)
    return {
        "theme": "Adversity reveals trust",
        "intent": "Comfort the weary without promising ease.",
        "ic": "high",
        "aud": "Pastors of hurting people.",
        "ac": "medium",
        "records": [
            _record("INTENT_KIND", "encourager"),
            _record("AUDIENCE_KIND", "pasteurs"),
            _record(
                "TOPIC",
                "Faith during trials",
                [src_a],
                [],
                ["Trial-side restatement of faith."],
            ),
            _record(
                "IDEA",
                "Faith changes the crossing of hardship.",
                [src_a],
                [2],
                ["claim", "central"],
            ),
            _record(
                "IDEA",
                "The night remains long yet inhabited.",
                [src_c],
                [2],
                ["observation", "minor"],
            ),
            _record(
                "EXAMPLE",
                "A man who still prayed each morning.",
                [src_b],
                [3],
                ["anecdote"],
            ),
            _record("VOICE", "warm spoken", [], [], ["tone"]),
            _record("VOICE", "short sentences", [], [], ["sentence_style"]),
        ],
    }


def win003_transport(window: WindowInput) -> dict:
    src_a, src_b, _src_c = _owned_triple(window)
    return {
        "theme": "Keep walking",
        "intent": "Urge persistence when the path is thin.",
        "ic": "high",
        "aud": "The wounded traveler.",
        "ac": "medium",
        "records": [
            _record("INTENT_KIND", "exhorter"),
            _record("AUDIENCE_KIND", "blesses"),
            _record(
                "TOPIC",
                "Walking through the valley",
                [src_a],
                [],
                ["A unique late theme."],
            ),
            _record(
                "IDEA",
                "Keep walking through the valley.",
                [src_a],
                [2],
                ["instruction", "central"],
            ),
            _record("VOICE", "claim then illustration", [], [], ["teaching_style"]),
            _record("VOICE", "you", [], [], ["direct_address"]),
            _record(
                "IDEA",
                "The limp does not cancel the next step.",
                [src_b],
                [2],
                ["principle", "supporting"],
            ),
        ],
    }


def window_transport_for(window: WindowInput) -> dict:
    builders = {
        "WIN001": win001_transport,
        "WIN002": win002_transport,
        "WIN003": win003_transport,
    }
    builder = builders.get(window.window_id)
    if builder is None:
        raise KeyError(f"pas de transport FakeAI pour {window.window_id}")
    return builder(window)


def e2e_consolidation_transport() -> dict:
    """
    MERGE des équivalents, KEEP des uniques, pas de DROP.
    Ordre transport volontairement ≠ ordre source.
    """
    return {
        "gm": {
            "th": CONSOLIDATION_THEME,
            "in": CONSOLIDATION_INTENT,
            "au": CONSOLIDATION_AUDIENCE,
            "vo": CONSOLIDATION_VOICE,
            "te": ["WIN001:R0003"],
            "ie": ["WIN001:R0001"],
            "ae": ["WIN001:R0002"],
            "ve": [
                "WIN001:R0010",
                "WIN001:R0011",
                "WIN002:R0008",
                "WIN003:R0005",
                "WIN003:R0006",
            ],
        },
        "ops": [
            {"o": "KEEP", "r": "WIN003:R0003"},
            {
                "o": "MERGE",
                "m": ["WIN001:R0003", "WIN002:R0003"],
                "v": MERGED_TOPIC_VALUE,
            },
            {
                "o": "MERGE",
                "m": ["WIN001:R0004", "WIN002:R0004"],
                "v": MERGED_IDEA_VALUE,
            },
            {"o": "KEEP", "r": "WIN001:R0005"},
            {"o": "KEEP", "r": "WIN001:R0006"},
            {"o": "KEEP", "r": "WIN002:R0005"},
            {"o": "KEEP", "r": "WIN003:R0004"},
            {"o": "KEEP", "r": "WIN003:R0007"},
            {"o": "KEEP", "r": "WIN002:R0006"},
            {"o": "KEEP", "r": "WIN001:R0008"},
            {"o": "KEEP", "r": "WIN001:R0009"},
            {"o": "KEEP", "r": "WIN001:R0007"},
            {"o": "KEEP", "r": "WIN002:R0001"},
            {"o": "KEEP", "r": "WIN002:R0002"},
            {"o": "KEEP", "r": "WIN002:R0007"},
            {"o": "KEEP", "r": "WIN003:R0001"},
            {"o": "KEEP", "r": "WIN003:R0002"},
            {
                "o": "REL",
                "t": "supports",
                "a": "WIN001:R0004",
                "b": "WIN003:R0004",
            },
            {
                "o": "REL",
                "t": "illustrates",
                "a": "WIN002:R0006",
                "b": "WIN001:R0004",
            },
            {
                "o": "REP",
                "c": "rhetorical",
                "m": ["WIN001:R0004", "WIN003:R0004"],
                "v": "The crossing claim returns as a walk.",
            },
        ],
    }


class HybridMappedFakeAI(FakeAIEngine):
    """FakeAI par window_id + une réponse de consolidation. Pas de replay."""

    def __init__(
        self,
        window_replies: dict[str, FakeReply | BaseException],
        consolidation_reply: FakeReply | BaseException,
        *,
        model: str | None = None,
    ):
        super().__init__(
            script=[],
            retry_policy=no_delay_policy(max_attempts=1),
            model=model,
        )
        self._window_replies = dict(window_replies)
        self._consolidation = consolidation_reply
        self.window_calls = 0
        self.consolidation_calls = 0

    def _invoke(self, request, model):
        self.requests.append(request)
        metadata = request.metadata or {}
        stage = metadata.get("stage")
        window_id = metadata.get("window_id")
        if stage == STAGE_CONSOLIDATION or (
            window_id is None and stage != STAGE_WINDOW
        ):
            self.consolidation_calls += 1
            return self._as_result(self._consolidation, model)
        if window_id not in self._window_replies:
            raise AIError(f"aucune réponse FakeAI pour {window_id!r}")
        self.window_calls += 1
        return self._as_result(self._window_replies[window_id], model)

    def _as_result(self, scripted, model):
        if isinstance(scripted, BaseException):
            raise scripted
        text = scripted.text
        if scripted.parsed is not None:
            import json

            text = json.dumps(scripted.parsed, ensure_ascii=False)
        return ProviderResult(
            text=text,
            input_tokens=scripted.input_tokens,
            output_tokens=scripted.output_tokens,
            total_tokens=scripted.total_tokens,
            finish_reason=scripted.finish_reason,
            request_id=scripted.request_id,
            model=scripted.model or model,
            raw_usage=dict(scripted.raw_usage),
        )


def e2e_engine(plan: WindowPlan) -> HybridMappedFakeAI:
    replies = {
        window.window_id: FakeReply(parsed=window_transport_for(window))
        for window in plan.windows
    }
    return HybridMappedFakeAI(
        replies,
        FakeReply(parsed=e2e_consolidation_transport()),
    )


def intermediate(
    record_id: str,
    kind: str,
    value: str,
    source_refs: tuple[str, ...] = (),
    *,
    index: int = 0,
    links: tuple[int, ...] = (),
    link_ids: tuple[str, ...] = (),
    metadata: tuple[str, ...] = (),
) -> WindowIntermediateRecord:
    return WindowIntermediateRecord(
        record_id=record_id,
        transport_index=index,
        kind=kind,
        value=value,
        source_refs=source_refs,
        links=links,
        link_record_ids=link_ids,
        metadata=metadata,
    )


def sparse_transcript() -> TranscriptInput:
    return make_transcript(
        (
            "First sparse source.",
            "Third sparse source.",
            "Tenth sparse source.",
        ),
        src_ids=("SRC000001", "SRC000003", "SRC000010"),
        transcript_id="TR-SPARSE",
        content_sha256="d" * 64,
    )


def two_window_sparse_plan(transcript: TranscriptInput) -> WindowPlan:
    windows = (
        window_for(transcript, owned=("SRC000001",), window_id="WIN001"),
        window_for(
            transcript,
            owned=("SRC000003", "SRC000010"),
            window_id="WIN002",
        ),
    )
    return window_plan_from_inputs(transcript, windows)


__all__ = [
    "CONSOLIDATION_AUDIENCE",
    "CONSOLIDATION_INTENT",
    "CONSOLIDATION_THEME",
    "CONSOLIDATION_VOICE",
    "E2E_SEGMENT_COUNT",
    "MERGED_IDEA_VALUE",
    "MERGED_TOPIC_VALUE",
    "TEST_PLANNER_HARD_MAX",
    "TEST_PLANNER_TARGET",
    "HybridMappedFakeAI",
    "e2e_consolidation_transport",
    "e2e_engine",
    "e2e_segment_texts",
    "intermediate",
    "make_e2e_transcript",
    "plan_e2e_windows",
    "sparse_transcript",
    "test_planner_config",
    "two_window_sparse_plan",
    "window_transport_for",
]
