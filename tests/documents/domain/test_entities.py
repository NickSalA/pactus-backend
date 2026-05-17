"""Tests unitarios para las entidades del dominio de documentos."""

from datetime import date

import pytest
from pydantic import ValidationError

from contractai_backend.modules.documents.domain import (
    DocumentServiceTable,
    DocumentTable,
    validate_service_currency_alignment,
    validate_service_periods,
)
from contractai_backend.modules.catalog.domain.entities import ServiceTable
from contractai_backend.modules.documents.domain.exceptions import DocumentValidationError
from contractai_backend.modules.documents.domain.value_objs import CurrencyType, DocumentState, DocumentType


def _valid_doc(**overrides) -> dict:
    base = {
        "organization_id": 1,
        "type": DocumentType.COMPANY,
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 12, 31),
        "form_data": {"value": 1000, "currency": "USD", "owner": "IT"},
    }
    base.update(overrides)
    return base


class TestDocumentTableValidation:
    def test_creates_valid_document(self):
        doc = DocumentTable.model_validate(_valid_doc())
        assert doc.organization_id == 1
        assert doc.type == DocumentType.COMPANY
        assert doc.state is None

    def test_end_date_before_start_date_raises(self):
        with pytest.raises(ValidationError, match="End date cannot be earlier than start date"):
            DocumentTable.model_validate(_valid_doc(start_date=date(2024, 6, 1), end_date=date(2024, 1, 1)))

    def test_blank_type_raises(self):
        with pytest.raises(ValidationError, match="Field cannot be empty"):
            DocumentTable.model_validate(_valid_doc(type="   "))

    def test_form_data_must_be_json_object(self):
        with pytest.raises(ValidationError, match="Input should be a valid dictionary"):
            DocumentTable.model_validate(_valid_doc(form_data=["invalid"]))

    def test_default_state_is_none(self):
        doc = DocumentTable.model_validate(_valid_doc())
        assert doc.state is None

    def test_file_path_defaults_to_none(self):
        doc = DocumentTable.model_validate(_valid_doc())
        assert doc.file_path is None
        assert doc.file_name is None

    def test_all_document_types_are_accepted(self):
        for doc_type in DocumentType:
            doc = DocumentTable.model_validate(_valid_doc(type=doc_type))
            assert doc.type == doc_type

    def test_all_document_states_can_be_set(self):
        for state in DocumentState:
            doc = DocumentTable.model_validate(_valid_doc(state=state))
            assert doc.state == state

    def test_nullable_top_level_fields_are_allowed(self):
        doc = DocumentTable.model_validate(
            _valid_doc(
                type=None,
                start_date=None,
                end_date=None,
                state=None,
            )
        )

        assert doc.type is None
        assert doc.start_date is None
        assert doc.end_date is None
        assert doc.state is None


class TestDocumentServiceTableValidation:
    def test_creates_valid_document_service(self):
        service_item = DocumentServiceTable.model_validate(
            {
                "company_contract_id": 1,
                "service_id": 2,
                "description": "Hosting",
                "value": 1500.0,
                "currency": CurrencyType.PEN,
                "start_date": date(2024, 1, 1),
                "end_date": date(2024, 6, 30),
            }
        )
        assert service_item.currency == CurrencyType.PEN

    def test_negative_value_raises(self):
        with pytest.raises(ValidationError, match="Value must be a positive number"):
            DocumentServiceTable.model_validate(
                {
                    "company_contract_id": 1,
                    "service_id": 2,
                    "value": -1.0,
                    "currency": CurrencyType.USD,
                    "start_date": date(2024, 1, 1),
                    "end_date": date(2024, 1, 2),
                }
            )

    def test_non_positive_service_id_raises(self):
        with pytest.raises(ValidationError, match="ID must be a positive integer"):
            DocumentServiceTable.model_validate(
                {
                    "company_contract_id": 1,
                    "service_id": 0,
                    "value": 10.0,
                    "currency": CurrencyType.EUR,
                    "start_date": date(2024, 1, 1),
                    "end_date": date(2024, 1, 2),
                }
            )

    def test_end_date_before_start_date_raises(self):
        with pytest.raises(ValidationError, match="End date cannot be earlier than start date"):
            DocumentServiceTable.model_validate(
                {
                    "company_contract_id": 1,
                    "service_id": 2,
                    "value": 10.0,
                    "currency": CurrencyType.EUR,
                    "start_date": date(2024, 2, 1),
                    "end_date": date(2024, 1, 1),
                }
            )


class TestSupportingTables:
    def test_service_table_requires_non_empty_name(self):
        with pytest.raises(ValidationError, match="Service name cannot be empty"):
            ServiceTable.model_validate({"organization_id": 1, "name": "   "})


class TestDocumentServiceRules:
    def test_currency_alignment_raises_for_mixed_currencies(self):
        items = [
            _make_service_item(currency=CurrencyType.USD),
            _make_service_item(service_id=3, currency=CurrencyType.PEN),
        ]

        with pytest.raises(DocumentValidationError, match="misma moneda"):
            validate_service_currency_alignment(items)

    def test_service_periods_raise_outside_document_range(self):
        items = [
            _make_service_item(start_date=date(2023, 12, 1), end_date=date(2024, 6, 1)),
        ]

        with pytest.raises(
            DocumentValidationError,
            match=r"contrato: 2024-01-01 a 2024-12-31, servicio: 2023-12-01 a 2024-06-01",
        ):
            validate_service_periods(
                document_start_date=date(2024, 1, 1),
                document_end_date=date(2024, 12, 31),
                service_items=items,
            )


def _make_service_item(**overrides) -> DocumentServiceTable:
    payload = {
        "company_contract_id": 1,
        "service_id": 2,
        "description": "Hosting",
        "value": 100.0,
        "currency": CurrencyType.USD,
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 6, 1),
    }
    payload.update(overrides)
    return DocumentServiceTable.model_validate(payload)
