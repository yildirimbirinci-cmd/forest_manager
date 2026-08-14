from __future__ import annotations

from pathlib import Path
import struct

from .models import PlantingIntent, ReferenceAnalysisResult, ReferenceImageInfo


class ReferenceImageError(RuntimeError):
    pass


def _read_png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ReferenceImageError("Invalid PNG file.")
    return struct.unpack(">II", header[16:24])


def _read_jpeg_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        data = handle.read(2)
        if data != b"\xff\xd8":
            raise ReferenceImageError("Invalid JPEG file.")

        while True:
            marker_start = handle.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue

            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)

            if not marker:
                break

            marker_value = marker[0]

            if marker_value in {0xD8, 0xD9}:
                continue

            length_raw = handle.read(2)
            if len(length_raw) != 2:
                break

            segment_length = struct.unpack(">H", length_raw)[0]
            if segment_length < 2:
                raise ReferenceImageError("Invalid JPEG segment length.")

            if marker_value in {
                0xC0, 0xC1, 0xC2, 0xC3,
                0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB,
                0xCD, 0xCE, 0xCF,
            }:
                payload = handle.read(segment_length - 2)
                if len(payload) < 5:
                    break
                height, width = struct.unpack(">HH", payload[1:5])
                return width, height

            handle.seek(segment_length - 2, 1)

    raise ReferenceImageError("Could not read JPEG dimensions.")


def _read_image_size(path: Path) -> tuple[int, int]:
    extension = path.suffix.lower()
    if extension == ".png":
        return _read_png_size(path)
    if extension in {".jpg", ".jpeg"}:
        return _read_jpeg_size(path)
    raise ReferenceImageError(
        "Stage 4I currently accepts PNG, JPG, and JPEG reference images."
    )


class ReferenceImageAnalyzer:
    """
    Stage 4I establishes the product-facing analysis contract.

    This implementation intentionally does not claim semantic AI understanding yet.
    It validates the image and produces deterministic structural metadata plus a
    conservative placeholder planting intent. A vision model can replace this
    analyzer later without changing CompositionPlan or the 3ds Max bridge.
    """

    ANALYZER_NAME = "stage4i_structural_v1"

    def analyze(self, image_path: Path | str) -> ReferenceAnalysisResult:
        path = Path(image_path).expanduser().resolve()

        if not path.exists():
            raise ReferenceImageError(f"Reference image does not exist: {path}")
        if not path.is_file():
            raise ReferenceImageError(f"Reference path is not a file: {path}")

        width, height = _read_image_size(path)
        if width <= 0 or height <= 0:
            raise ReferenceImageError("Reference image dimensions are invalid.")

        aspect_ratio = width / height
        if aspect_ratio > 1.05:
            orientation = "landscape"
        elif aspect_ratio < 0.95:
            orientation = "portrait"
        else:
            orientation = "square"

        image = ReferenceImageInfo(
            path=str(path),
            filename=path.name,
            extension=path.suffix.lower(),
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            orientation=orientation,
            file_size_bytes=path.stat().st_size,
        )

        intent = PlantingIntent(
            style="unclassified",
            density="unclassified",
            diversity="unclassified",
            canopy_bias="unclassified",
            notes=(
                "Semantic reference-image understanding is not enabled in Stage 4I.",
                "Stage 4I validates the image-analysis contract only.",
            ),
        )

        return ReferenceAnalysisResult(
            image=image,
            intent=intent,
            suggested_queries=(),
            confidence=0.0,
            analyzer=self.ANALYZER_NAME,
        )
