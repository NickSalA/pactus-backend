"""Application DTOs for the chatbot module."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from ...documents.domain.value_objs import DocumentType

# ---------------------------------------------------------------------------
# Chart DTOs (Pydantic — serializable for JSONB and API responses)
# ---------------------------------------------------------------------------


class ChartSeriesConfig(BaseModel):
    """One series definition for the frontend chart."""

    dataKey: str  # noqa: N815
    name: str
    color: str | None = None


class ChartConfig(BaseModel):
    """Axis and series configuration consumed by the frontend chart."""

    categoryKey: str  # noqa: N815
    series: list[ChartSeriesConfig]


class ChartData(BaseModel):
    """Complete payload the frontend needs to render a chart (Recharts-compatible)."""

    type: Literal["bar", "line", "pie"]
    layout: Literal["vertical", "horizontal", "centric"]
    title: str
    config: ChartConfig
    data: list[dict[str, str | int | float]]


@dataclass
class LLMResult:
    response: str
    thread_id: int
    chart: ChartData | None = None
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


@dataclass
class TokenUsageSummaryDTO:
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_input_cost_usd: Decimal
    total_output_cost_usd: Decimal
    total_cost_usd: Decimal
    usage_count: int


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
