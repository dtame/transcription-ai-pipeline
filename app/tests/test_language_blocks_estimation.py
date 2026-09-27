"""
Phase 3A.1.1 — estimation hors-ligne de la charge IA future (§27-28, §33
scénario 20).
"""

from __future__ import annotations

from app.language_blocks.builder import build_manifest
from app.language_blocks.estimation import (
    BATCH_SIZES,
    compute_ai_estimation,
)
from app.tests.language_blocks_fixtures import build_sequence, make_combined


def _manifest_with_needed_blocks(count: int):
    specs = []
    for index in range(count):
        specs.append({"language": "EN", "text": "hello good friend today number"})
        specs.append({"language": "FR", "text": f"bonjour numero {index}"})
    segments = build_sequence(specs)
    return build_manifest(make_combined(segments))


class TestEstimationIsFullyOffline:
    def test_estimation_never_touches_the_network(self, no_ai_network):
        """
        `no_ai_network` (app/tests/conftest.py) fait lever toute tentative de
        POST HTTP sortant de la couche IA : ce test réussit uniquement si
        compute_ai_estimation() ne déclenche jamais un tel appel.
        """
        manifest = _manifest_with_needed_blocks(3)
        estimation = compute_ai_estimation(manifest.blocks)

        assert estimation["blocks_needing_review"] == 3
        assert estimation["total_estimated_input_tokens"] > 0
        assert estimation["method"] in ("tiktoken", "heuristic_chars_per_token")


class TestBatchRequestCounts:
    def test_request_counts_use_ceiling_division(self):
        manifest = _manifest_with_needed_blocks(23)
        estimation = compute_ai_estimation(manifest.blocks)

        assert estimation["blocks_needing_review"] == 23
        assert set(estimation["batches"].keys()) == {str(size) for size in BATCH_SIZES}

        expected_requests = {1: 23, 5: 5, 10: 3, 20: 2, 50: 1}
        for size, expected in expected_requests.items():
            assert estimation["batches"][str(size)]["request_count"] == expected

    def test_content_tokens_identical_across_batch_sizes(self):
        """Le volume de contenu ne dépend jamais de la taille de lot choisie."""
        manifest = _manifest_with_needed_blocks(7)
        estimation = compute_ai_estimation(manifest.blocks)

        content_tokens = {
            batch["content_tokens"] for batch in estimation["batches"].values()
        }
        assert len(content_tokens) == 1
        assert content_tokens.pop() == estimation["total_estimated_input_tokens"]

    def test_smaller_batches_cost_more_system_prompt_overhead(self):
        manifest = _manifest_with_needed_blocks(11)
        estimation = compute_ai_estimation(manifest.blocks)

        overhead_by_size = {
            int(size): batch["system_prompt_tokens_total"]
            for size, batch in estimation["batches"].items()
        }
        ordered_sizes = sorted(overhead_by_size)
        overhead_values = [overhead_by_size[size] for size in ordered_sizes]
        assert overhead_values == sorted(overhead_values, reverse=True)


class TestEstimationWithNoBlocksNeeded:
    def test_zero_blocks_needing_review_yields_zero_requests(self):
        segments = build_sequence([{"language": "EN", "text": "hello good friend"}])
        manifest = build_manifest(make_combined(segments))

        estimation = compute_ai_estimation(manifest.blocks)

        assert estimation["blocks_needing_review"] == 0
        assert estimation["total_estimated_input_tokens"] == 0
        for batch in estimation["batches"].values():
            assert batch["request_count"] == 0
            assert batch["total_tokens"] == 0


class TestNoCostIsInvented:
    def test_estimation_payload_never_mentions_price(self):
        manifest = _manifest_with_needed_blocks(4)
        estimation = compute_ai_estimation(manifest.blocks)

        serialized_keys = set(estimation.keys()) | set(
            estimation["batches"]["1"].keys()
        )
        forbidden = {"cost", "price", "usd", "dollars"}
        assert not (serialized_keys & forbidden)
