"""Preliminary local-model compatibility. No weights are downloaded or run."""

from __future__ import annotations

from typing import Any

from app.cover.constants import COMPATIBILITY_RATINGS

# Planning thresholds in GiB. They are not measurements and not vendor-verified
# during this offline phase.
_FLUX_VRAM_LIKELY = 16.0
_FLUX_VRAM_OPTIMIZED = 8.0
_FLUX_CPU_RAM = 32.0
_SD35_VRAM_LIKELY = 12.0
_SD35_VRAM_OPTIMIZED = 8.0
_SD35_CPU_RAM = 24.0


def model_catalog() -> list[dict[str, Any]]:
    return [
        {
            "priority": 1,
            "model_name": "FLUX.1 Schnell",
            "model_id": "flux.1-schnell",
            "candidate_only": True,
            "selected": False,
            "parameter_class": "about_12B",
            "vram_likely_gib": _FLUX_VRAM_LIKELY,
            "vram_optimized_gib": _FLUX_VRAM_OPTIMIZED,
            "cpu_ram_gib": _FLUX_CPU_RAM,
            "license_status": "UNVERIFIED_OFFLINE",
            "license_note": (
                "Apache-2.0 is commonly published for FLUX.1 [schnell]. "
                "That claim was not re-checked against upstream in this offline phase."
            ),
            "commercial_use": "UNVERIFIED_OFFLINE",
            "windows_compatibility": "PROBABLE_NOT_DEMONSTRATED",
            "python_integration": "NOT_INSTALLED",
            "portrait_ratio": "PROBABLE_NON_NATIVE_RESOLUTION",
            "text_free_generation": "REQUIRED_NOT_DEMONSTRATED",
            "upscaling_to_print_pixels": "REQUIRED_NOT_DEMONSTRATED",
            "local_cost_usd_per_image": 0,
            "quality_for_professional_cover": "NOT_DEMONSTRATED",
        },
        {
            "priority": 2,
            "model_name": "Stable Diffusion 3.5 Medium",
            "model_id": "stable-diffusion-3.5-medium",
            "candidate_only": True,
            "selected": False,
            "parameter_class": "about_2.5B",
            "vram_likely_gib": _SD35_VRAM_LIKELY,
            "vram_optimized_gib": _SD35_VRAM_OPTIMIZED,
            "cpu_ram_gib": _SD35_CPU_RAM,
            "license_status": "UNVERIFIED_OFFLINE",
            "license_note": (
                "A Stability community license is commonly published for SD 3.5 Medium. "
                "Commercial terms were not re-checked in this offline phase."
            ),
            "commercial_use": "UNVERIFIED_OFFLINE",
            "windows_compatibility": "PROBABLE_NOT_DEMONSTRATED",
            "python_integration": "NOT_INSTALLED",
            "portrait_ratio": "PROBABLE_NON_NATIVE_RESOLUTION",
            "text_free_generation": "REQUIRED_NOT_DEMONSTRATED",
            "upscaling_to_print_pixels": "REQUIRED_NOT_DEMONSTRATED",
            "local_cost_usd_per_image": 0,
            "quality_for_professional_cover": "NOT_DEMONSTRATED",
        },
    ]


def rate_model(spec: dict[str, Any], hardware: dict[str, Any]) -> str:
    if hardware.get("system_ram_gib") is None or hardware.get("discrete_gpu") is None:
        return "INSUFFICIENT_INFORMATION"
    if hardware.get("discrete_gpu") is True and hardware.get("dedicated_vram_gib") is None:
        return "INSUFFICIENT_INFORMATION"
    rating = _rate_known(spec, hardware)
    if rating not in COMPATIBILITY_RATINGS:
        raise ValueError(f"unexpected rating {rating}")
    return rating


def evaluate_local_models(hardware: dict[str, Any]) -> dict[str, Any]:
    evaluations = []
    for spec in model_catalog():
        rating = rate_model(spec, hardware)
        evaluations.append(
            {
                **spec,
                "compatibility": rating,
                "justification": _justify(spec, hardware, rating),
                "weights_downloaded": False,
                "generation_executed": False,
                "preliminary": True,
                "professional_quality_demonstrated": False,
            }
        )
    recommendation = recommend(evaluations)
    return {
        "preliminary": True,
        "generation_executed": False,
        "weights_downloaded": False,
        "license_verification": "UNVERIFIED_OFFLINE",
        "evaluations": evaluations,
        **recommendation,
    }


def recommend(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    rank = {
        "LIKELY_COMPATIBLE": 3,
        "POSSIBLY_COMPATIBLE_WITH_OPTIMIZATION": 2,
        "INSUFFICIENT_INFORMATION": 1,
        "NOT_RECOMMENDED": 0,
    }
    ordered = sorted(evaluations, key=lambda item: item["priority"])
    viable = [item for item in ordered if rank[item["compatibility"]] >= 2]
    if not viable:
        return {
            "recommended_free_model": "NONE",
            "recommended_fallback": "PAID_API_NO_VENDOR_SELECTED",
            "revisit_first_if_hardware_changes": "Stable Diffusion 3.5 Medium",
            "recommendation_note": (
                "Neither free candidate is recommended on the measured hardware. "
                "No paid vendor is selected. Quality remains undemonstrated until "
                "a real image is generated and inspected."
            ),
        }
    best = max(viable, key=lambda item: rank[item["compatibility"]])
    others = [item for item in ordered if item["model_name"] != best["model_name"]]
    fallback = others[0]["model_name"] if others else "PAID_API_NO_VENDOR_SELECTED"
    if others and rank[others[0]["compatibility"]] < 2:
        fallback = "PAID_API_NO_VENDOR_SELECTED"
    return {
        "recommended_free_model": best["model_name"],
        "recommended_fallback": fallback,
        "revisit_first_if_hardware_changes": None,
        "recommendation_note": (
            "Compatibility is preliminary. No image was generated, so professional "
            "cover quality is not demonstrated."
        ),
    }


def _rate_known(spec: dict[str, Any], hardware: dict[str, Any]) -> str:
    ram = float(hardware["system_ram_gib"])
    if hardware.get("discrete_gpu") is True:
        vram = float(hardware["dedicated_vram_gib"])
        if vram >= float(spec["vram_likely_gib"]):
            return "LIKELY_COMPATIBLE"
        if vram >= float(spec["vram_optimized_gib"]):
            return "POSSIBLY_COMPATIBLE_WITH_OPTIMIZATION"
        return "NOT_RECOMMENDED"
    if ram >= float(spec["cpu_ram_gib"]):
        return "POSSIBLY_COMPATIBLE_WITH_OPTIMIZATION"
    return "NOT_RECOMMENDED"


def _justify(spec: dict[str, Any], hardware: dict[str, Any], rating: str) -> str:
    if rating == "INSUFFICIENT_INFORMATION":
        return "System RAM or discrete-GPU VRAM was not available, so no compatibility claim is made."
    if hardware.get("discrete_gpu") is not True:
        return (
            f"{spec['model_name']} has no demonstrated CPU path on this machine. "
            f"System RAM is {hardware.get('system_ram_gib')} GiB; the planning figure for a "
            f"CPU or offload attempt is {spec['cpu_ram_gib']} GiB. No generation was run."
        )
    return (
        f"Dedicated VRAM {hardware.get('dedicated_vram_gib')} GiB compared with planning "
        f"figures of {spec['vram_likely_gib']} GiB (likely) and "
        f"{spec['vram_optimized_gib']} GiB (optimized). No generation was run."
    )


__all__ = [
    "evaluate_local_models",
    "model_catalog",
    "rate_model",
    "recommend",
]
