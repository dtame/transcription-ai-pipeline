"""Fixtures FakeAI V2 — transcript synthétique, pas le corpus pastoral."""

from __future__ import annotations

from typing import Any, Mapping

from app.ai.errors import AIError
from app.ai.providers.base import ProviderResult
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.consolidation_fixtures import keep_all_ops
from app.source_analysis.consolidation_models import ConsolidationInput
from app.source_analysis.hybrid_e2e_fixtures import (
    CONSOLIDATION_AUDIENCE,
    CONSOLIDATION_INTENT,
    CONSOLIDATION_THEME,
    CONSOLIDATION_VOICE,
)
from app.source_analysis.window_fixtures import make_transcript, window_for, window_plan_from_inputs
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis_hybrid.contracts import WindowInput, WindowPlan
from app.source_analysis_local_v2.constants import (
    CONSOLIDATION_RECOVERY_VERSION,
    HARD_CEILINGS,
    OVERFLOW_TOKEN,
    OVERFLOW_UNCERTAINTY_KIND,
    OVERFLOW_UNCERTAINTY_SEVERITY,
)
from app.source_analysis_local_v2.recovery import GlobalRecoveryPayload, parse_recovery_payload
from app.source_analysis_local_v2.synthetic import build_max_policy_v2_transport
from app.source_analysis_small_window_hierarchy.constants import CANDIDATE_PLANNER_VERSION

from dataclasses import replace


def _record(kind, value, source_refs=None, links=None, metadata=None):
    return {
        "k": kind,
        "v": value,
        "s": list(source_refs or []),
        "l": list(links or []),
        "m": list(metadata or []),
    }


def v2_success_transport(*, owned_src: str = "SRC000001") -> dict:
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
            _record(
                "IDEA",
                "Prayer stays when the valley is dark.",
                [owned_src],
                [0],
                ["instruction", "supporting"],
            ),
            _record("RELATION", "supports", [], [2, 1], []),
            _record(
                "EXAMPLE",
                "A man still prayed each morning.",
                [owned_src],
                [1],
                ["anecdote"],
            ),
            _record(
                "REFERENCE",
                "Paul speaks of weakness as strength.",
                [owned_src],
                [],
                ["biblical", "vague", ""],
            ),
            _record(
                "UNCERTAINTY",
                "The exact Pauline wording is not located.",
                [owned_src],
                [],
                ["incomplete_reference", "medium"],
            ),
        ],
    }


def v2_capacity_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v2_success_transport(owned_src=owned_src)
    payload["records"] = list(payload["records"]) + [
        _record(
            "UNCERTAINTY",
            OVERFLOW_TOKEN,
            [owned_src],
            [],
            [OVERFLOW_UNCERTAINTY_KIND, OVERFLOW_UNCERTAINTY_SEVERITY],
        )
    ]
    return payload


def v2_over_limit_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v2_success_transport(owned_src=owned_src)
    extras = []
    ceiling = HARD_CEILINGS["IDEA"]
    for index in range(ceiling + 1):
        extras.append(
            _record(
                "IDEA",
                f"Idea overflow {index}.",
                [owned_src],
                [0],
                ["claim", "supporting"],
            )
        )
    payload["records"] = [payload["records"][0], *extras]
    return payload


def v2_value_overflow_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v2_success_transport(owned_src=owned_src)
    payload["records"][1]["v"] = "x" * 400
    return payload


def v2_source_ref_overflow_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v2_success_transport(owned_src=owned_src)
    payload["records"][1]["s"] = [f"SRC{index:06d}" for index in range(1, 60)]
    return payload


def v2_invalid_kind_transport(*, owned_src: str = "SRC000001") -> dict:
    payload = v2_success_transport(owned_src=owned_src)
    payload["records"].append(_record("CHAPTER", "nope", [owned_src], [], []))
    return payload


def v2_deferred_kind_transport(*, owned_src: str = "SRC000001", kind: str = "VOICE") -> dict:
    payload = v2_success_transport(owned_src=owned_src)
    if kind == "VOICE":
        payload["records"].append(_record("VOICE", "didactic", [], [], ["tone"]))
    else:
        payload["records"].append(
            _record("REPETITION", "restated claim", [owned_src], [1, 2], ["development"])
        )
    return payload


def v2_truncated_json() -> str:
    return (
        '{"theme":"t","intent":"i","ic":"high","aud":"a","ac":"low",'
        '"records":[{"k":"TOPIC","v":"x","s":["SRC000001"],"l":[],"m":[]},'
        '{"k":"REPET'
    )


def seven_window_plan():
    texts = tuple(
        f"Faith window {index} teaches how a trial is crossed."
        for index in range(1, 8)
    )
    src_ids = (
        "SRC000001",
        "SRC000003",
        "SRC000010",
        "SRC000020",
        "SRC000050",
        "SRC000080",
        "SRC000100",
    )
    transcript = make_transcript(
        texts,
        src_ids=src_ids,
        transcript_id="TR-V2-7",
        content_sha256="f" * 64,
    )
    windows = tuple(
        replace(
            window_for(transcript, owned=(src,), window_id=f"WIN{index:03d}"),
            planner_version=CANDIDATE_PLANNER_VERSION,
        )
        for index, src in enumerate(src_ids, start=1)
    )
    plan = replace(
        window_plan_from_inputs(transcript, windows),
        planner_version=CANDIDATE_PLANNER_VERSION,
    )
    return transcript, plan


def multi_src_window(transcript_id: str = "TR-V2-SUB"):
    texts = tuple(f"Owned unit {index} on faith and trials." for index in range(1, 7))
    src_ids = tuple(f"SRC{index:06d}" for index in range(1, 7))
    transcript = make_transcript(
        texts, src_ids=src_ids, transcript_id=transcript_id, content_sha256="b" * 64
    )
    window = window_for(transcript, owned=src_ids, window_id="WIN001")
    return transcript, window


def gm_from_v2_input(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    records = list(consolidation_input.all_records())
    topics = [r.record_id for r in records if r.kind == "TOPIC"]
    ideas = [r.record_id for r in records if r.kind == "IDEA"]
    theme = (topics or ideas or [records[0].record_id])[:2]
    intent = (ideas or theme)[:2]
    audience = (ideas[1:] or ideas or theme)[:2]
    voice = theme[:2] or intent[:2]
    return {
        "th": CONSOLIDATION_THEME,
        "in": CONSOLIDATION_INTENT,
        "au": CONSOLIDATION_AUDIENCE,
        "vo": CONSOLIDATION_VOICE,
        "te": theme,
        "ie": intent,
        "ae": audience,
        "ve": voice,
    }


def keep_all_v2_transport(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    ids = [record.record_id for record in consolidation_input.all_records()]
    return {"gm": gm_from_v2_input(consolidation_input), "ops": keep_all_ops(*ids)}


def global_v2_transport(consolidation_input: ConsolidationInput) -> dict[str, Any]:
    payload = keep_all_v2_transport(consolidation_input)
    ideas_by_window: dict[str, list[str]] = {}
    for record in consolidation_input.all_records():
        if record.kind == "IDEA":
            ideas_by_window.setdefault(record.window_id, []).append(record.record_id)
    window_ids = list(ideas_by_window)
    if len(window_ids) >= 2:
        left = ideas_by_window[window_ids[0]][0]
        right = ideas_by_window[window_ids[1]][0]
        payload["ops"] = list(payload["ops"]) + [
            {
                "o": "REP",
                "m": [left, right],
                "v": "The crossing claim is restated across windows.",
                "c": "development",
            },
            {"o": "REL", "a": left, "b": right, "t": "supports"},
        ]
    return payload


def default_recovery(consolidation_input: ConsolidationInput) -> GlobalRecoveryPayload:
    gm = gm_from_v2_input(consolidation_input)
    return parse_recovery_payload(
        {
            "version": CONSOLIDATION_RECOVERY_VERSION,
            "intent_kinds": ["enseigner"],
            "audience_kinds": ["croyants"],
            "intent_kind_evidence": list(gm["ie"]),
            "audience_kind_evidence": list(gm["ae"]),
            "voice_evidence": list(gm["ve"]),
            "intent_confidence": "high",
            "audience_confidence": "medium",
            "voice_profile": {
                "tone": ["didactic oral teaching"],
                "register": "pastoral spoken register",
                "sentence_style": "short spoken clauses",
                "rhetorical_patterns": ["direct address"],
                "use_of_questions": "occasional",
                "use_of_repetition": "developmental restatement",
                "use_of_examples": "brief lived scenes",
                "direct_address": "you who walk through trial",
                "teaching_style": "oral instruction",
                "distinctive_traits": [CONSOLIDATION_VOICE],
            },
        }
    )


class V2MappedFakeAI(FakeAIEngine):
    def __init__(
        self,
        window_replies: Mapping[str, FakeReply | BaseException] | None = None,
        *,
        default_factory=v2_success_transport,
        consolidation_factory=global_v2_transport,
        **kwargs,
    ):
        kwargs.setdefault("retry_policy", no_delay_policy())
        super().__init__(**kwargs)
        self._window_replies = dict(window_replies or {})
        self._default_factory = default_factory
        self._consolidation_factory = consolidation_factory
        self.window_calls = 0
        self.consolidation_calls = 0

    def _invoke(self, request, model: str) -> ProviderResult:
        metadata = request.metadata or {}
        window_id = metadata.get("window_id")
        stage = metadata.get("stage")
        if window_id:
            self.window_calls += 1
            scripted = self._default_factory
            if window_id in self._window_replies:
                reply = self._window_replies[window_id]
                if isinstance(reply, BaseException):
                    raise reply
                parsed = reply.parsed
                text = reply.text or "{}"
                return ProviderResult(
                    text=text if isinstance(text, str) else "{}",
                    model=model,
                    raw={"parsed": parsed},
                    parsed=parsed,
                    finish_reason=reply.finish_reason,
                    input_tokens=reply.input_tokens,
                    output_tokens=reply.output_tokens,
                    total_tokens=reply.total_tokens,
                )
            owned = "SRC000001"
            parsed = scripted(owned_src=owned) if callable(scripted) else scripted
            return ProviderResult(
                text="{}",
                model=model,
                raw={"parsed": parsed},
                parsed=parsed,
                finish_reason="stop",
            )
        self.consolidation_calls += 1
        return ProviderResult(text="{}", model=model, raw={}, parsed={}, finish_reason="stop")


def reply_for_transport(transport: dict) -> FakeReply:
    return FakeReply(text="{}", parsed=transport, finish_reason="stop")
