"""Fixtures synthétiques de transport fenêtre — pas le corpus pastoral."""

from __future__ import annotations

from pathlib import Path

from app.source_analysis.transcript_input import (
    SourceSegment,
    TranscriptInput,
    TranscriptInputMode,
)
from statistics import mean, median

from app.ai.errors import AIError
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.window_models import make_window_input
from app.source_analysis_hybrid.constants import (
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PLAN_STRATEGY,
    PLANNER_VERSION,
    TARGET_INPUT_TOKENS,
)
from app.source_analysis_hybrid.contracts import WindowInput, WindowPlan


def _record(kind, value, source_refs=None, links=None, metadata=None):
    return {
        "k": kind,
        "v": value,
        "s": list(source_refs or []),
        "l": list(links or []),
        "m": list(metadata or []),
    }


def make_transcript(
    texts: tuple[str, ...],
    *,
    src_ids: tuple[str, ...] | None = None,
    transcript_id: str = "TR001",
    language: str = "en",
    content_sha256: str = "a" * 64,
) -> TranscriptInput:
    segments: list[SourceSegment] = []
    for index, text in enumerate(texts):
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
        project_name="fixture",
        transcript_id=transcript_id,
        primary_language=language,
        detected_languages=(language,),
        segments=tuple(segments),
        path=Path("fixture.json"),
        content_sha256=content_sha256,
        schema_version="1.0",
        duration_seconds=float(len(segments)),
        mode=TranscriptInputMode.SOURCE,
    )


def window_for(
    transcript: TranscriptInput,
    *,
    owned: tuple[str, ...] | None = None,
    context: tuple[str, ...] = (),
    window_id: str = "WIN001",
) -> WindowInput:
    refs = owned if owned is not None else transcript.src_ids()
    return make_window_input(
        transcript,
        owned_src_refs=refs,
        context_src_refs=context,
        window_id=window_id,
        estimated_input_tokens=100,
    )


def minimal_transport(*, owned_src: str = "SRC000001") -> dict:
    return {
        "theme": "Faith changes how trials are crossed",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("TOPIC", "Faith in trial", [owned_src], [], ["What faith changes."]),
            _record(
                "IDEA",
                "Faith changes the crossing.",
                [owned_src],
                [0],
                ["claim", "central"],
            ),
        ],
    }


def rich_transport(
    *,
    owned_a: str = "SRC000001",
    owned_b: str = "SRC000002",
    extra_src: str | None = None,
) -> dict:
    third = extra_src or owned_a
    return {
        "theme": "Faith changes how trials are crossed",
        "intent": "Teach what faith does in hardship.",
        "ic": "high",
        "aud": "Believers facing trials.",
        "ac": "medium",
        "records": [
            _record("INTENT_KIND", "enseigner"),
            _record("AUDIENCE_KIND", "croyants"),
            _record("TOPIC", "Faith in trial", [owned_a], [], ["What faith changes."]),
            _record(
                "TOPIC",
                "Trust revealed",
                [owned_b],
                [],
                ["Trial reveals existing trust."],
            ),
            _record(
                "IDEA",
                "Faith changes the crossing.",
                [owned_a],
                [2],
                ["claim", "central"],
            ),
            _record(
                "IDEA",
                "Trial reveals trust.",
                [owned_b],
                [3],
                ["explanation", "supporting"],
            ),
            _record("RELATION", "supports", [], [5, 4], []),
            _record(
                "EXAMPLE",
                "A man who still prayed each morning.",
                [owned_b],
                [4],
                ["anecdote"],
            ),
            _record(
                "REFERENCE",
                "Paul says somewhere",
                [owned_a],
                [],
                ["biblical", "vague", ""],
            ),
            _record(
                "UNCERTAINTY",
                "The Pauline reference is not located.",
                [owned_a],
                [],
                ["incomplete_reference", "medium"],
            ),
            _record(
                "REPETITION",
                "Claim then development.",
                [owned_a, owned_b],
                [4, 5],
                ["development"],
            ),
            _record("VOICE", "didactic", [], [], ["tone"]),
            _record("VOICE", "oral accessible", [], [], ["register"]),
            _record("VOICE", "short sentences", [], [], ["sentence_style"]),
            _record("VOICE", "opposition", [], [], ["rhetorical_patterns"]),
            _record("VOICE", "rare", [], [], ["use_of_questions"]),
            _record("VOICE", "central formulas", [], [], ["use_of_repetition"]),
            _record("VOICE", "anecdotes", [], [], ["use_of_examples"]),
            _record("VOICE", "you", [], [], ["direct_address"]),
            _record("VOICE", "claim then illustration", [], [], ["teaching_style"]),
            _record("VOICE", "concrete images", [], [], ["distinctive_traits"]),
            _record(
                "IDEA",
                "Keep walking anyway.",
                [third],
                [3],
                ["instruction", "supporting"],
            ),
        ],
    }


def invalid_vocabulary_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["records"].append(
        _record(
            "UNCERTAINTY",
            "Possible artifact.",
            [owned_src],
            [],
            ["transcription_artifact", "low"],
        )
    )
    return payload


def invalid_src_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["records"][0]["s"] = ["SRC999999"]
    return payload


def context_only_transport(*, context_src: str) -> dict:
    return {
        "theme": "Boundary fragment",
        "intent": "Observe a cut thought.",
        "ic": "low",
        "aud": "Unclear.",
        "ac": "low",
        "records": [
            _record(
                "TOPIC",
                "Context only topic",
                [context_src],
                [],
                ["Should not stand alone."],
            ),
            _record(
                "IDEA",
                "Invented from context.",
                [context_src],
                [0],
                ["claim", "minor"],
            ),
        ],
    }


def owned_plus_context_transport(*, owned_src: str, context_src: str) -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["records"][1]["s"] = [owned_src, context_src]
    return payload


def deleted_src_transport(*, deleted_src: str, owned_src: str = "SRC000001") -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["records"][0]["s"] = [deleted_src]
    return payload


def invalid_link_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["records"][1]["l"] = [99]
    return payload


def editorial_leak_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["chapters"] = [{"title": "Chapter 1"}]
    return payload


def invalid_kind_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["records"][0]["k"] = "CHAPTER"
    return payload


def invalid_idea_kind_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["records"][1]["m"] = ["hypothesis", "central"]
    return payload


def invalid_relation_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = rich_transport(owned_a=owned_src, owned_b=owned_src)
    payload["records"][6]["v"] = "implies"
    return payload


def invalid_uncertainty_kind_transport(*, owned_src: str = "SRC000001") -> dict:
    return invalid_vocabulary_transport(owned_src=owned_src)


def window_plan_from_inputs(
    transcript: TranscriptInput,
    windows: tuple[WindowInput, ...],
) -> WindowPlan:
    """Plan synthétique stable — frontières fournies, pas un second planner."""
    if not windows:
        raise ValueError("WindowPlan synthétique vide interdit.")
    estimates = [window.estimated_input_tokens for window in windows]
    return WindowPlan(
        strategy=PLAN_STRATEGY,
        planner_version=windows[0].planner_version or PLANNER_VERSION,
        transcript_id=transcript.transcript_id,
        transcript_sha256=transcript.content_sha256,
        target_input_tokens=TARGET_INPUT_TOKENS,
        hard_max_input_tokens=HARD_MAX_INPUT_TOKENS,
        overlap_policy=OVERLAP_POLICY,
        prompt_overhead_tokens=0,
        windows=windows,
        owned_src_count=sum(window.owned_src_count for window in windows),
        context_src_count=sum(window.context_src_count for window in windows),
        window_count=len(windows),
        estimated_input_tokens_min=min(estimates),
        estimated_input_tokens_max=max(estimates),
        estimated_input_tokens_mean=float(mean(estimates)),
        estimated_input_tokens_median=float(median(estimates)),
    )


def three_window_fixture(
    *,
    texts: tuple[str, str, str] | None = None,
    content_sha256: str = "a" * 64,
    language: str = "en",
) -> tuple[TranscriptInput, WindowPlan]:
    """Trois fenêtres, une SRC chacune, frontières stables."""
    chosen = texts or (
        "Faith changes the crossing of a trial.",
        "Trust is revealed in hardship.",
        "Keep walking through the valley.",
    )
    transcript = make_transcript(chosen, content_sha256=content_sha256, language=language)
    windows = (
        window_for(transcript, owned=("SRC000001",), window_id="WIN001"),
        window_for(transcript, owned=("SRC000002",), window_id="WIN002"),
        window_for(transcript, owned=("SRC000003",), window_id="WIN003"),
    )
    return transcript, window_plan_from_inputs(transcript, windows)


class WindowMappedFakeAI(FakeAIEngine):
    """FakeAI dispatch par window_id. Le dernier item n'est pas rejoué."""

    def __init__(
        self,
        replies: dict[str, FakeReply | BaseException],
        *,
        model: str | None = None,
    ):
        super().__init__(
            script=[],
            retry_policy=no_delay_policy(max_attempts=1),
            model=model,
        )
        self._replies = dict(replies)

    def _invoke(self, request, model):
        self.requests.append(request)
        window_id = (request.metadata or {}).get("window_id")
        if window_id not in self._replies:
            raise AIError(f"aucune réponse FakeAI pour {window_id!r}")
        scripted = self._replies[window_id]
        if isinstance(scripted, BaseException):
            raise scripted
        text = scripted.text
        if scripted.parsed is not None:
            import json

            text = json.dumps(scripted.parsed, ensure_ascii=False)
        from app.ai.providers.base import ProviderResult

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


def mapped_minimal_engine(plan: WindowPlan) -> WindowMappedFakeAI:
    replies = {
        window.window_id: FakeReply(
            parsed=minimal_transport(owned_src=window.owned_src_refs[0])
        )
        for window in plan.windows
    }
    return WindowMappedFakeAI(replies)


def invalid_severity_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = minimal_transport(owned_src=owned_src)
    payload["records"].append(
        _record(
            "UNCERTAINTY",
            "Unclear cut.",
            [owned_src],
            [],
            ["ambiguous_meaning", "critical"],
        )
    )
    return payload
