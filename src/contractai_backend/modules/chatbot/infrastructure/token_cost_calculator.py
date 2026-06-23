"""Token cost calculator wrapper redirecting to audit module."""

from ...audit.infrastructure.token_cost_calculator import TokenCostCalculator

__all__ = ["TokenCostCalculator"]
