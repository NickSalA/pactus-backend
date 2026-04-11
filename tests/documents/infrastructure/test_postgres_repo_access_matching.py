"""Tests for relational contract access matching heuristics."""

from contractai_backend.modules.documents.infrastructure.postgres_repo import SQLModelDocumentRepository


def test_viable_party_match_accepts_small_name_typo() -> None:
    assert SQLModelDocumentRepository._is_viable_party_match(
        query="Nick Salcedp",
        candidate="Nick Emanuel Salcedo Alfaro",
    )


def test_viable_party_match_rejects_unrelated_name() -> None:
    assert not SQLModelDocumentRepository._is_viable_party_match(
        query="Nick Salcedo",
        candidate="Jose Medina Sanchez",
    )
