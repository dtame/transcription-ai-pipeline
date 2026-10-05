"""Python runtime and dependency forensics. No secrets. No network."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.ai.provider_preflight import PROVIDER_SPECS, import_provider_sdk, inspect_sdk
from app.ai.settings import ENV_OPENAI_API_KEY, get_api_key
from app.book_semantic_gate_4b241.constants import (
    CANONICAL_DEPENDENCY_MECHANISM,
    CANONICAL_PYTHON_ENV,
    OPENAI_SDK_CONSTRAINT,
)
from app.book_semantic_gate_4b241.paths import repo_root, requirements_path, venv_python_path


def describe_interpreter(executable: str | None = None) -> dict[str, Any]:
    return {
        "executable": executable or sys.executable,
        "version": sys.version,
        "version_info": list(sys.version_info[:3]),
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "in_virtualenv": sys.prefix != sys.base_prefix,
    }


def classify_environment(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    venv = venv_python_path(root=base)
    current = Path(sys.executable).resolve()
    venv_resolved = venv.resolve() if venv.exists() else None
    return {
        "canonical_environment": CANONICAL_PYTHON_ENV,
        "canonical_executable": str(venv) if venv.exists() else None,
        "current_is_canonical_venv": bool(
            venv_resolved and current == venv_resolved
        ),
        "venv_present": venv.exists(),
        "pipenv": (base / "Pipfile").exists(),
        "poetry": (base / "pyproject.toml").exists() or (base / "poetry.lock").exists(),
        "setup_py": (base / "setup.py").exists(),
        "setup_cfg": (base / "setup.cfg").exists(),
        "requirements_txt": requirements_path(root=base).exists(),
        "requirements_dev_txt": (base / "requirements-dev.txt").exists(),
        "dependency_mechanism": CANONICAL_DEPENDENCY_MECHANISM,
    }


def openai_declared_in_requirements(*, root: Path | None = None) -> bool:
    path = requirements_path(root=root)
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.split("=", 1)[0].split(">", 1)[0].split("<", 1)[0].strip() == "openai":
            return True
    return False


def openai_constraint_in_requirements(*, root: Path | None = None) -> str | None:
    path = requirements_path(root=root)
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("openai"):
            return stripped
    return None


def inspect_openai_install() -> dict[str, Any]:
    spec = PROVIDER_SPECS["openai"]
    status = inspect_sdk(spec)
    version = status.get("version")
    if status.get("importable"):
        try:
            module = import_provider_sdk("openai")
            from_ok = hasattr(module, "OpenAI")
        except Exception:
            from_ok = False
    else:
        from_ok = False
    return {
        **status,
        "from_openai_import_OpenAI": "PASS" if from_ok else "FAIL",
        "constraint": OPENAI_SDK_CONSTRAINT,
        "credential_available": (
            "YES"
            if bool(get_api_key(ENV_OPENAI_API_KEY, config_fallback="OPENAI_API_KEY"))
            else "NO"
        ),
    }


def root_cause(
    *,
    declared: bool,
    installed_in_canonical: bool,
    installed_in_failed_interpreter: bool,
    failed_interpreter_was_system: bool,
) -> dict[str, Any]:
    if failed_interpreter_was_system and installed_in_canonical and not installed_in_failed_interpreter:
        code = "C"
        summary = (
            "Wrong Python environment: 4B.2.4 attempt 2 executed "
            "C:\\Program Files\\Python311\\python.exe (system) instead of "
            "the canonical project .venv, where openai was already installed."
        )
    elif declared and not installed_in_canonical:
        code = "A"
        summary = "OpenAI SDK is declared in requirements.txt but was not installed in the canonical environment."
    elif not declared:
        code = "B"
        summary = "OpenAI SDK was not declared in the project dependency manifest."
    else:
        code = "D"
        summary = "OpenAI runtime failed for another local dependency or configuration reason."
    return {
        "code": code,
        "summary": summary,
        "declared": declared,
        "installed_in_canonical_venv": installed_in_canonical,
        "installed_in_failed_system_interpreter": installed_in_failed_interpreter,
        "failed_interpreter_was_system_python": failed_interpreter_was_system,
        "secondary": (
            "4B.2.4 consumed the one-shot lock before from openai import OpenAI succeeded."
        ),
    }


def runtime_forensics(*, root: Path | None = None) -> dict[str, Any]:
    env = classify_environment(root=root)
    declared = openai_declared_in_requirements(root=root)
    install = inspect_openai_install()
    current = describe_interpreter()
    cause = root_cause(
        declared=declared,
        installed_in_canonical=bool(env["venv_present"] and install.get("importable")),
        installed_in_failed_interpreter=False,
        failed_interpreter_was_system=True,
    )
    return {
        "python_executable": current["executable"],
        "python_version": current["version"],
        "python_prefix": current["prefix"],
        "python_base_prefix": current["base_prefix"],
        "environment_type": (
            CANONICAL_PYTHON_ENV if env["current_is_canonical_venv"] else (
                "venv" if current["in_virtualenv"] else "system"
            )
        ),
        "canonical_environment_type": CANONICAL_PYTHON_ENV,
        "dependency_mechanism": CANONICAL_DEPENDENCY_MECHANISM,
        "openai_dependency_status": {
            "declared_in_requirements": declared,
            "constraint": openai_constraint_in_requirements(root=root),
            "importable_in_current_interpreter": bool(install.get("importable")),
            "version": install.get("version"),
            "from_openai_import_OpenAI": install.get("from_openai_import_OpenAI"),
        },
        "anthropic_convention": {
            "official_sdk_declared": False,
            "official_sdk_required": False,
            "transport": "requests",
            "note": (
                "Anthropic uses app/ai/providers/anthropic_engine.py + requests. "
                "The official anthropic package is intentionally not a dependency."
            ),
        },
        "environment": env,
        "interpreter": current,
        "root_cause": cause,
        "secrets_included": False,
    }


__all__ = [
    "classify_environment",
    "describe_interpreter",
    "inspect_openai_install",
    "openai_constraint_in_requirements",
    "openai_declared_in_requirements",
    "root_cause",
    "runtime_forensics",
]
