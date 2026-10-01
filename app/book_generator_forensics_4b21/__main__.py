"""python -m app.book_generator_forensics_4b21 — offline forensics only."""

from __future__ import annotations

import json

from app.book_generator_forensics_4b21.runner import run_forensics
from app.book_generator_forensics_4b21.writer import write_forensics_artifacts


def main() -> int:
    result = run_forensics()
    write_forensics_artifacts(result.bundle)
    print(json.dumps(result.bundle["header"], ensure_ascii=True, indent=2))
    return 0 if result.result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
