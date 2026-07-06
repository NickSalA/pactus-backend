"""Generic text normalization and string utility functions."""

import re
import unicodedata


def remove_accents(text: str) -> str:
    """Removes diacritics/accents from a string."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_clause_label(label: str) -> str:
    """Normalizes clause labels or headings to uppercase and collapses spaces."""
    no_accents = remove_accents(label)
    return re.sub(r"\s+", " ", no_accents).strip().upper()
