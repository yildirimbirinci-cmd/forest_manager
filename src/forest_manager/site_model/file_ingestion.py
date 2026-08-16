from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .file_readers import CadFileReader, PdfFileReader, ProjectFileReaderError
from .ingestion import ImportBatch, IngestionResult, SiteModelIngestor
from .service import SiteModelService


@dataclass(frozen=True)
class ProjectFileImportResult:
    batch: ImportBatch
    ingestion: IngestionResult


class ProjectFileIngestionService:
    """End-to-end file -> parser -> ImportBatch -> SiteModel entry point."""

    def __init__(
        self,
        *,
        cad_reader: CadFileReader | None = None,
        pdf_reader: PdfFileReader | None = None,
        ingestor: SiteModelIngestor | None = None,
    ) -> None:
        self.cad_reader = cad_reader or CadFileReader()
        self.pdf_reader = pdf_reader or PdfFileReader()
        self.ingestor = ingestor or SiteModelIngestor()

    def read(self, path: str | Path, *, source_id: str | None = None) -> ImportBatch:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix in {".dxf", ".dwg"}:
            return self.cad_reader.read(file_path, source_id=source_id)
        if suffix == ".pdf":
            return self.pdf_reader.read(file_path, source_id=source_id)
        raise ProjectFileReaderError(f"unsupported project drawing format: {suffix or '<none>'}")

    def import_file(
        self,
        service: SiteModelService,
        path: str | Path,
        *,
        source_id: str | None = None,
    ) -> ProjectFileImportResult:
        batch = self.read(path, source_id=source_id)
        ingestion = self.ingestor.ingest(service, batch)
        return ProjectFileImportResult(batch=batch, ingestion=ingestion)
