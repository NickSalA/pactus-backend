import argparse
import asyncio
import json
from pathlib import Path

from contractai_backend.modules.documents.domain import DocumentType
from contractai_backend.modules.documents.infrastructure import LlamaParseExtractor
from contractai_backend.modules.templates.api.schemas import GenerateTemplateDraftRequest
from contractai_backend.modules.templates.application.services.template_authoring_service import TemplateAuthoringService
from contractai_backend.modules.templates.domain.entities import TemplateFormatTable
from contractai_backend.modules.templates.infrastructure import GeminiTemplateDraftGenerator, JinjaRenderer
from contractai_backend.modules.users.domain.value_objs import UserRole


class DummyTemplateRepository:
    async def save(self, entity):
        """Blocks persistence in the local script."""
        raise NotImplementedError("save is not supported in this script")


class DummyOrganizationRepository:
    async def get_organization_data(self, organization_id: int):
        """Returns empty organization context for local runs."""
        return {}


class DummyTemplateFormatRepository:
    def __init__(self):
        self._formats = [
            TemplateFormatTable(
                id=1,
                document_type=DocumentType.COMPANY,
                format_code="management",
                label="Contrato de Management",
                default_name="Contrato de Management",
                default_description="Plantilla base para contratos corporativos de management.",
                is_active=True,
            ),
            TemplateFormatTable(
                id=2,
                document_type=DocumentType.LABOR,
                format_code="fixed_term",
                label="Contrato a Plazo Fijo",
                default_name="Contrato a Plazo Fijo",
                default_description="Plantilla base para contratos laborales sujetos a plazo fijo.",
                is_active=True,
            ),
        ]

    async def get_by_id(self, id: int):
        """Returns one format by id."""
        for template_format in self._formats:
            if template_format.id == id:
                return template_format
        return None

    async def get_by_document_type_and_code(self, document_type: DocumentType, format_code: str):
        """Returns one active format by type and code."""
        for template_format in self._formats:
            if template_format.document_type == document_type and template_format.format_code == format_code and template_format.is_active:
                return template_format
        return None

    async def list_active(self, document_type: DocumentType | None = None):
        """Lists active dummy formats."""
        if document_type is None:
            return list(self._formats)
        return [template_format for template_format in self._formats if template_format.document_type == document_type and template_format.is_active]

    async def list_by_ids(self, ids):
        """Lists dummy formats by id."""
        return [template_format for template_format in self._formats if template_format.id in ids]


def _load_request_payload(raw: str | None) -> dict:
    """Loads a JSON payload from inline text or file."""
    if not raw:
        return {}

    path = Path(raw)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(raw)


def _build_request_payload(args: argparse.Namespace) -> dict:
    """Builds the final request payload from CLI args."""
    payload = _load_request_payload(args.request)

    if args.name:
        payload["name"] = args.name
    if args.description:
        payload["description"] = args.description
    if args.instructions:
        payload["instructions"] = args.instructions
    if args.document_type:
        payload["document_type"] = args.document_type
    if args.format_code:
        payload["format_code"] = args.format_code
    if args.jurisdiction:
        payload["jurisdiction"] = args.jurisdiction

    return payload


async def _run(args: argparse.Namespace) -> None:
    """Runs the draft generation flow."""
    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    payload = _build_request_payload(args)
    if not payload:
        payload = {
            "name": file_path.stem.replace("_", " ").strip() or "Plantilla sin nombre",
            "description": "Borrador generado desde archivo de referencia",
            "document_type": DocumentType.COMPANY,
            "format_code": "management",
        }

    request = GenerateTemplateDraftRequest(**payload)

    extractor = LlamaParseExtractor()
    draft_generator = GeminiTemplateDraftGenerator()
    service = TemplateAuthoringService(
        template_repo=DummyTemplateRepository(),
        template_format_repo=DummyTemplateFormatRepository(),
        organization_repo=DummyOrganizationRepository(),
        renderer=JinjaRenderer(),
        extractor=extractor,
        draft_generator=draft_generator,
    )

    file_content = file_path.read_bytes()
    draft, _ = await service.generate_draft_from_file(
        request=request,
        file_content=file_content,
        filename=file_path.name,
        organization_id=args.organization_id,
        user_role=UserRole.ADMIN,
    )

    output = draft.model_dump(mode="json")
    output_json = json.dumps(output, indent=2, ensure_ascii=True)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
    else:
        print(output_json)


def main() -> None:
    """Parses CLI args and launches the script."""
    parser = argparse.ArgumentParser(description="Generate a template draft from a reference file.")
    parser.add_argument("--file", required=True, help="Path to reference file (pdf/docx/md/txt)")
    parser.add_argument("--request", help="JSON string or path to JSON file with draft request")
    parser.add_argument("--name", help="Template name")
    parser.add_argument("--description", help="Template description")
    parser.add_argument("--instructions", help="Authoring instructions")
    parser.add_argument("--document-type", choices=[value.value for value in DocumentType], help="Document type")
    parser.add_argument("--format-code", help="Template format code")
    parser.add_argument("--jurisdiction", help="Jurisdiction")
    parser.add_argument("--output", help="Write draft JSON to this file")
    parser.add_argument("--organization-id", type=int, default=1, help="Organization ID (default: 1)")

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
