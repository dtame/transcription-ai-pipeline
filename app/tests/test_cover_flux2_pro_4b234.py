"""Phase 4B.2.34 offline tests. No provider socket."""

from __future__ import annotations

import pytest

from app.cover_flux2_pro_4b234.scenarios import CASE_NAMES, evaluate_cases


@pytest.fixture(scope="module")
def case_report():
    return evaluate_cases()


@pytest.mark.parametrize("case_name", CASE_NAMES)
def test_offline_case(case_name, case_report):
    case = next(item for item in case_report["cases"] if item["name"] == case_name)
    assert case["passed"], case["detail"]
    assert case_report["live_provider_calls"] == 0
    assert case_report["paid_cost_usd"] == 0


def test_required_matrix_is_present(case_report):
    assert case_report["failed"] == 0
    assert len(CASE_NAMES) >= 32
