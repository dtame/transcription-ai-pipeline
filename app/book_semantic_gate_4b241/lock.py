"""One-shot lock forensics for historical 4B.2.4 attempt 2. Read-only."""

from __future__ import annotations

from typing import Any

from app.ai.provider_preflight import future_call_accounting_contract
from app.book_semantic_gate_4b24.paths import canary_lock_path


def lock_forensics(*, root=None) -> dict[str, Any]:
    path = canary_lock_path(root=root)
    exists = path.is_file()
    text = path.read_text(encoding="utf-8") if exists else ""
    return {
        "historical_phase": "4B.2.4",
        "historical_attempt": 2,
        "historical_result": "FAIL",
        "do_not_rewrite_history": True,
        "lock_path": str(path),
        "lock_present": exists,
        "lock_consumed": exists and "consumed=1" in text,
        "lock_text_redacted": [line for line in text.splitlines() if line.strip()],
        "consumption_order": [
            {
                "step": 1,
                "site": "app/book_semantic_gate_4b24/runner.py:_consume_lock",
                "when": "before guard.guarded_generate",
                "condition": "isinstance(engine, CountingOpenAIEngine)",
                "effect": "writes book_semantic_gate_4b24_real_call.lock consumed=1",
            },
            {
                "step": 2,
                "site": "app/editorial_planner_canary_4a1/guard.py:OneShotCallGuard.guarded_generate",
                "when": "increments generate_attempts BEFORE engine.generate",
                "effect": "EXECUTION_ATTEMPT counted even if generate later fails locally",
            },
            {
                "step": 3,
                "site": "app/book_semantic_gate_4b24/engine.py:CountingOpenAIEngine.generate",
                "when": "increments generate_attempts then calls OpenAIEngine.generate",
                "effect": "engine-level attempt counter",
            },
            {
                "step": 4,
                "site": "app/book_semantic_gate_4b24/engine.py:CountingOpenAIEngine._invoke",
                "when": "increments post_attempts BEFORE super()._invoke",
                "effect": "historical ACTUAL TERRA CALLS / openai_post_attempts += 1",
            },
            {
                "step": 5,
                "site": "app/ai/providers/openai_engine.py:OpenAIEngine._invoke -> client()",
                "when": "from openai import OpenAI",
                "effect": (
                    "ImportError translated to AIProviderUnavailableError. "
                    "No client.chat.completions.create. No HTTP."
                ),
            },
        ],
        "why_attempt_2_consumed_slot_before_http": (
            "The file lock is written and OneShotCallGuard / CountingOpenAIEngine "
            "counters increment before the late import inside OpenAIEngine.client(). "
            "Attempt 2 therefore consumed the logical one-shot slot at local "
            "import failure: 'Le package openai n est pas installe'. "
            "HTTP to OpenAI remained 0. No request id, status, tokens, or response."
        ),
        "http_requests": 0,
        "remote_invocations": 0,
        "provider_responses": 0,
        "failed_interpreter": r"C:\Program Files\Python311\python.exe",
        "canonical_interpreter": r".venv\Scripts\python.exe",
        "future_accounting": future_call_accounting_contract(),
        "secrets_included": False,
    }


__all__ = ["lock_forensics"]
