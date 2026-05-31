"""Tests for chatbot access helpers."""

from contractai_backend.modules.chatbot.infrastructure.agent.tools.access import (
    ROLE_PERMISSION_DENIED_RESPONSE,
    evaluate_document_access,
    extract_contract_party_candidate,
)


def test_evaluate_document_access_denies_company_queries_for_hr() -> None:
    decision = evaluate_document_access("Dame contratos con empresas activas", "HR")

    assert decision.is_denied is True
    assert decision.to_prompt_payload()["must_deny"] is True


def test_evaluate_document_access_denies_labor_queries_for_manager() -> None:
    decision = evaluate_document_access("Muestrame contratos con trabajadores", "MANAGER")

    assert decision.is_denied is True
    assert ROLE_PERMISSION_DENIED_RESPONSE == "No tienes permisos para acceder a esa informacion."


def test_evaluate_document_access_denies_explicit_company_queries_for_hr() -> None:
    decision = evaluate_document_access("Necesito ver el contrato corporativo del cliente ACME", "HR")

    assert decision.is_denied is True
    assert decision.to_prompt_payload()["requested_document_types"] == ["COMPANY"]


def test_evaluate_document_access_leaves_named_party_queries_unresolved() -> None:
    decision = evaluate_document_access("Hablame del contrato con Nick Salcedo", "MANAGER")

    assert decision.is_denied is False
    assert decision.to_prompt_payload()["requested_document_types"] == []


def test_extract_contract_party_candidate_returns_entity_name() -> None:
    candidate = extract_contract_party_candidate("Hablame del contrato de Nick Salcedo por favor")

    assert candidate == "nick salcedo"


def test_extract_contract_party_candidate_supports_job_title_queries() -> None:
    candidate = extract_contract_party_candidate("Cual es el puesto de trabajo de Nick Salcedo?")

    assert candidate == "nick salcedo"


def test_evaluate_document_access_allows_generic_queries_for_restricted_roles() -> None:
    decision = evaluate_document_access("Dame los contratos vigentes", "HR")

    assert decision.is_denied is False
    assert decision.to_prompt_payload()["allowed_document_types"] == ["LABOR"]
