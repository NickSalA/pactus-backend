"""Tests for relational contract access matching heuristics."""

from pactus_backend.modules.documents.infrastructure.query_repo import SQLModelDocumentQueryRepository


def test_viable_party_match_accepts_small_name_typo() -> None:
    assert SQLModelDocumentQueryRepository._is_viable_party_match(
        query="Nick Salcedp",
        candidate="Nick Emanuel Salcedo Alfaro",
    )


def test_viable_party_match_rejects_unrelated_name() -> None:
    assert not SQLModelDocumentQueryRepository._is_viable_party_match(
        query="Nick Salcedo",
        candidate="Jose Medina Sanchez",
    )
