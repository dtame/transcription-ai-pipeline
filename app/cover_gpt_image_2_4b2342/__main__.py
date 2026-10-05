"""python -m app.cover_gpt_image_2_4b2342"""

from __future__ import annotations

from app.cover_gpt_image_2_4b2342.runner import run_phase


def main() -> None:
    result = run_phase(write_artifacts=True)
    tests = result["offline_tests"]
    print(
        f"PHASE 4B.2.34.2 {result['result']} "
        f"decision={result['decision']} "
        f"tests={tests['passed']} pass / {tests['failed']} fail "
        f"provider_calls={result['provider_calls']} cost={result['paid_cost_usd']}"
    )
    if tests["failed_names"]:
        print("failed: " + ", ".join(tests["failed_names"]))


if __name__ == "__main__":
    main()
