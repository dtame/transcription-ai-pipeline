# Budget policy design — phase 4B.2.34.3

STRICT remains the default. An authorization without `policy_mode` is STRICT.
STRICT still refuses a paid call when `verified_maximum_cost_usd` is unknown.
Approval flags for the experimental mode do not weaken STRICT.

EXPERIMENTAL_AUTHORIZED waives only `billing_ceiling_not_guaranteed` and
`estimated_cost_unknown`, and only when every other lock passes and the
process explicitly enables experimental submission. That switch is off
(`experimental_submission_enabled=False`).

The waiver does not remove provider, model, resolution, quality, format,
prompt hash, image count, expiry, cancellation, dry-run, API key, phase
lock, or one-time use checks. Selecting the mode is not consent. An API
key is not consent. A previous approval is bound to one authorization id.

The planning budget is an application hold. It is not a provider ceiling.
The published 0.041 USD cell is the image-output component for 1024×1536
medium. It is not `estimated_cost_usd`, not `observed_cost_usd`, and not
`verified_maximum_cost_usd`. Text-input tokens stay unknown.

Reservations stay on the existing `ReservationLedger` and its exclusive
lock file. Authorization rows live in the same JSON document. There is
no second reservation system.

OpenAI is the only adapter with an experimental submission path, and
that path is reached only when the test switch is on. Black Forest Labs
rejects `EXPERIMENTAL_AUTHORIZED` so it cannot become an automatic
fallback. This phase does not create an effective authorization and
does not call either provider.

Project `pastoral_retreat_v2_validation`. Book `The Life You Already Inherited`. Interior `print-review-v1.1`, 67 pages.
Art direction: The Door Already Open. The approved prompt is unchanged.
