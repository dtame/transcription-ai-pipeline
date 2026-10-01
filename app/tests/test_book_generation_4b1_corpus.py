"""Phase 4B.1 real-corpus offline gates. 0 réseau. Does not write book.json."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.book_generation.constants import (
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    VALIDATION_PROJECT_NAME,
)
from app.book_generation.errors import BookGenerationBlocked
from app.book_generation.identity import load_production_inputs
from app.book_generation.paths import book_path
from app.book_generation.writer import production_book_absent
from app.editorial_planning.pipeline import load_published_editorial_plan
from app.editorial_planning.writer import editorial_plan_path
from app.source_analysis.writer import source_map_path


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _production_present() -> bool:
    return (
        editorial_plan_path(VALIDATION_PROJECT_NAME).is_file()
        and source_map_path(VALIDATION_PROJECT_NAME).is_file()
    )


@pytest.mark.skipif(not _production_present(), reason="production artifacts absent")
class TestProductionIdentity:
    def test_reads_published_plan_not_a35_candidate(self):
        plan, raw, digest, path = load_published_editorial_plan(VALIDATION_PROJECT_NAME)
        assert path == editorial_plan_path(VALIDATION_PROJECT_NAME)
        assert digest.lower() == EXPECTED_EDITORIAL_PLAN_SHA256.lower()
        assert plan.selected_title
        assert "editorial_plan_candidate" not in str(path)

    def test_identity_gate(self):
        inputs = load_production_inputs(VALIDATION_PROJECT_NAME)
        assert inputs.plan_sha256.lower() == EXPECTED_EDITORIAL_PLAN_SHA256.lower()
        assert inputs.source_map_sha256.lower() == EXPECTED_SOURCE_MAP_SHA256.lower()
        assert inputs.status == "PASS"

    def test_mismatch_blocked(self, monkeypatch):
        from app.book_generation import identity as identity_mod

        monkeypatch.setattr(
            identity_mod, "EXPECTED_EDITORIAL_PLAN_SHA256", "0" * 64
        )
        with pytest.raises(BookGenerationBlocked):
            load_production_inputs(VALIDATION_PROJECT_NAME)

    def test_book_json_not_published(self):
        assert production_book_absent(VALIDATION_PROJECT_NAME)
        assert book_path(VALIDATION_PROJECT_NAME).is_file() is False


@pytest.mark.skipif(not _production_present(), reason="production artifacts absent")
def test_build_bundle_offline(tmp_path: Path):
    from app.book_generation.audit_writer import write_audit_bundle
    from app.book_generation.runner import build_bundle

    bundle = build_bundle(
        project_name=VALIDATION_PROJECT_NAME,
        tests="pytest 4b1 corpus",
        test_delta={"new_failure_count": 0},
    )
    assert bundle["header"]["real_provider_calls"] == 0
    assert bundle["header"]["book_json"] == "NOT PUBLISHED"
    assert bundle["header"]["ready_for_real_book_generation"] == "NO"
    assert bundle["fakeai"]["status"] == "PASS"
    assert bundle["preflight_ok"] is True
    written = write_audit_bundle(bundle, root=tmp_path, tests="pytest")
    assert written["report"].is_file()
    assert (tmp_path / "audit" / "book_generator_4b1").is_dir()
