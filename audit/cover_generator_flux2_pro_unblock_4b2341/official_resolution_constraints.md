# Official resolution constraints

Consulted on 2026-10-04. No generation request was sent.

## Sources

- https://help.bfl.ai/articles/6944273991-what-are-the-flux-2-technical-specifications
- https://help.bfl.ai/articles/8916739058-what-aspect-ratios-and-output-dimensions-are-supported
- https://docs.bfl.ai/api-reference/models/generate-or-edit-an-image-with-flux2-%5Bpro%5D

## What the pages state

| Constraint | Official statement |
| --- | --- |
| Minimum | 64 × 64 pixels. OpenAPI `minimum: 64` on width and height. |
| Maximum | 4 megapixels, with 2048 × 2048 given as the example. |
| Step | Width and height must be multiples of 16. |
| Default | 1024 × 1024. |
| Aspect ratio | Any. Portrait is allowed. There is no separate portrait limit. |
| Over 4MP | “Images over 4MP are automatically resized.” The page does not promise a rejection. |
| Below 64 | Schema validation. The errors page says an invalid body returns HTTP 422. |
| Not a multiple of 16 | Required by the help center. The published OpenAPI schema does not repeat the rule, and the pages read do not name the HTTP status for that case. |
| Quality note | The help center recommends staying at or below 2MP for quality and speed. |

## How “4 megapixels” is applied

The billing article treats 1920 × 1080 as 2.07MP, which is pixels / 1,000,000. On that decimal reading, 4 megapixels is 4,000,000 pixels.

The same help center calls 2048 × 2048 the maximum example. That square is 4194304 pixels, above 4,000,000. The phase does not send it.

The previous candidate 1664 × 2496 is 4153344 pixels. It is above 4,000,000 and is refused before any call. Problems: ['above_4_000_000_pixel_cap'].

The local validator also refuses a size the API might otherwise accept and silently resize. A silent resize could change the billed output.

## Selected size

1632 × 2448 = 3995136

width / height = 0.666667

Exact 2:3: True.
