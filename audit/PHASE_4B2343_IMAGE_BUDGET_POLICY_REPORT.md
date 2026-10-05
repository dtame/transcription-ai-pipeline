**PHASE 4B.2.34.3 — IMAGE BUDGET POLICY**

RESULT = PASS
PROVIDER CALLS = 0
PAID COST = 0 USD
DEFAULT POLICY = STRICT
EXPERIMENTAL POLICY = READY
EXPLICIT CONSENT = REQUIRED
ONE-TIME AUTHORIZATION = PASS
ATOMIC RESERVATION = PASS
CONCURRENCY SAFETY = PASS
NO AUTOMATIC RETRY = PASS
NO AUTOMATIC FALLBACK = PASS
COST ESTIMATE TRACKING = PASS
COST RECONCILIATION = READY
PRIMARY PROVIDER = OpenAI
PRIMARY MODEL = gpt-image-2
SECONDARY PROVIDER = Black Forest Labs
SECONDARY MODEL = flux-2-pro
ART DIRECTION = The Door Already Open
FIRST IMAGE CONFIGURATION = 1024 × 1536 / medium / PNG
FIRST IMAGE COUNT = 1
FIRST IMAGE AUTHORIZED = NO
IMAGE GENERATED = NO
COVER DOCX GENERATED = NO
COVER PDF GENERATED = NO
OFFLINE TESTS = 38 PASS / 0 FAIL
CANONICAL HASHES = MATCH
READY_TO_REQUEST_FIRST_IMAGE_AUTHORIZATION = YES

Project: pastoral_retreat_v2_validation. Book: The Life You Already Inherited. Interior: print-review-v1.1, 67 pages.
Canonical SHA-256: adde6e2344f4b94da0f7df183341885574e89abc90781c426459e850cc2b6550.

STRICT is unchanged. A missing verified maximum still refuses the call, including when experimental approval flags are present on a STRICT authorization. EXPERIMENTAL_AUTHORIZED is implemented as a one-time exception to that ceiling only. The process switch that allows a mock submission is off in production code. Tests turn it on inside temporary directories.

The published image-output cell for 1024×1536 medium remains 0.041 USD. Text-input tokens are unknown, so the full request estimate stays null. 0.041 USD is not stored as a verified maximum and is not an invoice. If a mock response has no billable cost, observed cost stays null and reconciliation stays COST_RECONCILIATION_PENDING.

The Door Already Open prompt is unchanged. Prompt SHA-256: 82f92129ec2d67666f288491c5d1b225272c46e6ec30f4f0daadaeef06cc3194. The prompt does not add title text. No effective authorization was written. The inactive plan identifies the prompt, the provider, the model, and the configuration, and leaves approval, planning budget, and acceptance false or empty.

OpenAIImageProvider and BlackForestLabsImageProvider are still the existing adapters. Experimental submission is wired only through the OpenAI path, and only behind the test switch. The Black Forest Labs adapter refuses EXPERIMENTAL_AUTHORIZED, so a failed OpenAI attempt cannot fall across.

Remaining limits: the provider still does not guarantee a dollar ceiling; the text-token component is unknown; usage token counts are not an invoice; experimental submission stays disabled until a later, separate user decision; this PASS does not authorize a real generation.

STOP. Do not call OpenAI, call Black Forest Labs, spend money, generate an image, or treat this phase as an authorization.
