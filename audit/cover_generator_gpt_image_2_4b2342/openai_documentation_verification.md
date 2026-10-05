# OpenAI documentation verification

Consulted on 2026-10-04. No API call. No account inspection.

## Sources

- https://developers.openai.com/api/docs/models/gpt-image-2
- https://developers.openai.com/api/docs/guides/image-generation
- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/reference/resources/images/methods/generate
- https://developers.openai.com/api/docs/guides/image-prompting
- https://openai.com/policies/services-agreement/
- https://openai.com/policies/service-terms/

## Confirmed

- Model id: `gpt-image-2`. Snapshot also listed: `gpt-image-2-2026-04-21`. This adapter sends the alias the phase names, and records the snapshot without sending it.
- Direct generation endpoint: `POST https://api.openai.com/v1/images/generations`.
- The image guide says the Image API is the choice for one image from one prompt. The Responses API adds a conversational model and is not used.
- Authentication in the reference curl: `Authorization: Bearer $OPENAI_API_KEY`.
- Generation parameters read on the reference: `model`, `prompt` (maximum 32,000 characters), `n` (1 to 10), `size`, `quality`, `output_format` (`png`, `jpeg`, `webp`), `output_compression` (jpeg and webp), `background` (`transparent`, `opaque`, `auto`), `moderation` (`low`, `auto`), `stream`, `partial_images` (0 to 3), `user`.
- `response_format` and `style` are documented as unsupported for GPT image models. They are not sent.
- GPT Image models return base64 in `data[].b64_json`. A URL response is documented as unsupported for those models.
- Qualities for `gpt-image-2`: `low`, `medium`, `high`, and `auto`. `xhigh` and `max` are documented for the 2.5 models.
- Size constraints for `gpt-image-2`: both edges multiples of 16, neither edge above 3,840, long-to-short ratio at most 3:1, total pixels from 655,360 through 8,294,400.
- Popular sizes include `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, `2048x1152`, `3840x2160`, and `2160x3840`.
- The prompting guide says outputs with more than 3,686,400 pixels (`2560x1440`) are experimental.
- Default output format in the guide: `png`.
- `partial_images` adds 100 image output tokens per partial. This adapter does not stream.
- Cached input pricing applies to the Responses API image tool and does not apply to direct Images API requests.
- Rate limits on the model page, images per minute: Free not supported; tier 1 is 5; tier 2 is 20; tier 3 is 50; tier 4 is 150; tier 5 is 250. Tokens per minute are listed beside those tiers. A rate limit is not a per-image dollar cap.
- The guide says organization verification may be required before GPT Image models can be used.
- The guide says not to retry quota errors or `image_generation_user_error` automatically. This adapter retries nothing.
- Pricing page, in the table that names `gpt-image-2`, per 1M tokens: image input $4.00, cached image input $1.00, image output $15.00, text input $2.50, cached text input $0.625.
- The guide's comparison table gives rounded image-output estimates for `1024x1024`, `1024x1536`, and `1536x1024` at low, medium, and high. It says to still account for text input tokens. It says a larger non-square size can use fewer output tokens than a smaller size.
- Services Agreement, effective January 1, 2026: the customer owns Output, and OpenAI assigns its interest in Output to the customer. Section 1.5 says usage-based fees are calculated by OpenAI. Section 6.6 says price changes take effect fourteen days after they are posted, and that OpenAI may correct pricing errors after an invoice.

## Not confirmed

- Whether this OpenAI organization has completed API Organization Verification. The phase did not open the account.
- Whether `gpt-image-2` returns `usage`. The reference schema says the usage object is for `gpt-image-1` only. A curl example that includes `usage` names `gpt-image-2.5-flare`, not `gpt-image-2`.
- A token count, or a dollar maximum, that is guaranteed before the request for a chosen size and quality. The published dollar cells are estimates.
- A request field that tells the provider to stop at a dollar amount. None was found on the Images generation reference.
- Which output-token rate is the invoice rate. The pricing page prints $15 beside `gpt-image-2` and also prints $30 for `gpt-image-2.5`. The guide states the $30 schedule for 2.5 and says the models can share the same price per image output token.
- That the character limit of 32,000 is a token ceiling. It is a character ceiling.
- A Canada-specific output clause. None was found on the pages read.
- That the Services Agreement names printed books. It does not.

## Adapter choice

One text prompt, one image, no reference image, no conversational model. The call, when a later phase unlocks it, is `POST /v1/images/generations`.
