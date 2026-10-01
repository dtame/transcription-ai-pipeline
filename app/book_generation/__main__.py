"""python -m app.book_generation — offline Phase 4B.1 audits only."""

from __future__ import annotations

import json

from app.book_generation.audit_writer import write_audit_bundle
from app.book_generation.constants import VALIDATION_PROJECT_NAME
from app.book_generation.runner import build_bundle


def main() -> int:
    bundle = build_bundle(project_name=VALIDATION_PROJECT_NAME)
    write_audit_bundle(bundle)
    print(json.dumps(bundle["header"], ensure_ascii=True, indent=2))
    return 0 if bundle["header"].get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
