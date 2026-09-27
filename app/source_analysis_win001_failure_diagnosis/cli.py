"""CLI offline 3B.7.7A.1. Aucun appel provider."""

from __future__ import annotations

import argparse
import sys

from app.source_analysis_win001_failure_diagnosis.constants import PROJECT_NAME
from app.source_analysis_win001_failure_diagnosis.runner import run_win001_failure_diagnosis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="3B.7.7A.1 offline WIN001 structured-output / token diagnosis"
    )
    parser.add_argument("project_name", nargs="?", default=PROJECT_NAME)
    args = parser.parse_args(argv)
    result = run_win001_failure_diagnosis(args.project_name)
    print(f"[3B.7.7A.1] result=PASS real_provider_calls={result['real_provider_calls']}")
    for name, sha in result["sha256"].items():
        print(f"[3B.7.7A.1] {name} sha256={sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
