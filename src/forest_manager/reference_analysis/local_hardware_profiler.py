from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import os
import platform
import shutil
from typing import Any


@dataclass(frozen=True)
class LocalVisionHardwareProfile:
    platform: str
    machine: str
    processor: str
    logical_cpu_count: int | None
    total_ram_bytes: int | None
    free_disk_bytes: int | None
    python_version: str
    torch_available: bool
    transformers_available: bool
    pillow_available: bool
    cuda_available: bool
    cuda_device_count: int
    cuda_device_name: str | None
    cuda_total_vram_bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalVisionHardwareProfiler:
    @staticmethod
    def _module_exists(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    @staticmethod
    def _total_ram_bytes() -> int | None:
        if os.name == "nt":
            try:
                import ctypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                status = MEMORYSTATUSEX()
                status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                    return int(status.ullTotalPhys)
            except Exception:
                return None
            return None

        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            pages = os.sysconf("SC_PHYS_PAGES")
            return int(page_size * pages)
        except (AttributeError, ValueError, OSError):
            return None

    @staticmethod
    def _free_disk_bytes() -> int | None:
        try:
            usage = shutil.disk_usage(os.getcwd())
            return int(usage.free)
        except OSError:
            return None

    def inspect(self) -> LocalVisionHardwareProfile:
        torch_available = self._module_exists("torch")
        transformers_available = self._module_exists("transformers")
        pillow_available = self._module_exists("PIL")

        cuda_available = False
        cuda_device_count = 0
        cuda_device_name = None
        cuda_total_vram_bytes = None

        if torch_available:
            try:
                import torch

                cuda_available = bool(torch.cuda.is_available())
                if cuda_available:
                    cuda_device_count = int(torch.cuda.device_count())
                    if cuda_device_count > 0:
                        props = torch.cuda.get_device_properties(0)
                        cuda_device_name = str(props.name)
                        cuda_total_vram_bytes = int(props.total_memory)
            except Exception:
                cuda_available = False
                cuda_device_count = 0

        return LocalVisionHardwareProfile(
            platform=platform.platform(),
            machine=platform.machine(),
            processor=platform.processor(),
            logical_cpu_count=os.cpu_count(),
            total_ram_bytes=self._total_ram_bytes(),
            free_disk_bytes=self._free_disk_bytes(),
            python_version=platform.python_version(),
            torch_available=torch_available,
            transformers_available=transformers_available,
            pillow_available=pillow_available,
            cuda_available=cuda_available,
            cuda_device_count=cuda_device_count,
            cuda_device_name=cuda_device_name,
            cuda_total_vram_bytes=cuda_total_vram_bytes,
        )
