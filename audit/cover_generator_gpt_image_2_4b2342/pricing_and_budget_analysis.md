# Pricing and budget

Consulted on 2026-10-04. No API call.

## What is billed

The pricing page bills tokens. A text-only generation can include text input tokens and image output tokens. Image input tokens apply when reference images are sent. This phase attaches none. Cached input rates are documented for the Responses API and are documented as not applying to `POST /v1/images/generations`.

Partial images add 100 output tokens each. This adapter does not stream, so that extra is not requested. Omitting it does not cap the final image.

## Published image-output estimates

These are the guide's rounded comparison cells. They exclude text tokens. They are not ceilings.

| Size | Low | Medium | High |
| --- | --- | --- | --- |
| 1024×1024 | 0.006 | 0.053 | 0.211 |
| 1024×1536 | 0.005 | 0.041 | 0.165 |
| 1536×1024 | 0.005 | 0.041 | 0.165 |

Custom sizes, including 1536×2304 and 2160×3840, have no cell in that table. Their full request estimate is unknown.

The selected first-test quality is medium at 1024×1536. The published image-output component is 0.041 USD. The guide calls `low` a draft setting and says final assets should be compared at higher settings. Medium is the explicit middle setting for a first look. High's published image-output component at the same size is 0.165 USD. Neither figure is a guaranteed invoice.

Text input is additional, at the rate printed beside the model, once the token count exists. The count is not known before the provider tokenizes the prompt.

## Why the call stays blocked

- No page states a maximum output-token count for a size and quality.
- The guide says a larger size can cost fewer output tokens than a smaller one, so pixel count is not a ceiling.
- The $15 and $30 output rates are both printed in the official pages, for different named models, with a sentence that the models can share a rate. That conflict means a token count would still not produce one invoice amount.
- The usage object is not confirmed for `gpt-image-2`, so a cost might not be observable after the call either.
- No Images API field was found that stops billing at a dollar amount.
- Rate limits cap throughput. They do not cap the price of one image.
- A local `max_budget_usd` reserves money in this repository's ledger. It does not bind OpenAI. Section 1.5 of the Services Agreement says usage-based fees are calculated by OpenAI. Section 6.6 allows a later price correction.

`TokenBillingPricing` therefore returns `estimated_cost_usd = null` and `verified_maximum_cost_usd = null`. The guard adds `billing_ceiling_not_guaranteed` and `estimated_cost_unknown`. A local budget of 1000 USD does not remove those reasons.

The reservation ledger, the one-shot lock, the ban on automatic retries, and the refusal to reuse the phase 4B.2.34.1 authorization are unchanged in spirit and are applied to this provider. No authorization file is written for a later automatic run.

## Print note for the selected size

1024×1536 is exact 2:3. Placed on the 6×9 trim it is about 170.67 ppi, with an enlargement of about 1.7578 toward 300 ppi. The bleed canvas needs a small cover-crop. Professional sharpness is not guaranteed. A later visual inspection decides whether a larger legal size is worth a separate, still-capped test. Those larger sizes have no published dollar cell, so they are not selected while the ceiling is unknown.
