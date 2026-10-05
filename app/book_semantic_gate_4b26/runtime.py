"""Interpreter and provider-runtime gates. No secrets. No network."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import PROVIDER_SPECS, inspect_sdk
from app.book_semantic_gate_4b241.runtime import (
    classify_environment,
    describe_interpreter,
    inspect_openai_install,
)
from app.book_semantic_gate_4b26.constants import (
    CANONICAL_PYTHON_ENV,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_PYTHON_VERSION,
    OPENAI_SDK_CONSTRAINT,
    PHASE,
)
from app.book_semantic_gate_4b26.paths import repo_root, venv_python_path


def normalize_executable(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def expected_interpreter(*, root: Path | None = None) -> Path:
    configured = Path(CANONICAL_PYTHON_EXECUTABLE)
    if configured.exists():
        return configured.resolve()
    return venv_python_path(root=root).resolve()


def interpreter_match(*, root: Path | None = None) -> dict[str, Any]:
    expected = expected_interpreter(root=root)
    actual = Path(sys.executable).resolve()
    version = list(sys.version_info[:3])
    return {
        "expected": str(expected),
        "actual": str(actual),
        "match": actual == expected,
        "normalized_expected": normalize_executable(expected),
        "normalized_actual": normalize_executable(actual),
        "python_version": version,
        "expected_python_version": list(EXPECTED_PYTHON_VERSION),
        "python_version_match": tuple(version) == EXPECTED_PYTHON_VERSION,
        "canonical_environment": CANONICAL_PYTHON_ENV,
    }


def env_ignored_by_git(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    env_path = base / ".env"
    completed = subprocess.run(
        ["git", "check-ignore", "-q", "--", ".env"],
        cwd=str(base),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "path": ".env",
        "exists": env_path.is_file(),
        "ignored": completed.returncode == 0,
        "gitignore_lists_env": True,
        "secrets_included": False,
        "note": "API key is never printed, hashed, or persisted.",
    }


def runtime_snapshot(*, root: Path | None = None) -> dict[str, Any]:
    match = interpreter_match(root=root)
    env = classify_environment(root=root or repo_root())
    install = inspect_openai_install()
    current = describe_interpreter()
    sdk = inspect_sdk(PROVIDER_SPECS["openai"])
    git_env = env_ignored_by_git(root=root)
    sdk_version = install.get("version") or sdk.get("version")
    return {
        "phase": PHASE,
        "expected_interpreter": match["expected"],
        "actual_interpreter": match["actual"],
        "interpreter_match": match["match"],
        "python_version": current["version"],
        "python_version_info": current["version_info"],
        "python_version_match": match["python_version_match"],
        "openai_sdk_version": sdk_version,
        "expected_openai_sdk_version": EXPECTED_OPENAI_SDK_VERSION,
        "openai_sdk_version_match": str(sdk_version or "") == EXPECTED_OPENAI_SDK_VERSION,
        "openai_sdk_constraint": OPENAI_SDK_CONSTRAINT,
        "credential_available": install.get("credential_available"),
        "environment_type": (
            CANONICAL_PYTHON_ENV if match["match"] else (
                "venv" if current["in_virtualenv"] else "system"
            )
        ),
        "environment": env,
        "interpreter": current,
        "sdk": {
            "import": sdk.get("status"),
            "version": sdk.get("version"),
            "supported": sdk.get("supported"),
            "from_openai_import_OpenAI": install.get("from_openai_import_OpenAI"),
        },
        "env_ignored_by_git": git_env,
        "secrets_included": False,
    }


__all__ = [
    "env_ignored_by_git",
    "expected_interpreter",
    "interpreter_match",
    "normalize_executable",
    "runtime_snapshot",
]
