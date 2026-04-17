"""Helpers for automatic payload values used while rendering templates."""

from datetime import datetime

MONTH_NAMES: tuple[str, ...] = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def build_signature_time_payload(now: datetime) -> dict[str, int | str]:
    """Builds the standard signature date placeholders."""
    return {
        "day_sign": now.day,
        "month_sign": MONTH_NAMES[now.month - 1],
        "year_sign": now.year,
    }
