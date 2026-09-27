"""
Classification des artefacts sous analysis/.

Trois classes distinctes :

    FORENSIC_ARTIFACT
        preuve d'appel / d'échec provider. Pas une analyse publiée.

    SEMANTIC_ANALYSIS_ARTIFACT
        transport ou résultat sémantique de fenêtre / consolidation.

    PUBLISHED_CANONICAL_ARTIFACT
        SourceMap canonique publié.

L'existence de analysis/ n'implique pas une publication Source Analyzer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

CLASS_FORENSIC = "FORENSIC_ARTIFACT"
CLASS_SEMANTIC = "SEMANTIC_ANALYSIS_ARTIFACT"
CLASS_PUBLISHED = "PUBLISHED_CANONICAL_ARTIFACT"
CLASS_UNKNOWN = "UNKNOWN_ANALYSIS_ARTIFACT"

FORENSIC_DIR_NAMES = frozenset(
    {
        "provider_forensics",
        "structured_output_forensics",
    }
)
FORENSIC_FILE_NAMES = frozenset(
    {
        "provider_http_envelope.json",
        "provider_raw_response.bin",
        "provider_raw_content.txt",
        "provider_response_forensics.json",
    }
)
SEMANTIC_DIR_NAMES = frozenset(
    {
        "windows",
        "consolidation",
        "hybrid",
        "reconstruction",
    }
)
SEMANTIC_FILE_NAMES = frozenset(
    {
        "transport.json",
        "result.json",
        "metadata.json",
    }
)
PUBLISHED_CANONICAL_NAMES = frozenset({"source_map.json"})


def classify_analysis_name(name: str) -> str:
    if name in FORENSIC_DIR_NAMES or name in FORENSIC_FILE_NAMES:
        return CLASS_FORENSIC
    if name in PUBLISHED_CANONICAL_NAMES:
        return CLASS_PUBLISHED
    if name in SEMANTIC_DIR_NAMES or name in SEMANTIC_FILE_NAMES:
        return CLASS_SEMANTIC
    return CLASS_UNKNOWN


def inspect_analysis_directory(analysis: Path) -> dict[str, Any]:
    """
    Invariant : pas de publication sémantique / canonique non autorisée.

    analysis/ peut exister s'il ne contient que des forensics classées.
    """
    root = Path(analysis)
    findings: list[dict[str, str]] = []
    forensic_dirs: list[str] = []
    if not root.exists():
        return {
            "analysis_exists": False,
            "ok": True,
            "forensic_dirs": [],
            "violations": [],
            "published_canonical_present": False,
            "semantic_artifact_present": False,
            "unknown_artifact_present": False,
        }
    if not root.is_dir():
        findings.append(
            {
                "path": str(root),
                "class": CLASS_UNKNOWN,
                "reason": "analysis_path_is_not_a_directory",
            }
        )
        return _finish(root, forensic_dirs, findings)

    for child in sorted(root.iterdir(), key=lambda item: item.name):
        classified = classify_analysis_name(child.name)
        if classified == CLASS_FORENSIC and child.is_dir():
            forensic_dirs.append(child.name)
            findings.extend(_inspect_forensic_tree(child))
            continue
        if classified == CLASS_PUBLISHED:
            findings.append(
                {
                    "path": str(child.relative_to(root)),
                    "class": CLASS_PUBLISHED,
                    "reason": "published_canonical_source_map",
                }
            )
            continue
        if classified == CLASS_SEMANTIC:
            findings.append(
                {
                    "path": str(child.relative_to(root)),
                    "class": CLASS_SEMANTIC,
                    "reason": "unauthorized_semantic_analysis_artifact",
                }
            )
            continue
        findings.append(
            {
                "path": str(child.relative_to(root)),
                "class": CLASS_UNKNOWN,
                "reason": "analysis_child_not_classified_as_forensic",
            }
        )
    return _finish(root, forensic_dirs, findings)


def _inspect_forensic_tree(directory: Path) -> list[dict[str, str]]:
    unexpected: list[dict[str, str]] = []
    root = directory
    while root.name not in FORENSIC_DIR_NAMES and root.parent != root:
        root = root.parent
    for path in sorted(directory.rglob("*")):
        if path.is_dir():
            continue
        classified = classify_analysis_name(path.name)
        if classified == CLASS_FORENSIC:
            continue
        if classified == CLASS_PUBLISHED:
            unexpected.append(
                {
                    "path": str(path.relative_to(root.parent)),
                    "class": CLASS_PUBLISHED,
                    "reason": "canonical_filename_inside_forensics",
                }
            )
            continue
        if classified == CLASS_SEMANTIC:
            unexpected.append(
                {
                    "path": str(path.relative_to(root.parent)),
                    "class": CLASS_SEMANTIC,
                    "reason": "semantic_filename_inside_forensics",
                }
            )
            continue
        unexpected.append(
            {
                "path": str(path.relative_to(root.parent)),
                "class": CLASS_UNKNOWN,
                "reason": "unclassified_file_inside_forensics",
            }
        )
    return unexpected


def _finish(
    root: Path, forensic_dirs: list[str], findings: list[dict[str, str]]
) -> dict[str, Any]:
    published = any(item["class"] == CLASS_PUBLISHED for item in findings)
    semantic = any(item["class"] == CLASS_SEMANTIC for item in findings)
    unknown = any(item["class"] == CLASS_UNKNOWN for item in findings)
    return {
        "analysis_exists": root.exists(),
        "ok": not findings,
        "forensic_dirs": forensic_dirs,
        "violations": findings,
        "published_canonical_present": published,
        "semantic_artifact_present": semantic,
        "unknown_artifact_present": unknown,
    }


def inspect_sortie_isolation(sortie: Path) -> dict[str, Any]:
    root = Path(sortie)
    projects: list[dict[str, Any]] = []
    if not root.exists():
        return {
            "sortie_exists": False,
            "ok": True,
            "projects": [],
            "source_maps": [],
            "violations": [],
        }
    source_maps = [str(path) for path in sorted(root.glob("*/analysis/source_map.json"))]
    for analysis in sorted(root.glob("*/analysis")):
        report = inspect_analysis_directory(analysis)
        report["project"] = analysis.parent.name
        report["analysis_path"] = str(analysis)
        projects.append(report)
    violations = [
        item
        for project in projects
        for item in project["violations"]
    ]
    return {
        "sortie_exists": True,
        "ok": not source_maps and all(project["ok"] for project in projects),
        "projects": projects,
        "source_maps": source_maps,
        "violations": violations,
    }


__all__ = [
    "CLASS_FORENSIC",
    "CLASS_PUBLISHED",
    "CLASS_SEMANTIC",
    "CLASS_UNKNOWN",
    "FORENSIC_DIR_NAMES",
    "FORENSIC_FILE_NAMES",
    "PUBLISHED_CANONICAL_NAMES",
    "SEMANTIC_DIR_NAMES",
    "SEMANTIC_FILE_NAMES",
    "classify_analysis_name",
    "inspect_analysis_directory",
    "inspect_sortie_isolation",
]
