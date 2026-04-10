"""Tests for chatbot access helpers."""

from contractai_backend.modules.chatbot.infrastructure.agent.access import ROLE_PERMISSION_DENIED_RESPONSE, evaluate_document_access


def test_evaluate_document_access_denies_company_queries_for_hr() -> None:
    decision = evaluate_document_access("Dame contratos con empresas activas", "HR")

    assert decision.is_denied is True
    assert decision.to_prompt_payload()["must_deny"] is True


def test_evaluate_document_access_denies_labor_queries_for_manager() -> None:
    decision = evaluate_document_access("Muestrame contratos con trabajadores", "MANAGER")

    assert decision.is_denied is True
    assert ROLE_PERMISSION_DENIED_RESPONSE == "No tienes permisos para acceder a esa informacion."


def test_evaluate_document_access_allows_generic_queries_for_restricted_roles() -> None:
    decision = evaluate_document_access("Dame los contratos vigentes", "HR")

    assert decision.is_denied is False
    assert decision.to_prompt_payload()["allowed_document_types"] == ["LABOR"]
