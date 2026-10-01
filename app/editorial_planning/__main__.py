"""python -m app.editorial_planning — audit offline Phase 4A uniquement."""

from __future__ import annotations

import json

from app.editorial_planning.audit_writer import write_audit_bundle
from app.editorial_planning.constants import VALIDATION_PROJECT_NAME
from app.editorial_planning.runner import build_bundle


def main() -> int:
    bundle = build_bundle(project_name=VALIDATION_PROJECT_NAME)
    write_audit_bundle(VALIDATION_PROJECT_NAME, bundle)
    print(json.dumps(bundle["header"], ensure_ascii=True, indent=2))
    return 0 if bundle["header"].get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
