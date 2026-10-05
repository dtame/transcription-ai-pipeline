"""Prepare the approved front image for a 6×9 bleed canvas. No new generation."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from PIL import Image

from app.cover.renderer.geometry import CoverGeometry
from app.cover_print_ready_4b235.guard import ApprovedImageHashError, CoverPrintReady4235Error


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_approved_image(path: Path, expected_sha256: str) -> str:
    if not path.is_file():
        raise CoverPrintReady4235Error(
            f"approved front image is missing: {path}. STOP. It was not replaced."
        )
    digest = sha256_file(path)
    if digest != expected_sha256:
        raise ApprovedImageHashError(
            f"approved image SHA-256 mismatch: {digest}. STOP. The image was not replaced."
        )
    return digest


def prepare_cover_image(
    source: Path,
    destination: Path,
    geometry: CoverGeometry,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    """Lanczos cover-fit. The source file is only read."""
    if source.resolve() == destination.resolve():
        raise CoverPrintReady4235Error("refusing to overwrite the approved original. STOP.")
    digest = assert_approved_image(source, expected_sha256)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        src_w, src_h = image.size
        ratio = src_w / src_h
        if abs(ratio - (2 / 3)) > 1e-6:
            raise CoverPrintReady4235Error(
                f"approved image ratio is {src_w}×{src_h}, not 2:3. STOP."
            )
        target_w = geometry.full_width_px
        target_h = geometry.full_height_px
        scale_w = target_w / src_w
        scale_h = target_h / src_h
        if scale_w >= scale_h:
            resized_w = target_w
            resized_h = math.ceil(src_h * target_w / src_w)
            uniform_scale = scale_w
        else:
            resized_h = target_h
            resized_w = math.ceil(src_w * target_h / src_h)
            uniform_scale = scale_h
        resized = image.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
        left = max(0, (resized_w - target_w) // 2)
        top = max(0, (resized_h - target_h) // 2)
        cropped = resized.crop((left, top, left + target_w, top + target_h))
        if cropped.size != (target_w, target_h):
            raise CoverPrintReady4235Error("prepared canvas does not match the bleed size")
        partial = destination.with_suffix(".partial.png")
        cropped.save(partial, format="PNG", dpi=(geometry.dpi, geometry.dpi))
        partial.replace(destination)
    if sha256_file(source) != digest:
        raise CoverPrintReady4235Error("the approved original changed during preparation. STOP.")
    crop_top = top
    crop_bottom = resized_h - target_h - top
    crop_left = left
    crop_right = resized_w - target_w - left
    return {
        "source": str(source).replace("\\", "/"),
        "destination": str(destination).replace("\\", "/"),
        "source_sha256": digest,
        "prepared_sha256": sha256_file(destination),
        "source_px": [src_w, src_h],
        "resized_px": [resized_w, resized_h],
        "canvas_px": [target_w, target_h],
        "uniform_scale": round(uniform_scale, 6),
        "fit": "cover",
        "stretch": False,
        "resample": "LANCZOS",
        "anchor": "center",
        "crop_px": {
            "left": crop_left,
            "top": crop_top,
            "right": crop_right,
            "bottom": crop_bottom,
        },
        "sharpened": False,
        "saturation_adjusted": False,
        "artistic_modification": False,
        "color_mode": "RGB",
        "dpi": geometry.dpi,
    }


__all__ = ["assert_approved_image", "prepare_cover_image", "sha256_file"]
