"""Service for classifying and validating reference document types."""

import re
import unicodedata

from ....documents.domain import DocumentType
from ...domain.exceptions import TemplateReferenceError
from ...domain.patterns import COMPANY_CLASSIFIER_PATTERNS, LABOR_CLASSIFIER_PATTERNS
from .template_reference_preprocessor import TemplateReferenceContext


class TemplateReferenceService:
    """Handles classification and validation of uploaded reference documents."""

    def validate_reference_document_type(
        self,
        reference_context: TemplateReferenceContext,
        expected_document_type: DocumentType,
    ) -> None:
        """Validates that the uploaded file matches the expected base type."""
        detected_document_type = self.classify_reference_document_type(reference_context.clean_text)
        if detected_document_type is None:
            raise TemplateReferenceError("No se pudo determinar si el archivo corresponde a COMPANY o LABOR.")
        if detected_document_type != expected_document_type:
            raise TemplateReferenceError(f"El archivo no corresponde a una plantilla de tipo {expected_document_type.value}.")

    def classify_reference_document_type(self, clean_text: str) -> DocumentType | None:
        """Classifies a reference document as COMPANY or LABOR using heuristics."""
        normalized_text = self._normalize_reference_text(clean_text)
        labor_score = self._score_classifier_patterns(normalized_text, LABOR_CLASSIFIER_PATTERNS)
        company_score = self._score_classifier_patterns(normalized_text, COMPANY_CLASSIFIER_PATTERNS)

        if labor_score == 0 and company_score == 0:
            return None
        if company_score >= labor_score + 2:
            return DocumentType.COMPANY
        return DocumentType.LABOR if labor_score >= company_score + 2 else None

    def _score_classifier_patterns(self, text: str, patterns: tuple[tuple[str, int], ...]) -> int:
        """Scores a normalized reference text using weighted regex patterns."""
        return sum(weight for pattern, weight in patterns if re.search(pattern, text))

    def _normalize_reference_text(self, value: str) -> str:
        """Normalizes extracted text for heuristic matching."""
        normalized = unicodedata.normalize("NFD", value)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return re.sub(r"\s+", " ", normalized).strip().lower()
