# OpenAI adapter

`OpenAIImageProvider` implements `CoverImageProvider`. `BlackForestLabsImageProvider` is unchanged.

The default instance uses `TokenBillingPricing`, a disabled authorization, `dry_run=True`, and `phase_lock=True`. It refuses before a reservation and before the transport. The module does not import `urllib`. Tests inject a mock transport. There is no production fake provider.

`OPENAI_API_KEY` is read from the environment mapping passed to the provider. The value is placed only in the `Authorization` header of a call that has already passed the guard. It is not written to `book.json`, a cover record, the reservation ledger, a result object, or a prompt.

An image is marked generated only after the base64 payload decodes as a PNG of the requested width and height and the bytes just written hash to the same SHA-256. A corrupt payload, a remote URL, a missing `b64_json`, a non-200 status, or a timeout marks the reservation `outcome_unknown` and does not start another paid call.

The body sends `model`, `prompt`, `n=1`, `size`, `quality`, `output_format`, and `background=opaque`. It does not send a negative prompt, a seed, `stream`, `partial_images`, `response_format`, or a reference image. `disable_pup` belongs to Black Forest Labs and is not sent.
