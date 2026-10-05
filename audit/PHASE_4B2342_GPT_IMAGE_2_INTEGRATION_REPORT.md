**PHASE 4B.2.34.2 — GPT IMAGE 2 INTEGRATION**

RESULT = BLOCKED
PROVIDER CALLS = 0
PAID COST = 0 USD
PRIMARY PROVIDER = OpenAI
PRIMARY MODEL = gpt-image-2
SECONDARY PROVIDER = Black Forest Labs
SECONDARY MODEL = flux-2-pro
API DOCUMENTATION = VERIFIED WITH GAPS
COMMERCIAL USE = VERIFIED, NOT A LEGAL CERTIFICATION
API ADAPTER = IMPLEMENTED, SEALED
SELECTED RESOLUTION = 1024 × 1536
SELECTED QUALITY = medium
OUTPUT FORMAT = png
ESTIMATED COST PER IMAGE = 0.041 USD published image-output component only; full request estimate UNKNOWN
VERIFIED MAXIMUM COST = UNKNOWN
BUDGET GUARD = PASS
ART DIRECTION = The Door Already Open
IMAGE GENERATED = NO
FRONT COVER GENERATED = NO
BACK COVER GENERATED = NO
COVER DOCX GENERATED = NO
COVER PDF GENERATED = NO
OFFLINE TESTS = 34 PASS / 0 FAIL
CANONICAL HASHES = MATCH
READY_FOR_FIRST_IMAGE_TEST = NO
REMAINING BLOCKERS = BLOCKED_BILLING_CEILING, TOKEN_MAXIMUM_NOT_GUARANTEED_BEFORE_REQUEST, USAGE_FIELD_NOT_CONFIRMED_FOR_GPT_IMAGE_2, PER_TOKEN_RATE_TABLES_CONFLICT

Project: pastoral_retreat_v2_validation. Book: The Life You Already Inherited. Interior: print-review-v1.1, 67 pages. Canonical SHA-256: adde6e2344f4b94da0f7df183341885574e89abc90781c426459e850cc2b6550.

`OpenAIImageProvider` sits on `CoverImageProvider`. The Black Forest Labs adapter is still installed and still sealed. The direct Images endpoint is `POST https://api.openai.com/v1/images/generations` with model `gpt-image-2`. The snapshot `gpt-image-2-2026-04-21` is recorded and not sent. No conversational model is added.

1024×1536 is the documented portrait size, exact 2:3, and the only portrait candidate with a published image-output estimate. On the 6×9 trim that image is about 170.67 ppi. The enlargement toward 300 ppi is about 1.7578. Sharpness is not guaranteed. Larger legal sizes have no published dollar cell and were not selected. FLUX pixel limits were not reused.

The guide's medium cell for this size is 0.041 USD of image output, excluding text tokens. That cell is an estimate. The pricing page and the image guide do not agree on a single output-token rate, and no pre-request token maximum was found. A local budget is not an OpenAI cap. The guard therefore refuses every paid call, including a call whose local budget is far above the published cell. No persistent authorization was written. The phase 4B.2.34.1 authorization is refused if it is presented again.

The pictorial prompt approved for The Door Already Open is unchanged. It asks for no title, no author name, and no barcode. The Cover Renderer would add type later. It does not run in this phase. Author biography stays MISSING_OPTIONAL. The book description stays NOT_STARTED.

STOP. Do not call the API, spend money, generate an image, download a model, or produce a cover until a verified per-image maximum exists and a separate explicit authorization is given.
