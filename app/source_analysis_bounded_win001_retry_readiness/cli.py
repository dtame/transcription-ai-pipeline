"""CLI offline 3B.7.7A.3. Aucun appel provider."""

from __future__ import annotations

import argparse
import sys

from app.source_analysis_bounded_win001_retry_readiness.constants import PROJECT_NAME
from app.source_analysis_bounded_win001_retry_readiness.runner import (
    run_bounded_win001_retry_readiness,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="3B.7.7A.3 offline bounded WIN001 retry readiness / cost-risk"
    )
    parser.add_argument("project_name", nargs="?", default=PROJECT_NAME)
    forbidden = {"--execute-real", "--real-call", "--authorize-real-call"}
    args_list = list(sys.argv[1:] if argv is None else argv)
    if any(token in forbidden for token in args_list):
        print("[ERREUR] flags d'exécution réelle interdits dans cette revue.")
        return 2
    args = parser.parse_args(args_list)
    result = run_bounded_win001_retry_readiness(args.project_name)
    print(
        f"[3B.7.7A.3] result={result['result']} readiness={result['readiness']} "
        f"real_provider_calls={result['real_provider_calls']}"
    )
    for name, sha in result["sha256"].items():
        print(f"[3B.7.7A.3] {name} sha256={sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
