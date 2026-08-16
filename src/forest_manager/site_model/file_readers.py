from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .ingestion import ImportBatch, ProjectSource, ProjectSourceKind
from .parser_adapters import CadParserAdapter, ParsedPrimitive, PdfParserAdapter


class ProjectFileReaderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReaderBackendStatus:
    backend: str
    available: bool
    detail: str = ""


def reader_backend_status() -> tuple[ReaderBackendStatus, ...]:
    statuses: list[ReaderBackendStatus] = []
    try:
        import ezdxf  # type: ignore

        statuses.append(ReaderBackendStatus("ezdxf", True, str(getattr(ezdxf, "__version__", ""))))
    except Exception as exc:  # pragma: no cover - environment dependent
        statuses.append(ReaderBackendStatus("ezdxf", False, str(exc)))
    try:
        import fitz  # type: ignore

        version = getattr(fitz, "VersionBind", "") or getattr(fitz, "__version__", "")
        statuses.append(ReaderBackendStatus("PyMuPDF", True, str(version)))
    except Exception as exc:  # pragma: no cover - environment dependent
        statuses.append(ReaderBackendStatus("PyMuPDF", False, str(exc)))
    return tuple(statuses)


def _source_id(path: Path, explicit: str | None) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    return path.stem.strip() or "project-source"


def _point_tuple(value: Any) -> tuple[float, float, float]:
    z = getattr(value, "z", 0.0)
    return (float(value.x), float(value.y), float(z))


class CadFileReader:
    """Read real DXF files and normalize supported entities for Stage 8 ingestion.

    DWG is deliberately rejected here because ezdxf does not read native DWG.
    A future converter/backend can feed the existing CadParserAdapter without
    changing the Site Model contract.
    """

    def __init__(self, *, adapter: CadParserAdapter | None = None) -> None:
        self.adapter = adapter or CadParserAdapter()

    def read(self, path: str | Path, *, source_id: str | None = None) -> ImportBatch:
        file_path = Path(path)
        if file_path.suffix.lower() == ".dwg":
            raise ProjectFileReaderError("native DWG reading is not available; convert DWG to DXF before import")
        if file_path.suffix.lower() != ".dxf":
            raise ProjectFileReaderError("CAD reader currently accepts .dxf files")
        if not file_path.is_file():
            raise ProjectFileReaderError(f"CAD source file does not exist: {file_path}")
        try:
            import ezdxf  # type: ignore
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ProjectFileReaderError("DXF backend unavailable; install ezdxf") from exc
        try:
            document = ezdxf.readfile(str(file_path))
        except Exception as exc:
            raise ProjectFileReaderError(f"failed to read DXF file: {file_path}") from exc

        units = int(document.header.get("$INSUNITS", 0) or 0)
        source = ProjectSource(
            source_id=_source_id(file_path, source_id),
            kind=ProjectSourceKind.CAD,
            path=str(file_path),
            metadata={"reader_backend": "ezdxf", "dxf_insunits": units},
        )
        primitives = tuple(self._iter_primitives(document.modelspace()))
        return self.adapter.adapt(source, primitives)

    def _iter_primitives(self, modelspace: Any) -> Iterable[ParsedPrimitive]:
        for index, entity in enumerate(modelspace):
            entity_type = str(entity.dxftype()).upper()
            handle = str(getattr(entity.dxf, "handle", "") or f"entity-{index}")
            layer = str(getattr(entity.dxf, "layer", "") or "")
            base_meta = {"cad_entity_type": entity_type, "cad_handle": handle}

            if entity_type == "LINE":
                yield ParsedPrimitive(
                    entity_id=handle,
                    primitive_type="line",
                    points=(_point_tuple(entity.dxf.start), _point_tuple(entity.dxf.end)),
                    layer=layer,
                    metadata=base_meta,
                )
                continue

            if entity_type == "POINT":
                yield ParsedPrimitive(
                    entity_id=handle,
                    primitive_type="point",
                    points=(_point_tuple(entity.dxf.location),),
                    layer=layer,
                    metadata=base_meta,
                )
                continue

            if entity_type == "LWPOLYLINE":
                elevation = float(getattr(entity.dxf, "elevation", 0.0) or 0.0)
                points = tuple((float(x), float(y), elevation) for x, y, *_ in entity.get_points("xy"))
                if points:
                    yield ParsedPrimitive(
                        entity_id=handle,
                        primitive_type="lwpolyline",
                        points=points,
                        closed=bool(entity.closed),
                        layer=layer,
                        metadata=base_meta,
                    )
                continue

            if entity_type == "POLYLINE":
                points = tuple(_point_tuple(vertex.dxf.location) for vertex in entity.vertices)
                if points:
                    yield ParsedPrimitive(
                        entity_id=handle,
                        primitive_type="polyline",
                        points=points,
                        closed=bool(entity.is_closed),
                        layer=layer,
                        metadata=base_meta,
                    )
                continue

            if entity_type == "HATCH":
                for path_index, boundary in enumerate(entity.paths):
                    points = self._hatch_boundary_points(boundary)
                    if len(points) < 3:
                        continue
                    metadata = dict(base_meta)
                    metadata["hatch_path_index"] = path_index
                    yield ParsedPrimitive(
                        entity_id=f"{handle}:path-{path_index}",
                        primitive_type="hatch",
                        points=points,
                        closed=True,
                        layer=layer,
                        metadata=metadata,
                    )

    @staticmethod
    def _hatch_boundary_points(boundary: Any) -> tuple[tuple[float, float, float], ...]:
        vertices = getattr(boundary, "vertices", None)
        if vertices:
            result = []
            for vertex in vertices:
                result.append((float(vertex[0]), float(vertex[1]), 0.0))
            return tuple(result)

        edges = getattr(boundary, "edges", None) or ()
        result: list[tuple[float, float, float]] = []
        for edge in edges:
            start = getattr(edge, "start", None)
            end = getattr(edge, "end", None)
            if start is not None:
                point = (float(start[0]), float(start[1]), 0.0)
                if not result or result[-1] != point:
                    result.append(point)
            if end is not None:
                point = (float(end[0]), float(end[1]), 0.0)
                if not result or result[-1] != point:
                    result.append(point)
        return tuple(result)


class PdfFileReader:
    """Read vector paths from real PDF files through PyMuPDF."""

    def __init__(self, *, adapter: PdfParserAdapter | None = None) -> None:
        self.adapter = adapter or PdfParserAdapter()

    def read(self, path: str | Path, *, source_id: str | None = None) -> ImportBatch:
        file_path = Path(path)
        if file_path.suffix.lower() != ".pdf":
            raise ProjectFileReaderError("PDF reader accepts .pdf files")
        if not file_path.is_file():
            raise ProjectFileReaderError(f"PDF source file does not exist: {file_path}")
        try:
            import fitz  # type: ignore
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ProjectFileReaderError("PDF backend unavailable; install PyMuPDF") from exc

        try:
            document = fitz.open(str(file_path))
        except Exception as exc:
            raise ProjectFileReaderError(f"failed to read PDF file: {file_path}") from exc

        try:
            source = ProjectSource(
                source_id=_source_id(file_path, source_id),
                kind=ProjectSourceKind.PDF,
                path=str(file_path),
                page_count=int(document.page_count),
                metadata={"reader_backend": "PyMuPDF"},
            )
            primitives: list[ParsedPrimitive] = []
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                for drawing_index, drawing in enumerate(page.get_drawings()):
                    points = self._drawing_points(drawing)
                    if len(points) < 2:
                        continue
                    closed = bool(drawing.get("closePath", False))
                    primitive_type = "region" if closed and len(points) >= 3 else "path"
                    metadata = {
                        "pdf_drawing_index": drawing_index,
                        "pdf_rect": self._rect_payload(drawing.get("rect")),
                        "pdf_fill": self._simple_value(drawing.get("fill")),
                        "pdf_color": self._simple_value(drawing.get("color")),
                        "pdf_width": drawing.get("width"),
                        "pdf_dashes": drawing.get("dashes"),
                    }
                    primitives.append(
                        ParsedPrimitive(
                            entity_id=f"page-{page_index}:drawing-{drawing_index}",
                            primitive_type=primitive_type,
                            points=points,
                            closed=closed,
                            page_index=page_index,
                            layer=str(drawing.get("layer") or ""),
                            metadata=metadata,
                        )
                    )
            return self.adapter.adapt(source, primitives)
        finally:
            document.close()

    @classmethod
    def _drawing_points(cls, drawing: dict[str, Any]) -> tuple[tuple[float, float], ...]:
        result: list[tuple[float, float]] = []
        for item in drawing.get("items") or ():
            if not item:
                continue
            command = str(item[0]).lower()
            if command == "l" and len(item) >= 3:
                cls._append_pdf_point(result, item[1])
                cls._append_pdf_point(result, item[2])
            elif command == "re" and len(item) >= 2:
                rect = item[1]
                for point in (
                    (rect.x0, rect.y0),
                    (rect.x1, rect.y0),
                    (rect.x1, rect.y1),
                    (rect.x0, rect.y1),
                ):
                    cls._append_pdf_point(result, point)
            elif command == "qu" and len(item) >= 2:
                quad = item[1]
                for point in (quad.ul, quad.ur, quad.lr, quad.ll):
                    cls._append_pdf_point(result, point)
            elif command == "c" and len(item) >= 5:
                cls._append_pdf_point(result, item[1])
                cls._append_pdf_point(result, item[4])
        return tuple(result)

    @staticmethod
    def _append_pdf_point(target: list[tuple[float, float]], value: Any) -> None:
        if hasattr(value, "x") and hasattr(value, "y"):
            point = (float(value.x), float(value.y))
        else:
            point = (float(value[0]), float(value[1]))
        if not target or target[-1] != point:
            target.append(point)

    @staticmethod
    def _rect_payload(value: Any) -> tuple[float, float, float, float] | None:
        if value is None:
            return None
        return (float(value.x0), float(value.y0), float(value.x1), float(value.y1))

    @staticmethod
    def _simple_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (tuple, list)):
            return tuple(float(item) for item in value)
        return str(value)
