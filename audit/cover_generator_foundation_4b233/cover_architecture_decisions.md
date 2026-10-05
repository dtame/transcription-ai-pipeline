# Cover architecture decisions — 4B.2.33

## Decision

The print cover is a new module, `app/cover`. The workshop cover stack stays in place and is not called.

## Why it is not an extension of the current engines

`app/cover_engine.py`, `app/cover_builder.py`, `app/cover_renderer.py`, and `app/image_engine/` already generate images or typographic covers. Several of those paths can call a local WebUI or a paid image API, write `project_state`, and produce one cover file inside a project's publication folder.

The print cover needs different guarantees:

- two separate pages, with no spine and no wraparound
- an author library shared across books
- a biography snapshot that does not follow later profile edits
- private contact data kept off the back cover
- a paid-call gate with an explicit budget
- no image, DOCX, or PDF during this phase

Folding that into the workshop engines would mix those behaviors with the interior publication path. `app/word_renderer` remains the interior renderer. `app/publication_docx_engine.py` and `app/publication_pdf_engine.py` remain the workshop publishers.

## Module boundaries

- `app/cover/author_library` stores reusable public profiles and a separate private contact file.
- `app/cover/content` defines description and biography states. It does not call a model.
- `app/cover/image_providers` defines the provider interface, the free-model rating, and the paid-call policy.
- `app/cover/renderer` defines geometry and the two-page export contract. Export methods refuse to write files.
- `app/cover/validation` builds a draft record from the book title and subtitle only.

## Storage

Author profiles live under `data/author_library`, outside `sortie/<project>`. A cover record for this book lives under `sortie/pastoral_retreat_v2_validation/publication/covers/draft_v1/`. `book.json` is not the cover store.

## What this phase does not claim

Local model licenses were not re-checked online. Hardware compatibility is a planning judgment. No professional cover quality is demonstrated, because no image was generated.
