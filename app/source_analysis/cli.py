"""
Invocation manuelle du Source Analyzer.

Usage :
    python -m app.source_analysis.cli <projet> --preflight-derived
    python -m app.source_analysis.cli <projet> --analyze-derived

`--preflight-derived` charge le transcript clean en mode DERIVED, planifie
l'analyse, écrit l'artefact de préflight, et S'ARRÊTE avant tout appel IA.

`--analyze-derived` exécute la tentative réelle gardée (max 1 appel
Anthropic, max_attempts=1, aucun fallback). Ne pas combiner les deux flags.
"""

from __future__ import annotations

import sys

from app.source_analysis.errors import SourceAnalysisError
from app.source_analysis.preflight import run_project_derived_preflight
from app.source_analysis.real_run import run_derived_source_analysis


def _usage() -> None:
    print("Usage  : python -m app.source_analysis.cli <nom_du_projet> --preflight-derived")
    print("         python -m app.source_analysis.cli <nom_du_projet> --analyze-derived")
    print("Défaut : STOP avant engine.generate() ; 0 appel réseau.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        _usage()
        return 0

    project_name = argv[0]
    flags = set(argv[1:])

    allowed = {"--preflight-derived", "--analyze-derived"}
    unknown = flags - allowed
    if unknown:
        print(f"[ERREUR] option(s) inconnue(s) : {sorted(unknown)}")
        _usage()
        return 2

    if "--preflight-derived" in flags and "--analyze-derived" in flags:
        print("[ERREUR] --preflight-derived et --analyze-derived sont mutuellement exclusifs.")
        return 2

    if "--analyze-derived" in flags:
        return _run_analyze(project_name)

    if "--preflight-derived" not in flags:
        print("[ERREUR] cette phase n'accepte que --preflight-derived ou --analyze-derived.")
        _usage()
        return 2

    return _run_preflight(project_name)


def _run_preflight(project_name: str) -> int:
    try:
        result = run_project_derived_preflight(project_name, write=True)
    except SourceAnalysisError as exc:
        print(f"[ERREUR] {type(exc).__name__} - STOP : {exc}")
        return 1

    artifact = result.to_artifact()
    analysis = artifact["source_analysis"]
    print(f"[source_analyzer_preflight] mode = {artifact['input']['mode']}")
    print(
        f"[source_analyzer_preflight] provider={analysis['provider']} "
        f"model={analysis['model']}"
    )
    print(
        f"[source_analyzer_preflight] segments={result.transcript.segment_count} "
        f"words={result.transcript.word_count} "
        f"duration={result.transcript.duration_seconds}"
    )
    tokens = analysis["estimated_tokens"]
    print(
        f"[source_analyzer_preflight] tokens system={tokens['system']} "
        f"user={tokens['user']} total={tokens['total']}"
    )
    print(
        f"[source_analyzer_preflight] strategy={analysis['context_strategy']} "
        f"budget={analysis['usable_input_budget']} "
        f"margin={analysis['remaining_margin']}"
    )
    print(f"[source_analyzer_preflight] signature={analysis['signature']}")
    print("[source_analyzer_preflight] would_call_ai=false engine.generate=0 network=0")
    print("[source_analyzer_preflight] STOP - en attente de revue humaine.")
    return 0


def _run_analyze(project_name: str) -> int:
    print(f"[source_analyzer_real] projet={project_name} mode=DERIVED")
    print("[source_analyzer_real] max_real_calls=1 max_attempts=1 provider=anthropic")
    print("[source_analyzer_real] aucun fallback, aucun retry, aucun second prompt")

    result = run_derived_source_analysis(project_name)

    print(f"[source_analyzer_real] outcome={result.outcome}")
    print(
        f"[source_analyzer_real] pipeline={result.pipeline_result} "
        f"real_call={result.real_call_result}"
    )
    print(
        f"[source_analyzer_real] real_calls={result.real_call_count} "
        f"cache_hit={result.cache_hit}"
    )
    if result.error_type:
        print(f"[source_analyzer_real] error={result.error_type}")
    print(
        f"[source_analyzer_real] source_map_exists={result.source_map_exists} "
        f"protected_unchanged={result.protected_unchanged}"
    )
    print("[source_analyzer_real] STOP - revue humaine avant Phase 4.")
    return 0 if result.outcome == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
