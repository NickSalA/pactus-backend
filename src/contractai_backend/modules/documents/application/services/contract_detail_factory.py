"""Factories for document contract detail entities."""

from datetime import UTC, datetime
from typing import Any

from ...domain import CompanyContractTable, CurrencyType, LaborContractTable
from ..dto import (
    CompanyContractRequest,
    CreateDocumentDraftRequest,
    CreateDocumentRequest,
    ExtractedDocumentData,
    LaborContractRequest,
    UpdateDocumentRequest,
)

LABOR_CONTRACT_NAME_PREFIX = "Contrato Estándar de Trabajador"
COMPANY_CONTRACT_NAME_PREFIX = "Contrato Estándar de Empresa"


class ContractDetailFactory:
    """Builds contract detail entities from requests, form data and extracted data."""

    @staticmethod
    def first_text_value(*values: Any) -> str | None:
        """Returns the first non-empty stripped text value."""
        stripped_values = (v.strip() for v in values if isinstance(v, str))
        return next((v for v in stripped_values if v), None)

    @staticmethod
    def first_float_value(*values: Any) -> float | None:
        """Returns the first value that can be converted to float."""
        for value in values:
            if value is None or value == "":
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def coerce_currency(value: Any) -> CurrencyType | None:
        """Converts loose currency values into a supported currency enum."""
        if value is None or value == "":
            return None
        try:
            return CurrencyType(str(value).strip().upper())
        except ValueError:
            return None

    @classmethod
    def build_company_contract_entity(
        cls,
        *,
        document_id: int,
        data: CreateDocumentRequest | CreateDocumentDraftRequest | UpdateDocumentRequest,
        extracted_data: ExtractedDocumentData | None,
        form_data: dict[str, Any],
    ) -> CompanyContractTable:
        """Builds company-specific contract details."""
        company_contract: CompanyContractRequest | None = getattr(data, "company_contract", None)
        return CompanyContractTable(
            document_id=document_id,
            ruc=cls.first_text_value(
                getattr(company_contract, "ruc", None),
                extracted_data.ruc if extracted_data is not None else None,
                form_data.get("gerente_ruc"),
                form_data.get("contratista_ruc"),
                form_data.get("proveedor_ruc"),
                form_data.get("otra_parte_ruc"),
                form_data.get("ruc_gerente"),
                form_data.get("cliente_ruc"),
            ),
            client=cls.first_text_value(
                getattr(company_contract, "client", None),
                getattr(data, "client", None),
                extracted_data.client if extracted_data is not None else None,
            ),
            updated_at=datetime.now(UTC),
        )

    @classmethod
    def build_labor_contract_entity(
        cls,
        *,
        document_id: int,
        data: CreateDocumentRequest | CreateDocumentDraftRequest | UpdateDocumentRequest,
        extracted_data: ExtractedDocumentData | None,
        form_data: dict[str, Any],
    ) -> LaborContractTable:
        """Builds labor-specific contract details."""
        labor_contract: LaborContractRequest | None = getattr(data, "labor_contract", None)
        salary_currency = getattr(labor_contract, "salary_currency", None) or cls.coerce_currency(form_data.get("currency"))
        return LaborContractTable(
            document_id=document_id,
            worker_name=cls.first_text_value(
                getattr(labor_contract, "worker_name", None),
                getattr(data, "client", None),
                extracted_data.worker_name if extracted_data is not None else None,
                form_data.get("trabajador_nombre"),
                form_data.get("nombre_trabajador"),
                form_data.get("trabajador_nombre_completo"),
                form_data.get("empleado_nombre_completo"),
            ),
            worker_document_number=cls.first_text_value(
                getattr(labor_contract, "worker_document_number", None),
                extracted_data.worker_document_number if extracted_data is not None else None,
                form_data.get("trabajador_dni"),
                form_data.get("dni_trabajador"),
                form_data.get("numero_documento_trabajador"),
                form_data.get("empleado_dni"),
            ),
            position=cls.first_text_value(
                getattr(labor_contract, "position", None),
                extracted_data.position if extracted_data is not None else None,
                form_data.get("position"),
                form_data.get("puesto_trabajo"),
                form_data.get("cargo"),
                form_data.get("cargo_ocupar"),
            ),
            salary_value=cls.first_float_value(
                getattr(labor_contract, "salary_value", None),
                form_data.get("value"),
                form_data.get("monto_remuneracion"),
                form_data.get("remuneracion_mensual_monto"),
                form_data.get("remuneracion_bruta"),
            ),
            salary_currency=salary_currency,
            salary_periodicity=cls.first_text_value(
                getattr(labor_contract, "salary_periodicity", None),
                extracted_data.salary_periodicity if extracted_data is not None else None,
                form_data.get("periodicidad_remuneracion"),
                form_data.get("frecuencia_pago"),
                form_data.get("periodicidad_pago"),
            ),
            contract_modality=cls.first_text_value(
                getattr(labor_contract, "contract_modality", None),
                extracted_data.contract_modality if extracted_data is not None else None,
                form_data.get("modalidad_contrato"),
                form_data.get("modalidad_contrato_tipo"),
                form_data.get("forma_contratacion"),
            ),
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    def build_labor_contract_name(worker_name: str | None) -> str:
        """Builds the default display name for labor contracts."""
        normalized_worker_name = worker_name.strip() if isinstance(worker_name, str) else ""
        if normalized_worker_name:
            return f"{LABOR_CONTRACT_NAME_PREFIX} - {normalized_worker_name}"
        return LABOR_CONTRACT_NAME_PREFIX

    @staticmethod
    def build_company_contract_name(company_name: str | None) -> str:
        """Builds the default display name for company contracts."""
        normalized_company_name = company_name.strip() if isinstance(company_name, str) else ""
        if normalized_company_name:
            return f"{COMPANY_CONTRACT_NAME_PREFIX} - {normalized_company_name}"
        return COMPANY_CONTRACT_NAME_PREFIX
