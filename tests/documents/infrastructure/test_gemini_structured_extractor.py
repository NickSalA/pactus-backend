"""Tests for GeminiDocumentStructuredExtractor prompt rules."""

from contractai_backend.modules.catalog.domain.entities import ServiceTable
from contractai_backend.modules.documents.infrastructure.gemini_structured_extractor import GeminiDocumentStructuredExtractor


def test_build_prompt_includes_labor_worker_and_monthly_pay_rules() -> None:
    prompt = GeminiDocumentStructuredExtractor._build_prompt(
        filename="contrato_laboral.pdf",
        markdown="Contrato de trabajo de prueba",
        available_services=[ServiceTable(id=1, organization_id=1, name="Planilla")],
    )

    assert "Never use the employer, institution, company, clinic, school, municipality" in prompt
    assert '"worker_name": string | null' in prompt
    assert '"labor_monthly_value": number | null' in prompt
    assert '"labor_monthly_currency": "PEN" | "USD" | "EUR" | null' in prompt
    assert "form_data.value and form_data.currency must match labor_monthly_value and labor_monthly_currency" in prompt


def test_build_prompt_includes_service_item_uniqueness_and_completeness_rules() -> None:
    prompt = GeminiDocumentStructuredExtractor._build_prompt(
        filename="contrato_servicios.pdf",
        markdown="Contrato con servicios de prueba",
        available_services=[ServiceTable(id=5, organization_id=2, name="Hosting")],
    )

    assert "service_items must not contain duplicated service_id values" in prompt
    assert "If the same catalog service appears more than once" in prompt
    assert "contract explicitly provides value, currency, start_date and end_date" in prompt
