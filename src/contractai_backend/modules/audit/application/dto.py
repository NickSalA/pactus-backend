"""DTOs for the audit module."""

from dataclasses import dataclass


@dataclass
class TokenCostResult:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    model_used: str
