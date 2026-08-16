from .file_ingestion import ProjectFileImportResult, ProjectFileIngestionService
from .file_readers import (
    CadFileReader,
    PdfFileReader,
    ProjectFileReaderError,
    ReaderBackendStatus,
    reader_backend_status,
)
from .annotations import AREA_ROLES, BOUNDARY_ROLES, is_boundary_role, resolve_annotation
from .geometry import create_geometry
from .ingestion import (
    ImportBatch,
    ImportedEntity,
    IngestionResult,
    ProjectSource,
    ProjectSourceKind,
    SiteModelIngestor,
    SourceLocator,
)
from .parser_adapters import CadParserAdapter, ParsedPrimitive, ParserAdapterError, PdfParserAdapter
from .persistence import SiteModelPersistence
from .schema import (
    AnnotationSource,
    GeometryKind,
    SemanticAnnotation,
    SemanticRole,
    SiteGeometry,
    SiteModelSnapshot,
    SitePoint,
)
from .service import SiteModelError, SiteModelService
from .viewer import SiteModelViewerAdapter, ViewerGeometryRecord, ViewerSnapshot
from .viewer_interaction import SiteModelViewerInteraction, ViewerCorrectionResult, ViewerSelectionState
from .viewer_binding import SiteModelViewerBinding, ViewerBindingSnapshot, ViewerBounds, ViewerRenderRecord

__all__ = [
    "AREA_ROLES",
    "BOUNDARY_ROLES",
    "AnnotationSource",
    "CadFileReader",
    "CadParserAdapter",
    "GeometryKind",
    "ImportBatch",
    "ImportedEntity",
    "IngestionResult",
    "ParsedPrimitive",
    "ParserAdapterError",
    "PdfFileReader",
    "PdfParserAdapter",
    "ProjectFileImportResult",
    "ProjectFileIngestionService",
    "ProjectFileReaderError",
    "ProjectSource",
    "ProjectSourceKind",
    "ReaderBackendStatus",
    "SemanticAnnotation",
    "SemanticRole",
    "SiteGeometry",
    "SiteModelError",
    "SiteModelIngestor",
    "SiteModelPersistence",
    "SiteModelService",
    "SiteModelSnapshot",
    "SiteModelViewerAdapter",
    "SiteModelViewerBinding",
    "SiteModelViewerInteraction",
    "SitePoint",
    "SourceLocator",
    "ViewerBindingSnapshot",
    "ViewerBounds",
    "ViewerCorrectionResult",
    "ViewerGeometryRecord",
    "ViewerRenderRecord",
    "ViewerSelectionState",
    "ViewerSnapshot",
    "create_geometry",
    "is_boundary_role",
    "reader_backend_status",
    "resolve_annotation",
]

from .viewer_presenter import ProjectViewerState, SiteViewerPresenter

__all__.extend(["ProjectViewerState", "SiteViewerPresenter"])
