"""HTTP schemas for document-related API requests and responses."""

from ..application.dto import (
    CompanyContractBase as ApplicationCompanyContractBase,
)
from ..application.dto import (
    CompanyContractRequest as ApplicationCompanyContractRequest,
)
from ..application.dto import (
    CompanyContractResponse as ApplicationCompanyContractResponse,
)
from ..application.dto import (
    CreateDocumentDraftRequest as ApplicationCreateDocumentDraftRequest,
)
from ..application.dto import (
    CreateDocumentRequest as ApplicationCreateDocumentRequest,
)
from ..application.dto import (
    DocumentBase as ApplicationDocumentBase,
)
from ..application.dto import (
    DocumentCatalogServiceResponse as ApplicationDocumentCatalogServiceResponse,
)
from ..application.dto import (
    DocumentDraftBase as ApplicationDocumentDraftBase,
)
from ..application.dto import (
    DocumentFileUrlResponse as ApplicationDocumentFileUrlResponse,
)
from ..application.dto import (
    DocumentResponse as ApplicationDocumentResponse,
)
from ..application.dto import (
    DocumentServiceItemBase as ApplicationDocumentServiceItemBase,
)
from ..application.dto import (
    DocumentServiceItemRequest as ApplicationDocumentServiceItemRequest,
)
from ..application.dto import (
    DocumentServiceItemResponse as ApplicationDocumentServiceItemResponse,
)
from ..application.dto import (
    FileRequest as ApplicationFileRequest,
)
from ..application.dto import (
    LaborContractBase as ApplicationLaborContractBase,
)
from ..application.dto import (
    LaborContractRequest as ApplicationLaborContractRequest,
)
from ..application.dto import (
    LaborContractResponse as ApplicationLaborContractResponse,
)
from ..application.dto import (
    UpdateDocumentRequest as ApplicationUpdateDocumentRequest,
)


class DocumentServiceItemBase(ApplicationDocumentServiceItemBase):
    """HTTP base schema for document service items."""


class DocumentServiceItemRequest(ApplicationDocumentServiceItemRequest):
    """HTTP request schema for document service items."""


class DocumentServiceItemResponse(ApplicationDocumentServiceItemResponse):
    """HTTP response schema for document service items."""


class CompanyContractBase(ApplicationCompanyContractBase):
    """HTTP base schema for company contract data."""


class CompanyContractRequest(ApplicationCompanyContractRequest):
    """HTTP request schema for company contract data."""


class CompanyContractResponse(ApplicationCompanyContractResponse):
    """HTTP response schema for company contract data."""


class LaborContractBase(ApplicationLaborContractBase):
    """HTTP base schema for labor contract data."""


class LaborContractRequest(ApplicationLaborContractRequest):
    """HTTP request schema for labor contract data."""


class LaborContractResponse(ApplicationLaborContractResponse):
    """HTTP response schema for labor contract data."""


class DocumentBase(ApplicationDocumentBase):
    """HTTP base schema for documents."""


class DocumentDraftBase(ApplicationDocumentDraftBase):
    """HTTP base schema for draft document requests."""


class CreateDocumentDraftRequest(ApplicationCreateDocumentDraftRequest):
    """HTTP request schema for creating document drafts."""


class CreateDocumentRequest(ApplicationCreateDocumentRequest):
    """HTTP request schema for creating complete documents."""


class UpdateDocumentRequest(ApplicationUpdateDocumentRequest):
    """HTTP request schema for updating documents."""


class DocumentResponse(ApplicationDocumentResponse):
    """HTTP response schema for documents."""


class DocumentCatalogServiceResponse(ApplicationDocumentCatalogServiceResponse):
    """HTTP response schema for catalog services inside document screens."""


class DocumentFileUrlResponse(ApplicationDocumentFileUrlResponse):
    """HTTP response schema for signed document file URLs."""


class FileRequest(ApplicationFileRequest):
    """Internal HTTP helper for uploaded file content."""

__all__ = [
    "CompanyContractBase",
    "CompanyContractRequest",
    "CompanyContractResponse",
    "CreateDocumentDraftRequest",
    "CreateDocumentRequest",
    "DocumentBase",
    "DocumentCatalogServiceResponse",
    "DocumentDraftBase",
    "DocumentFileUrlResponse",
    "DocumentResponse",
    "DocumentServiceItemBase",
    "DocumentServiceItemRequest",
    "DocumentServiceItemResponse",
    "FileRequest",
    "LaborContractBase",
    "LaborContractRequest",
    "LaborContractResponse",
    "UpdateDocumentRequest",
]
