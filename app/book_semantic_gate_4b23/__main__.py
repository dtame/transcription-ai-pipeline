"""python -m app.book_semantic_gate_4b23 — offline architecture only."""

from __future__ import annotations

import json

from app.book_semantic_gate_4b23.runner import run_semantic_gate_architecture
from app.book_semantic_gate_4b23.writer import write_semantic_gate_artifacts


def main() -> int:
    result = run_semantic_gate_architecture()
    write_semantic_gate_artifacts(result.bundle)
    print(json.dumps(result.bundle["header"], ensure_ascii=True, indent=2))
    return 0 if result.result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
