"""Publication atomique des octets validés. Jamais un JSON partiel en production."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import partial_path
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    BYTE_IDENTITY_EXACT,
    PUBLICATION_MODE_BLOCKED,
    PUBLICATION_MODE_CONFLICT,
    PUBLICATION_MODE_IDENTICAL,
    PUBLICATION_MODE_NEW,
)
from app.source_analysis_v31_global_a49_source_map_publication.identity import (
    bytes_identity,
    file_identity,
)


def atomic_replace(partial: Path, target: Path) -> None:
    Path(partial).replace(Path(target))


def write_raw_bytes_atomic(path: Path, data: bytes, *, fsync: bool = True) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = partial_path(path)
    try:
        with partial.open("wb") as handle:
            handle.write(data)
            handle.flush()
            if fsync:
                handle.fileno()
                try:
                    import os

                    os.fsync(handle.fileno())
                except OSError:
                    pass
        if partial.read_bytes() != data:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        atomic_replace(partial, path)
    except BaseException:
        leftover = partial_path(path)
        leftover.unlink(missing_ok=True)
        if partial != leftover:
            partial.unlink(missing_ok=True)
        raise
    leftover = partial_path(path)
    if leftover.exists():
        leftover.unlink()
    return path


def inspect_target(path: Path, candidate_bytes: bytes) -> dict[str, Any]:
    path = Path(path)
    exists = path.is_file()
    current = file_identity(path) if exists else {
        "exists": False,
        "sha256": "",
        "utf8_bytes": 0,
        "character_count": 0,
        "canonical_json_sha256": "",
        "json_parse": "FAIL",
        "payload": {},
        "path": str(path),
    }
    candidate = bytes_identity(candidate_bytes)
    identical = exists and path.read_bytes() == candidate_bytes
    conflict = exists and not identical
    if not exists:
        mode = PUBLICATION_MODE_NEW
    elif identical:
        mode = PUBLICATION_MODE_IDENTICAL
    else:
        mode = PUBLICATION_MODE_CONFLICT
    return {
        "path": str(path),
        "preexisted": exists,
        "conflict": conflict,
        "identical": identical,
        "mode": mode,
        "existing": current,
        "candidate": candidate,
    }


def publish_exact_bytes(
    target: Path,
    candidate_bytes: bytes,
    *,
    authorized: bool,
) -> dict[str, Any]:
    target = Path(target)
    inspection = inspect_target(target, candidate_bytes)
    mode = inspection["mode"]
    published = False
    atomic = "NOT_ATTEMPTED"
    if not authorized:
        mode = PUBLICATION_MODE_BLOCKED
        return {
            **inspection,
            "mode": mode,
            "published": False,
            "atomic_publication": "NOT_ATTEMPTED",
            "byte_identity": "NOT_PUBLISHED",
            "partial_leftover": partial_path(target).exists(),
        }
    if mode == PUBLICATION_MODE_CONFLICT:
        return {
            **inspection,
            "published": False,
            "atomic_publication": "BLOCKED_CONFLICT",
            "byte_identity": "CONFLICT",
            "partial_leftover": False,
        }
    if mode == PUBLICATION_MODE_IDENTICAL:
        atomic = "SKIPPED_IDENTICAL"
    else:
        write_raw_bytes_atomic(target, candidate_bytes)
        published = True
        atomic = "PASS"
        mode = PUBLICATION_MODE_NEW
    after = target.read_bytes() if target.is_file() else b""
    byte_identity = (
        BYTE_IDENTITY_EXACT if after == candidate_bytes else "MISMATCH"
    )
    return {
        **inspection,
        "mode": mode if mode == PUBLICATION_MODE_IDENTICAL else (
            PUBLICATION_MODE_NEW if published or mode == PUBLICATION_MODE_NEW else mode
        ),
        "published": published or mode == PUBLICATION_MODE_IDENTICAL,
        "atomic_publication": atomic,
        "byte_identity": byte_identity,
        "partial_leftover": partial_path(target).exists(),
        "published_identity": bytes_identity(after) if after else {},
    }


__all__ = [
    "atomic_replace",
    "inspect_target",
    "partial_path",
    "publish_exact_bytes",
    "write_raw_bytes_atomic",
]
