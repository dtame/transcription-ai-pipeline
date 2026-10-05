"""Three front-cover directions drawn from canonical chapter titles.

The prompts ask for a text-free image. FLUX.2 [pro] has no negative-prompt
field, so the exclusions are written in the positive prompt and the negative
prompt is kept only as an editorial note.
"""

from __future__ import annotations

from typing import Any, Mapping


class ArtDirectionError(ValueError):
    """The canonical book does not contain a title this direction cites."""


_EXCLUSIONS = (
    "no words, no letters, no numerals, no title, no subtitle, no author name, "
    "no logo, no barcode, no ISBN, no watermark, no signature, no cross, "
    "no crucifix, no stained glass, no halo, no angel, no church interior, "
    "no crowd, no celebrity face, no skeleton, no open tomb"
)


def build_front_cover_directions(book: Mapping[str, Any]) -> list[dict[str, Any]]:
    title = str(book.get("title") or "").strip()
    subtitle = str(book.get("subtitle") or "").strip()
    if title != "The Life You Already Inherited":
        raise ArtDirectionError("the canonical title is not the reference book")
    chapters = {
        str(chapter.get("title") or ""): chapter
        for chapter in book.get("chapters") or []
        if isinstance(chapter, Mapping)
    }
    known = set(chapters)
    for chapter in chapters.values():
        for section in chapter.get("sections") or []:
            if isinstance(section, Mapping) and section.get("title"):
                known.add(str(section["title"]))
    cited = {
        "unlearning": _require(chapters, "Unlearning What Was Handed Down"),
        "flesh": _require(chapters, "Flesh and Bone: The Resurrection You Inherit"),
        "power": _require(chapters, "Hebrews 2: Death Already Destroyed"),
        "access": _require(chapters, "Access, Not Achievement"),
        "body": _require(chapters, "Spirit, Soul and Body"),
        "eater": _require(chapters, "Out of the Eater"),
        "laws": _require(chapters, "Laws You Gave Yourself"),
    }
    directions = [
        _direction(
            number=1,
            name="The door already open",
            intention=(
                "A quiet domestic threshold, already open, with light already in the room. "
                "The picture argues access rather than achievement."
            ),
            themes=[
                title,
                subtitle,
                cited["access"],
                "The Power Is Already Inside",
                "Operating What You Have",
            ],
            palette=["#E7D7C1 warm plaster", "#5C4033 walnut", "#E0A15A lamp flame", "#3E4A3A olive shadow"],
            elements=[
                "an interior door standing open",
                "a small oil lamp already lit on a plain table",
                "an even plaster wall",
            ],
            composition=(
                "Vertical 2:3. The upper third is an even plaster field reserved for the title. "
                "The doorway and lamp occupy the lower two-thirds, slightly left of center."
            ),
            title_space="Upper third, low detail, #E7D7C1, dark type to be added by the renderer.",
            contrast="Light field over a darker walnut and olive base.",
            risks=[
                "The lamp can slip into generic spirituality.",
                "The doorway can become a church door.",
                "Wood grain can resemble letters.",
            ],
            prompt=(
                "Editorial photograph for a book cover, vertical two-to-three ratio. "
                "A plain domestic doorway already standing open, warm dawn light already inside the room, "
                "a small oil lamp already burning on a walnut table. Upper third is an even plaster wall "
                "in exact color #E7D7C1 with no objects and no texture that resembles writing. "
                "Flame in #E0A15A, shadows in #3E4A3A. Photographed, calm, sharp, no people. "
                f"{_EXCLUSIONS}."
            ),
        ),
        _direction(
            number=2,
            name="Linen, bone, and a living olive",
            intention=(
                "Body and life in the same still life. Cloth, pale stone, and a living branch, "
                "without a tomb or a spectacle."
            ),
            themes=[
                cited["flesh"],
                cited["body"],
                "Life Older, Better, Everlasting",
                subtitle,
            ],
            palette=["#F3EDE4 bone", "#C8C2B8 stone", "#6B7F5A olive leaf", "#1C1C1C ink shadow"],
            elements=[
                "folded undyed linen",
                "a smooth pale stone",
                "one living olive branch",
            ],
            composition=(
                "Vertical still life. The upper third is empty bone-colored cloth. "
                "The branch and stone sit in the lower half, with wide quiet margins."
            ),
            title_space="Upper third of undyed linen, #F3EDE4, reserved for later type.",
            contrast="Pale ground, one deep green accent, a small ink shadow.",
            risks=[
                "Linen can be read as a shroud.",
                "The branch can become a ceremonial palm.",
                "Stone can suggest a headstone.",
            ],
            prompt=(
                "Editorial still-life photograph, vertical two-to-three ratio, for a book about inherited "
                "resurrection life and the whole person: spirit, soul, and body. Folded undyed linen, "
                "a smooth pale stone, and one living olive branch with green leaves. No tomb, no skeleton, "
                "no grave, no shroud ritual. Upper third is an even field of linen in exact color #F3EDE4. "
                "Leaf in #6B7F5A. Soft north light, sharp cloth texture, generous empty margin. "
                f"{_EXCLUSIONS}."
            ),
        ),
        _direction(
            number=3,
            name="Honey from heavy ground",
            intention=(
                "Something nourishing coming out of what was meant to be hard. "
                "A metaphor from the chapter title, not a scene of a lion or an angel."
            ),
            themes=[
                cited["eater"],
                "Meant for Evil",
                cited["unlearning"],
                cited["laws"],
            ],
            palette=["#2A2724 charcoal soil", "#D4A017 honey", "#F6F1E7 cream", "#8C4A32 muted clay"],
            elements=[
                "dark cracked earth across the lower half",
                "broken honeycomb with visible honey",
                "a calm cream field above",
            ],
            composition=(
                "Vertical. Dark cracked ground fills the bottom half. Honeycomb sits just below the middle. "
                "The upper third is a smooth cream field for the title."
            ),
            title_space="Upper third, even #F6F1E7, no honeycomb and no cracks.",
            contrast="Dark lower mass, bright honey accent, light title field.",
            risks=[
                "Honeycomb can look like a food advertisement.",
                "The dark ground can turn ominous or horror-like.",
                "A lion or an angel would illustrate a different story than the chapter's pastoral teaching.",
            ],
            prompt=(
                "Editorial still-life photograph, vertical two-to-three ratio. Dark cracked earth in #2A2724 "
                "fills the lower half. A broken piece of honeycomb rests on that ground, honey glowing in "
                "exact color #D4A017. The upper third is a smooth empty field in exact color #F6F1E7 with "
                "no objects. No lion, no animal, no angel, no wings, no people. Natural light, sharp, "
                "restrained, not glossy advertising. "
                f"{_EXCLUSIONS}."
            ),
        ),
    ]
    for direction in directions:
        for theme in direction["themes"]:
            if theme in {title, subtitle}:
                continue
            if theme not in known:
                raise ArtDirectionError(theme)
    return directions


def _require(chapters: Mapping[str, Any], title: str) -> str:
    if title not in chapters:
        raise ArtDirectionError(title)
    return title


def _direction(**fields: Any) -> dict[str, Any]:
    fields["negative_prompt"] = (
        "text, letters, numbers, title, subtitle, author name, logo, barcode, ISBN, "
        "watermark, signature, cross, stained glass, halo, angel, church, crowd, skeleton, tomb, lion"
    )
    fields["negative_prompt_supported_by_flux2_pro"] = False
    fields["negative_prompt_transmitted"] = False
    fields["image_generated"] = False
    return fields


__all__ = ["ArtDirectionError", "build_front_cover_directions"]
