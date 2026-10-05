# Print resolution strategy

Finished trim: 6.0 × 9.0 inches at 300 ppi.

Calculated trim: 1800 × 2700 px.
Calculated 3 mm bleed canvas: 1871 × 2771 px.
These two canvases are not sent to the API. Reasons: trim ['not_multiple_of_16', 'above_4_megapixel_cap']; bleed canvas ['not_multiple_of_16', 'above_4_megapixel_cap'].

Largest legal 2:3 generation size inside the documented 2048×2048 example cap: 1664 × 2496 px (4153344 pixels; cap 4194304).

Placement, if a later phase is authorized to generate:

1. Request that PNG with `disable_pup` true.
2. Scale it uniformly by about 1.1244 so it covers the bleed canvas.
3. Crop the overflow. Do not stretch 2:3 onto the bleed ratio.
4. The renderer adds type inside the safety inset. The image stays text-free.
5. Inspect sharpness before any print approval. This enlargement is not evidence of print quality.
6. Do not run a generative upscaler in this phase.
7. Do not change the interior format.

Request the largest legal 2:3 PNG. Place it on the bleed canvas with a uniform cover-crop. Do not stretch it to the bleed ratio. Inspect sharpness before any print file is approved.
