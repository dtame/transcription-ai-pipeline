"""CLI offline 3B.7.7A.2. Aucun appel provider."""

from __future__ import annotations

import argparse
import sys

from app.source_analysis_window_output_bounding.constants import PROJECT_NAME
from app.source_analysis_window_output_bounding.runner import run_window_output_bounding


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="3B.7.7A.2 offline window output bounding / granularity redesign"
    )
    parser.add_argument("project_name", nargs="?", default=PROJECT_NAME)
    args = parser.parse_args(argv)
    result = run_window_output_bounding(args.project_name)
    print(
        f"[3B.7.7A.2] result={result['result']} "
        f"real_provider_calls={result['real_provider_calls']}"
    )
    for name, sha in result["sha256"].items():
        print(f"[3B.7.7A.2] {name} sha256={sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
