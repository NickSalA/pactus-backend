"""Template format helpers."""

import re

FORMAT_CODE_PATTERN: re.Pattern[str] = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def normalize_format_code(value: str) -> str:
    """Normalizes and validates a template format code."""
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized or not FORMAT_CODE_PATTERN.fullmatch(normalized):
        raise ValueError("format_code must be a lowercase slug using letters, numbers and underscores")
    return normalized
