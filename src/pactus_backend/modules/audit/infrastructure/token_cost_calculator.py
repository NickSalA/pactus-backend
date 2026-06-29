"""Token cost calculator for AI LLM usage."""

from ....shared.config import settings
from ..application.dto import TokenCostResult


class TokenCostCalculator:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.GEMINI_MODEL_NAME
        self.input_price_per_m = settings.GEMINI_INPUT_PRICE_PER_M
        self.output_price_per_m = settings.GEMINI_OUTPUT_PRICE_PER_M

    def calculate(self, input_tokens: int, output_tokens: int) -> TokenCostResult:
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_m
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_m
        total_cost = input_cost + output_cost
        return TokenCostResult(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost_usd=round(input_cost, 8),
            output_cost_usd=round(output_cost, 8),
            total_cost_usd=round(total_cost, 8),
            model_used=self.model_name,
        )
