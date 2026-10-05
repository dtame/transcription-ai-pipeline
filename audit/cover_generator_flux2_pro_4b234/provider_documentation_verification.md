# FLUX.2 [pro] documentation verification

Verified on 2026-10-04. No generation, polling, download, or billing endpoint was called.

## Verified

| Item | Finding | Source |
| --- | --- | --- |
| Submit endpoint | `POST https://api.bfl.ai/v1/flux-2-pro` | https://docs.bfl.ai/api-reference/models/generate-or-edit-an-image-with-flux2-%5Bpro%5D |
| Pinned model id | `flux-2-pro` | Help center and FLUX.2 overview |
| Preview id, not selected | `flux-2-pro-preview` | FLUX.2 overview. Same request contract, moving weights. |
| Authentication | Header `x-key` | OpenAPI security scheme `APIKeyHeader` |
| Environment variable | `BFL_API_KEY` | Official quick start |
| Async submit response | `id`, `polling_url`, optional `cost`, `input_mp`, `output_mp` | OpenAPI `AsyncResponse` |
| Poll | `GET` the returned `polling_url`. Do not rewrite the host. | https://docs.bfl.ai/api_integration/integration_guidelines |
| Poll hosts | `api.bfl.ai`, `api.eu.bfl.ai`, `api.us.bfl.ai` | Integration guide |
| Ready result | `result.sample` | https://docs.bfl.ai/flux_2/flux2_text_to_image |
| Delivery host | `delivery.<region>.bfl.ai` | Integration guide |
| Signed URL lifetime | 10 minutes | Text-to-image guide |
| Output formats | jpeg, png, webp. Default in the schema is jpeg. This adapter requests png. | OpenAPI `OutputFormat` |
| Width and height | Integers, minimum 64 | OpenAPI `Flux2Inputs` |
| Edge multiple and area cap | Multiples of 16. Maximum 4 megapixels, example 2048×2048. | https://help.bfl.ai/articles/6944273991-what-are-the-flux-2-technical-specifications |
| Seed | Optional integer | OpenAPI |
| Prompt upsampling | On by default for [pro]. `disable_pup: true` keeps the prompt as written. | OpenAPI |
| Status values | Pending, Reasoning, Generating, Ready, Error, Request Moderated, Content Moderated, Task not found | https://docs.bfl.ai/api-reference/utility/get-result |
| Extra status in the guides | `Failed` is named in the quick start and is absent from the OpenAPI enum. Treated as terminal. | Quick start |
| HTTP errors | 400, 402, 403, 422, 429, 500, 503 | https://docs.bfl.ai/api_integration/errors |
| Active-task limit | 24 for most endpoints. 429 when exceeded. | Quick start |
| Negative prompt | Not a field of `Flux2Inputs` | OpenAPI |

## Unverified

- The exact USD amount for a 1664×2496 image. The pricing page says the price varies by resolution and points to a calculator.
- Whether “4 megapixels” means 4,000,000 pixels or the documented example 2048×2048 (4,194,304). The adapter uses the documented example as the cap.
- Whether `get_result` can issue a fresh delivery URL after the signed URL expires. The recovery strategy does not submit a new task.
- The batch parameter. Pricing mentions a batch multiplier. `Flux2Inputs` has no image-count field. One POST is one image.
- The maximum download size imposed by the provider. This project caps a download at 32 MiB.
- `https://bfl.ai/pricing/api/`, cited by the API terms as the fee page, returned HTTP 404 on 2026-10-04.

## Not followed

The integration guide shows an automatic retry on HTTP 429 and on network errors. This phase does not retry a request that might be billed.
