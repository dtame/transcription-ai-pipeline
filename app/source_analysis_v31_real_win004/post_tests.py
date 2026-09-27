"""Delta de suite post-appel A.27. 0 provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_real_win004.constants import (
    BASELINE_ARTIFACT,
    PHASE,
    POST_TEST_ARTIFACT,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_real_win004.offline import complete_offline_after_canonical_fix


def parse_junit(path: Path) -> dict[str, Any]:
    tree = ElementTree.parse(path)
    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    passed = failed = skipped = errors = 0
    failing: list[str] = []
    for suite in suites:
        passed += int(suite.attrib.get("tests") or 0)
        failed += int(suite.attrib.get("failures") or 0)
        skipped += int(suite.attrib.get("skipped") or 0)
        errors += int(suite.attrib.get("errors") or 0)
        passed -= (
            int(suite.attrib.get("failures") or 0)
            + int(suite.attrib.get("errors") or 0)
            + int(suite.attrib.get("skipped") or 0)
        )
        for case in suite.findall("testcase"):
            node = f"{case.attrib.get('classname')}::{case.attrib.get('name')}"
            if case.find("failure") is not None or case.find("error") is not None:
                failing.append(node)
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "xfailed": 0,
        "summary": f"{passed} passed, {failed} failed, {skipped} skipped",
        "failing_node_ids": failing,
        "junit": str(path),
    }


def write_post_test_delta(
    project_name: str = PROJECT_NAME,
    *,
    post_junit: Path,
    focused: dict[str, Any] | None = None,
    sortie_dir: Path | None = None,
) -> Path:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    baseline = json.loads((audit / BASELINE_ARTIFACT).read_text(encoding="utf-8"))
    pre = baseline.get("full_suite") or {}
    post = parse_junit(post_junit)
    pre_fail = set(pre.get("failing_node_ids") or [])
    post_fail = set(post.get("failing_node_ids") or [])
    new_failures = sorted(post_fail - pre_fail)
    gone = sorted(pre_fail - post_fail)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "POST_CALL_TEST_DELTA",
        "provider_calls": 0,
        "pre_call_full": pre,
        "post_call_full": post,
        "focused_post": focused or {},
        "new_failures": new_failures,
        "resolved_failures": gone,
        "new_failure_count": len(new_failures),
        "source_map_published": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).is_file(),
        "gate": "PASS" if not new_failures else "FAIL",
    }
    return write_bytes_atomic(audit / POST_TEST_ARTIFACT, payload)


def refresh_report_with_post_tests(
    project_name: str = PROJECT_NAME,
    *,
    post_junit: Path,
    focused: dict[str, Any] | None = None,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    delta_path = write_post_test_delta(
        project_name,
        post_junit=post_junit,
        focused=focused,
        sortie_dir=sortie_dir,
    )
    delta = json.loads(delta_path.read_text(encoding="utf-8"))
    result = complete_offline_after_canonical_fix(
        project_name,
        sortie_dir=sortie_dir,
        tests=delta["post_call_full"]["summary"],
    )
    result.execution["post_tests"] = {
        "summary": delta["post_call_full"]["summary"],
        "new_failures": delta["new_failure_count"],
        "gate": delta["gate"],
        "focused": (focused or {}).get("summary"),
    }
    from app.source_analysis_v31_real_win004.writer import write_execution_artifacts
    from app.source_analysis_v31_real_win004.offline import load_saved_transport

    write_execution_artifacts(
        project_name,
        result,
        transport=load_saved_transport(project_name, sortie_dir=sortie_dir),
        sortie_dir=sortie_dir,
        tests=delta["post_call_full"]["summary"],
    )
    return delta


__all__ = [
    "parse_junit",
    "refresh_report_with_post_tests",
    "write_post_test_delta",
]
