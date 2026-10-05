# One-time authorization lifecycle

Statuses: NOT_AUTHORIZED, AUTHORIZED, RESERVED, SUBMITTED, SUCCEEDED,
FAILED, OUTCOME_UNKNOWN, EXPIRED, CANCELLED.

NOT_AUTHORIZED is the only status this phase writes into the audit.
AUTHORIZED exists only inside temporary test ledgers.

Before a submission the lock checks the provider, model, resolution,
quality, format, prompt hash, image count, expiry, and the persisted
row. The transition AUTHORIZED → RESERVED is atomic. The planning
budget is held in the same write as the reservation row.

SUBMITTED is recorded before the mock exchange. A crash after RESERVED
or after SUBMITTED cannot submit a second time. Timeout and an
ambiguous response become OUTCOME_UNKNOWN. The authorization is not
released and `retry_count` stays 0.

Two threads share one ledger file. The exclusive lock admits one
reservation and one exchange.

When the provider does not return a verified invoice, `observed_cost_usd`
stays null and the reconciliation status is COST_RECONCILIATION_PENDING.
Token counts are not converted into a dollar amount.
