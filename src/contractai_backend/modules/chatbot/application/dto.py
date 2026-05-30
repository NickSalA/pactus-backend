"""Application DTOs for the chatbot module."""

from dataclasses import dataclass

from ...documents.domain.value_objs import DocumentType


@dataclass
class LLMResult:
    response: str
    thread_id: int
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model_used: str = ""


@dataclass
class TokenCostResult:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    model_used: str


@dataclass(frozen=True)
class DocumentAccessDecision:
    allowed_document_types: frozenset[DocumentType] | None
    requested_document_types: frozenset[DocumentType]
    denied_document_types: frozenset[DocumentType]

    @property
    def is_denied(self) -> bool:
        return bool(self.denied_document_types)

    @staticmethod
    def _serialize_types(doc_types: frozenset[DocumentType] | None) -> list[str] | None:
        if doc_types is None:
            return None
        return [dt.value for dt in sorted(doc_types, key=lambda x: x.value)]

    def to_prompt_payload(self) -> dict[str, object]:
        return {
            "allowed_document_types": self._serialize_types(self.allowed_document_types),
            "requested_document_types": self._serialize_types(self.requested_document_types) or [],
            "denied_document_types": self._serialize_types(self.denied_document_types) or [],
            "must_deny": self.is_denied,
        }
