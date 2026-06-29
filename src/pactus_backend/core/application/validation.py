"""Validation helpers shared across application services."""

from pydantic import ValidationError


def format_pydantic_validation_error(exc: ValidationError, default_field: str = "payload") -> str:
    """Formats Pydantic errors into a compact message."""
    messages: list[str] = []

    for error in exc.errors():
        field = error.get("loc", [default_field])[0]
        messages.append(f"{field}: {error.get('msg')}")

    return "; ".join(messages)
