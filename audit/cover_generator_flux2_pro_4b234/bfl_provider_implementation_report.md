# BFL provider implementation

## Differences found in the 4B.2.33 code

The 4B.2.33 report and the code agree that `CoverImageProvider` exists, `evaluate_paid_call` refuses a paid call while its foundation lock is on, and `DEFAULT_PAID_PROVIDER` is null. The report’s recommended fallback is `PAID_API_NO_VENDOR_SELECTED`.

The same code has no reservation ledger, no API-key gate, and no download check. `requests` is listed in `requirements.txt`, and the 4B.2.33 test forbids importing `requests` or `httpx` inside `app/cover`.

`book.json` is `print-review-v1`. The interior DOCX and PDF are `print-review-v1.1`. That split was already documented in 4B.2.33.

The indicative model string `flux_2_pro` is not the API identifier. The pinned identifier is `flux-2-pro`.

## What this phase added

`BlackForestLabsImageProvider` implements the existing contract. The default authorization is disabled, the dry-run flag is on, the price is unknown, and `LIVE_HTTP_ENABLED` is false. `evaluate_paid_call` is reused and was not loosened.

A reservation is an exclusive lock file plus a JSON ledger. One authorization can hold one reservation. An unknown outcome stays consumed. Nothing is retried.

Print pixels 1800×2700 and bleed pixels 1871×2771 are not legal API dimensions (not_multiple_of_16, above_4_megapixel_cap). The adapter can request 1664×2496 only after a later human authorization. It does not request them in this phase.

The historical modules `app/cover_engine.py`, `app/cover_builder.py`, `app/cover_renderer.py`, and `app/image_engine/` were not modified.
