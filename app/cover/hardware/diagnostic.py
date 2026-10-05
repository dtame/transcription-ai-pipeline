"""Non-destructive local hardware inventory. No installs, downloads, or benchmarks."""

from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from typing import Any


def collect_hardware(*, repo_root: str | None = None) -> dict[str, Any]:
    memory = _memory_status()
    gpus = _video_controllers()
    primary = gpus[0] if gpus else {}
    discrete = _discrete_gpu(primary)
    processor = _processor()
    disk_root = repo_root or "C:\\"
    disk = shutil.disk_usage(disk_root)
    pytorch = _module_available("torch")
    directml_module = _module_available("torch_directml")
    ort_providers = _onnx_providers()
    return {
        "operating_system": platform.platform(),
        "python_version": platform.python_version(),
        "cpu": processor.get("name") or platform.processor() or None,
        "cpu_cores": processor.get("cores"),
        "system_ram_bytes": memory.get("total_bytes"),
        "system_ram_gib": _gib(memory.get("total_bytes")),
        "available_ram_bytes": memory.get("available_bytes"),
        "available_ram_gib": _gib(memory.get("available_bytes")),
        "available_ram_is_point_in_time": True,
        "gpu_present": bool(primary.get("name")),
        "gpu_name": primary.get("name"),
        "gpu_vendor": primary.get("vendor"),
        "discrete_gpu": discrete,
        "dedicated_vram_gib": None,
        "wmi_adapter_ram_bytes": primary.get("adapter_ram_bytes"),
        "wmi_adapter_ram_treated_as_dedicated_vram": False,
        "vram_note": _vram_note(primary, discrete),
        "cuda_version": None,
        "nvidia_smi": False,
        "pytorch_installed": pytorch,
        "directml_available": bool(directml_module or "DmlExecutionProvider" in ort_providers),
        "onnxruntime_providers": ort_providers,
        "inference_libraries": _inference_libraries(),
        "disk_total_bytes": disk.total,
        "disk_free_bytes": disk.free,
        "disk_free_gib": _gib(disk.free),
        "network_calls": 0,
        "downloads": 0,
        "packages_installed": [],
        "benchmark_executed": False,
        "preliminary": True,
        "python_executable": sys.executable,
    }


def _memory_status() -> dict[str, int | None]:
    if sys.platform != "win32":
        return {"total_bytes": None, "available_bytes": None}
    import ctypes

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"total_bytes": None, "available_bytes": None}
    return {
        "total_bytes": int(status.ullTotalPhys),
        "available_bytes": int(status.ullAvailPhys),
    }


def _video_controllers() -> list[dict[str, Any]]:
    if sys.platform != "win32":
        return []
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterCompatibility,AdapterRAM,PNPDeviceID | "
        "ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not (completed.stdout or "").strip():
        return []
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    rows = payload if isinstance(payload, list) else [payload]
    controllers = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ram = row.get("AdapterRAM")
        controllers.append(
            {
                "name": row.get("Name"),
                "vendor": row.get("AdapterCompatibility"),
                "adapter_ram_bytes": int(ram) if isinstance(ram, int) and ram > 0 else None,
                "pnp": row.get("PNPDeviceID"),
            }
        )
    return controllers


def _processor() -> dict[str, Any]:
    if sys.platform != "win32":
        return {"name": platform.processor() or None, "cores": None}
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$p = Get-CimInstance Win32_Processor | Select-Object -First 1; "
            "@{name=$p.Name; cores=$p.NumberOfCores} | ConvertTo-Json -Compress",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout or "")
    except json.JSONDecodeError:
        payload = {}
    cores = payload.get("cores")
    return {
        "name": str(payload.get("name") or "").strip() or platform.processor() or None,
        "cores": int(cores) if isinstance(cores, int) else None,
    }


def _discrete_gpu(controller: dict[str, Any]) -> bool | None:
    if not controller:
        return False
    name = str(controller.get("name") or "").lower()
    vendor = str(controller.get("vendor") or "").lower()
    pnp = str(controller.get("pnp") or "").upper()
    if not name:
        return None
    if "nvidia" in vendor or "ven_10de" in pnp.lower() or "nvidia" in name:
        return True
    if "amd" in vendor or "radeon" in name or "ven_1002" in pnp.lower():
        if "radeon" in name:
            return True
    integrated_markers = ("iris", "uhd", "intel", "basic display", "microsoft")
    if any(marker in name or marker in vendor for marker in integrated_markers):
        return False
    return None


def _vram_note(controller: dict[str, Any], discrete: bool | None) -> str:
    if not controller:
        return "No video controller was reported."
    if discrete is False:
        return (
            "The reported GPU is integrated and uses shared system memory. "
            "Win32_VideoController.AdapterRAM is not treated as dedicated VRAM."
        )
    if discrete is True:
        return "Dedicated VRAM was not queried because nvidia-smi is not used unless a discrete NVIDIA GPU is identified."
    return "GPU class could not be classified from the local controller record."


def _inference_libraries() -> dict[str, bool]:
    names = (
        "torch",
        "diffusers",
        "transformers",
        "accelerate",
        "safetensors",
        "onnxruntime",
        "PIL",
        "torch_directml",
    )
    return {name: _module_available(name) for name in names}


def _onnx_providers() -> list[str]:
    if not _module_available("onnxruntime"):
        return []
    try:
        import onnxruntime as ort
    except Exception:
        return []
    try:
        return list(ort.get_available_providers())
    except Exception:
        return []


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _gib(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / (1024**3), 2)


__all__ = ["collect_hardware"]
