"""Image-provider contract. Production code does not generate an image."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.cover.constants import IMAGE_GENERATION_AUTHORIZED


class CoverImageGenerationForbidden(RuntimeError):
    """Image generation is outside the foundation phase."""


@dataclass
class ImageGenerationRequest:
    provider_id: str
    model_name: str
    model_version: str | None
    prompt: str
    negative_prompt: str | None
    width_px: int
    height_px: int
    aspect_ratio: str
    seed: int | None
    image_count: int
    output_paths: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    embed_text: bool = False
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "aspect_ratio": self.aspect_ratio,
            "seed": self.seed,
            "image_count": self.image_count,
            "output_paths": list(self.output_paths),
            "metadata": dict(self.metadata),
            "embed_text": self.embed_text,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


@dataclass
class ProviderCapabilities:
    provider_id: str
    model_name: str
    model_version: str | None
    negative_prompt: bool
    seed: bool
    portrait_ratio: bool
    text_free_generation: bool
    local_execution: bool
    paid: bool
    max_images: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "portrait_ratio": self.portrait_ratio,
            "text_free_generation": self.text_free_generation,
            "local_execution": self.local_execution,
            "paid": self.paid,
            "max_images": self.max_images,
        }


class CoverImageProvider(ABC):
    """Interchangeable image backend. The renderer depends on this contract only."""

    provider_id = "unspecified"

    @abstractmethod
    def check_availability(self) -> dict[str, Any]:
        """Report whether the backend can be called. Do not download weights."""

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Describe supported controls. Do not generate."""

    @abstractmethod
    def estimate_cost(self, request: ImageGenerationRequest) -> dict[str, Any]:
        """Return a cost estimate. Unknown cost must stay unknown."""

    def generate(self, request: ImageGenerationRequest) -> dict[str, Any]:
        del request
        if not IMAGE_GENERATION_AUTHORIZED:
            raise CoverImageGenerationForbidden(
                "image generation is not authorized. No file will be written."
            )
        raise CoverImageGenerationForbidden("no production provider is selected")


def provider_contract_document() -> dict[str, Any]:
    return {
        "interface": "CoverImageProvider",
        "methods": [
            "check_availability",
            "get_capabilities",
            "estimate_cost",
            "generate",
        ],
        "request_fields": [
            "provider_id",
            "model_name",
            "model_version",
            "prompt",
            "negative_prompt",
            "width_px",
            "height_px",
            "aspect_ratio",
            "seed",
            "image_count",
            "output_paths",
            "metadata",
            "embed_text",
            "estimated_cost_usd",
        ],
        "result_fields": [
            "provider_id",
            "model_name",
            "model_version",
            "output_paths",
            "metadata",
            "license",
            "estimated_cost_usd",
            "actual_cost_usd",
            "error",
            "history",
        ],
        "text_baked_into_image": False,
        "production_fake_provider": False,
        "mocks_allowed_in": "tests_only",
        "generation_authorized": IMAGE_GENERATION_AUTHORIZED,
        "history": [],
    }


def validate_image_request(request: ImageGenerationRequest) -> None:
    if request.embed_text:
        raise CoverImageGenerationForbidden(
            "the generated cover image must not contain text"
        )
    if request.image_count < 1:
        raise CoverImageGenerationForbidden("image_count must be at least 1")
    if request.width_px < 1 or request.height_px < 1:
        raise CoverImageGenerationForbidden("image dimensions must be positive")


__all__ = [
    "CoverImageGenerationForbidden",
    "CoverImageProvider",
    "ImageGenerationRequest",
    "ProviderCapabilities",
    "provider_contract_document",
    "validate_image_request",
]
