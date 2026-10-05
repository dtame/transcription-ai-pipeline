# Official pricing

Status: UNVERIFIED as a maximum. Consulted on 2026-10-04. No billing endpoint and no generation endpoint was called.

## Sources

- https://docs.bfl.ai/quick_start/pricing
- https://help.bfl.ai/articles/7986977817-what-are-the-costs-associated-with-using-your-models
- https://docs.bfl.ai/flux_2/flux2_overview
- https://bfl.ai/legal/flux-api-service-terms
- Fee URL named in the API terms: https://bfl.ai/pricing/api/ — HTTP_404_ON_2026_10_04

## What is published for FLUX.2 [pro]

| Item | Published statement |
| --- | --- |
| Unit | 1 credit = 0.01 USD. Pricing is the same for the API and the Playground. |
| Text-to-image | “from $0.03/MP” |
| Image editing | “from $0.045/MP” |
| Resolution effect | “FLUX.2 pricing scales with output resolution.” |
| Rounding | “Resolution always rounds UP to the next megapixel. For example, 1920×1080 = 2.07MP → charged as 3MP.” |
| Klein, not Pro | The first megapixel is a flat rate and each additional megapixel adds to it. The worked Klein 4B example is $0.014 + $0.001 = $0.015 for 2MP. |
| Calculator | “Use the pricing calculator for exact costs.” |
| Contract | Fees are the then-current prices. The API and the models may be changed at the company’s discretion. |

The words “from $0.03” are a floor. They are not used as a maximum. The additional-megapixel rate for [pro] is not published. The Klein formula is not applied to [pro].

The overview table says [pro] is “from $0.03 / MP” and [flex] is “$0.06 / MP”. The help-center cost article lists [flex] as “$0.05/MP”. Those two official pages disagree about [flex]. That disagreement is not used to invent a [pro] rate.

The static pricing page fetched on 2026-10-04 showed a calculator whose visible rate was a FLUX 3 image price. It did not publish a static dollar amount for one 1632 × 2448 `flux-2-pro` image.

## Selected image

1632 × 2448 = 3995136 pixels = 3.995136 decimal megapixels.

The published round-up charges that as 4 megapixels. Dividing by 1024 × 1024 and rounding up also yields 4. The help center’s label “1024×1024 = 1 megapixel” conflicts with a decimal ceiling of 1.048576, which is 2. The ceiling is kept because truncation would bill the published 2.07MP example as 2MP.

The dollar amount for those 4 billed megapixels is not determined. 0.03 × 4 = 0.12 is not a verified maximum.

A budget chosen by the user does not, by itself, limit what the provider charges. The API terms point at then-current prices, and the fee URL returned HTTP 404.

## If a later call is still wanted

Ask Black Forest Labs for the written maximum, in USD, of one text-to-image request to `flux-2-pro` at 1632 × 2448, including rounding. Until that figure exists, the estimator refuses the call.

FLUX.2 [klein] 4B publishes “$0.014 + $0.001/MP” on the model overview, together with the same round-up example. That is a different model and it is not selected. FLUX.2 [flex] is not a safer substitute while its two official rates disagree. FLUX.1 Kontext [pro] is a fixed $0.04 per image at about 1MP and is not the chosen model.
