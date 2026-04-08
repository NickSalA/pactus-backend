"""Helpers for compacting reference documents before prompting."""

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

WHITESPACE_PATTERN = re.compile(r"\s+")
MULTI_BLANK_PATTERN = re.compile(r"\n{3,}")
CLAUSE_HEADING_PATTERN = re.compile(
    r"^(cl[aá]usula|art[ií]culo|cap[ií]tulo|secci[oó]n|primera|segunda|tercera|cuarta|quinta|sexta|septima|séptima|octava|novena|d[eé]cima|und[eé]cima|duod[eé]cima)\b",
    re.IGNORECASE,
)
PAGE_LINE_PATTERN = re.compile(r"^(p[aá]gina\s+\d+|\d+\s*/\s*\d+)$", re.IGNORECASE)
CLAUSE_LABEL_PATTERN = re.compile(r"\*\*(?P<label>[A-ZÁÉÍÓÚÑ ]+?)\s*\.\-\*\*", re.IGNORECASE)
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(?P<title>.+)$")
NAMED_STRUCTURE_PATTERN = re.compile(
    r"^(?:\*\*)?(?P<prefix>cl[aá]usula|art[ií]culo|secci[oó]n|cap[ií]tulo)\s+(?P<identifier>[A-Z0-9IVXLCM]+(?:\.\d+)*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TemplateReferenceContext:
    """Stores the prompt reference sent to the LLM."""

    mode: str
    original_chars: int
    clean_chars: int
    clean_text: str
    prompt_text: str
    section_titles: tuple[str, ...]
    clause_sequence: tuple[str, ...]
    structure_sequence: tuple[str, ...]

    def to_prompt_outline(self) -> dict[str, Any]:
        """Builds the outline payload passed to the LLM."""
        return {
            "reference_mode": self.mode,
            "clause_sequence": list(self.clause_sequence),
            "clause_count": len(self.clause_sequence),
            "first_clause": self.clause_sequence[0] if self.clause_sequence else None,
            "last_clause": self.clause_sequence[-1] if self.clause_sequence else None,
            "structure_sequence": list(self.structure_sequence),
            "structure_count": len(self.structure_sequence),
            "section_titles": list(self.section_titles),
            "original_chars": self.original_chars,
            "clean_chars": self.clean_chars,
        }


class TemplateReferencePreprocessor:
    """Builds a compact or full reference from extracted pages."""

    POSITIVE_KEYWORDS = (
        "comparecen",
        "partes",
        "objeto",
        "servicio",
        "plazo",
        "vigencia",
        "remuneracion",
        "remuneración",
        "honorarios",
        "pago",
        "obligaciones",
        "confidencialidad",
        "resolucion",
        "resolución",
        "terminacion",
        "terminación",
    )
    NEGATIVE_KEYWORDS = ("firma", "firmas", "anexo", "anexos", "huella", "sello")
    MAX_REFERENCE_CHARS = 7000
    FULL_REFERENCE_CHAR_THRESHOLD = 6500
    MAX_SECTION_CHARS = 1400
    MAX_SELECTED_SECTIONS = 6

    def build(self, pages: Sequence[Any]) -> TemplateReferenceContext:
        """Builds the final reference context from extracted pages."""
        original_text = "\n\n".join((getattr(page, "text", "") or "").strip() for page in pages if getattr(page, "text", "").strip())
        original_chars = len(original_text)

        page_lines = [self._split_page_lines(page) for page in pages]
        page_lines = [lines for lines in page_lines if lines]
        if not page_lines:
            return TemplateReferenceContext(
                mode="compact",
                original_chars=original_chars,
                clean_chars=0,
                clean_text="",
                prompt_text="",
                section_titles=tuple(),
                clause_sequence=tuple(),
                structure_sequence=tuple(),
            )

        repeated_lines = self._find_repeated_lines(page_lines)
        cleaned_lines = [self._remove_repeated_lines(lines, repeated_lines) for lines in page_lines]
        flat_lines = [line for lines in cleaned_lines for line in lines if line]
        if not flat_lines:
            return TemplateReferenceContext(
                mode="compact",
                original_chars=original_chars,
                clean_chars=0,
                clean_text="",
                prompt_text="",
                section_titles=tuple(),
                clause_sequence=tuple(),
                structure_sequence=tuple(),
            )

        sections = self._split_sections(flat_lines)
        prompt_sections = self._prepare_prompt_sections(sections)
        clean_text = MULTI_BLANK_PATTERN.sub("\n\n", self._compose_clean_document(prompt_sections)).strip()
        clause_sequence = tuple(self._extract_clause_sequence(clean_text))
        structure_sequence = tuple(self._extract_structure_sequence(clean_text))

        full_prompt_text = self._compose_full_clean_prompt(clean_text)
        if clean_text and len(clean_text) <= self.FULL_REFERENCE_CHAR_THRESHOLD:
            prompt_text = full_prompt_text
            section_titles = tuple(title for _, title, _ in prompt_sections if title)
            mode = "full_clean"
        else:
            selected_sections = self._select_sections(sections)
            prompt_text = self._format_prompt_text(selected_sections, flat_lines)
            section_titles = tuple(title for _, title, _ in selected_sections if title)
            mode = "compact"

        return TemplateReferenceContext(
            mode=mode,
            original_chars=original_chars,
            clean_chars=len(clean_text),
            clean_text=clean_text,
            prompt_text=prompt_text,
            section_titles=section_titles,
            clause_sequence=clause_sequence,
            structure_sequence=structure_sequence,
        )

    def _split_page_lines(self, page: Any) -> list[str]:
        """Normalizes lines extracted from a single page."""
        raw_text = getattr(page, "text", "") or ""
        lines: list[str] = []
        for raw_line in raw_text.splitlines():
            line = self._normalize_line_content(raw_line)
            if not line or PAGE_LINE_PATTERN.fullmatch(line) or line == "---":
                continue
            lines.append(line)
        return lines

    def _normalize_line_content(self, raw_line: str) -> str:
        """Normalizes spacing and clause punctuation in a line."""
        line = raw_line.replace("\u00a0", " ").strip()
        line = WHITESPACE_PATTERN.sub(" ", line)
        line = re.sub(r"\*\*(?P<label>[^*]+?)\s+\.\-\*\*", r"**\g<label>.-**", line)
        line = re.sub(r"\*\*(?P<label>[^*]+?)\.\s+\-\*\*", r"**\g<label>.-**", line)
        return line.strip()

    def _find_repeated_lines(self, page_lines: Sequence[list[str]]) -> set[str]:
        """Detects likely headers and footers repeated across pages."""
        counts: Counter[str] = Counter()
        page_count = len(page_lines)
        for lines in page_lines:
            seen_on_page = {self._normalize_line(line) for line in lines if self._is_repeated_line_candidate(line)}
            counts.update(seen_on_page)

        min_page_hits = 2 if page_count <= 2 else max(2, int(page_count * 0.6))
        return {line for line, count in counts.items() if count >= min_page_hits}

    def _remove_repeated_lines(self, lines: Sequence[str], repeated_lines: set[str]) -> list[str]:
        """Removes repeated boilerplate lines from a page."""
        cleaned: list[str] = []
        for line in lines:
            normalized = self._normalize_line(line)
            if normalized in repeated_lines and not self._is_section_heading(line):
                continue
            cleaned.append(line)
        return cleaned

    def _split_sections(self, lines: Sequence[str]) -> list[tuple[str, str]]:
        """Splits the cleaned document into coarse sections."""
        sections: list[tuple[str, str]] = []
        current_title = "Documento"
        current_lines: list[str] = []
        seen_heading = False

        for line in lines:
            if self._is_section_heading(line):
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = line.lstrip("# ").strip()
                current_lines = []
                seen_heading = True
                continue
            current_lines.append(line)

        if current_lines:
            final_title = current_title if seen_heading else "Documento"
            sections.append((final_title, "\n".join(current_lines).strip()))
        return sections

    def _select_sections(self, sections: Sequence[tuple[str, str]]) -> list[tuple[int, str, str]]:
        """Keeps the most useful contiguous sections for prompting."""
        prepared_sections = self._prepare_sections(sections)
        if not prepared_sections:
            return []

        best_window = self._find_best_section_window(prepared_sections)
        if best_window is None:
            index, title, body, _, _ = prepared_sections[0]
            return [(index, title, body)]

        start, end = best_window
        return [(index, title, body) for index, title, body, _, _ in prepared_sections[start : end + 1]]

    def _prepare_sections(self, sections: Sequence[tuple[str, str]]) -> list[tuple[int, str, str, int, int]]:
        """Builds scored sections ready for contiguous selection."""
        prepared: list[tuple[int, str, str, int, int]] = []
        for index, (title, body) in enumerate(sections):
            section_body = self._truncate_text(body, self.MAX_SECTION_CHARS)
            section_text = self._format_section(title, section_body)
            if not section_text:
                continue
            score = self._score_section(title=title, body=body, index=index)
            prepared.append((index, title, section_body, score, len(section_text)))
        return prepared

    def _prepare_prompt_sections(self, sections: Sequence[tuple[str, str]]) -> list[tuple[int, str, str]]:
        """Builds prompt sections without compact truncation."""
        prompt_sections: list[tuple[int, str, str]] = []
        for index, (title, body) in enumerate(sections):
            normalized_body = body.strip()
            if not normalized_body:
                continue
            prompt_sections.append((index, title, normalized_body))
        return prompt_sections

    def _find_best_section_window(
        self,
        sections: Sequence[tuple[int, str, str, int, int]],
    ) -> tuple[int, int] | None:
        """Selects the best contiguous section window within budget."""
        best_window: tuple[int, int] | None = None
        best_metrics: tuple[int, int, int, int] | None = None

        for start in range(len(sections)):
            for end in range(start, min(len(sections), start + self.MAX_SELECTED_SECTIONS)):
                candidate_sections = [(index, title, body) for index, title, body, _, _ in sections[start : end + 1]]
                candidate_text = self._compose_prompt_text(candidate_sections)
                if len(candidate_text) > self.MAX_REFERENCE_CHARS:
                    break

                candidate_score = sum(score for _, _, _, score, _ in sections[start : end + 1])
                if start == 0:
                    candidate_score += 2

                metrics = (candidate_score, len(candidate_sections), -start, -len(candidate_text))
                if best_metrics is None or metrics > best_metrics:
                    best_metrics = metrics
                    best_window = (start, end)

        return best_window

    def _format_prompt_text(self, sections: Sequence[tuple[int, str, str]], lines: Sequence[str]) -> str:
        """Formats the compact reference block for the prompt."""
        if not sections:
            return self._truncate_text("\n".join(lines), self.MAX_REFERENCE_CHARS)
        return self._truncate_text(self._compose_prompt_text(sections), self.MAX_REFERENCE_CHARS)

    def _compose_prompt_text(self, sections: Sequence[tuple[int, str, str]]) -> str:
        """Builds the prompt text without applying the global cap."""
        if not sections:
            return ""

        titles = [f"- {title}" for _, title, _ in sections if title]
        formatted_sections = [self._format_section(title, body) for _, title, body in sections]
        formatted_sections = [section for section in formatted_sections if section]
        prompt_parts: list[str] = []
        if titles:
            prompt_parts.append("SECTION_TITLES:\n" + "\n".join(titles))
        if formatted_sections:
            prompt_parts.append("REFERENCE_EXCERPT:\n" + "\n\n".join(formatted_sections))
        return MULTI_BLANK_PATTERN.sub("\n\n", "\n\n".join(prompt_parts)).strip()

    def _compose_clean_document(self, sections: Sequence[tuple[int, str, str]]) -> str:
        """Builds the cleaned document used for outline and full mode."""
        parts = [self._format_section(title, body) for _, title, body in sections]
        parts = [part for part in parts if part]
        return MULTI_BLANK_PATTERN.sub("\n\n", "\n\n".join(parts)).strip()

    def _compose_full_clean_prompt(self, clean_text: str) -> str:
        """Builds the prompt payload for short documents."""
        if not clean_text:
            return ""
        return f"FULL_CLEAN_REFERENCE:\n{clean_text}"

    def _score_section(self, title: str, body: str, index: int) -> int:
        """Scores a section based on likely drafting relevance."""
        haystack = f"{title}\n{body}".lower()
        score = 3 if index == 0 else 0
        score += sum(2 for keyword in self.POSITIVE_KEYWORDS if keyword in haystack)
        score -= sum(3 for keyword in self.NEGATIVE_KEYWORDS if keyword in haystack)
        return score

    def _is_section_heading(self, line: str) -> bool:
        """Checks whether a line looks like a section heading."""
        stripped = line.strip()
        plain = stripped.lstrip("# ").strip()
        if not plain or len(plain) > 120:
            return False
        if stripped.startswith("#"):
            return True
        if CLAUSE_HEADING_PATTERN.match(plain):
            return True
        return plain.isupper() and 1 < len(plain.split()) <= 12

    def _is_repeated_line_candidate(self, line: str) -> bool:
        """Checks whether a line may be page boilerplate."""
        normalized = self._normalize_line(line)
        if not normalized or self._is_section_heading(line):
            return False
        return len(normalized) <= 120 and len(normalized.split()) <= 12

    def _normalize_line(self, line: str) -> str:
        """Builds a normalized key for duplicate detection."""
        return WHITESPACE_PATTERN.sub(" ", line).strip().lower()

    def _extract_clause_sequence(self, text: str) -> list[str]:
        """Extracts clause labels in order from the cleaned text."""
        labels: list[str] = []
        for match in CLAUSE_LABEL_PATTERN.finditer(text):
            raw_label = match.group("label").strip()
            labels.append(self._normalize_clause_label(raw_label))
        return labels

    def _extract_structure_sequence(self, text: str) -> list[str]:
        """Extracts generic structural markers from the cleaned text."""
        markers: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            heading_match = MARKDOWN_HEADING_PATTERN.match(line)
            if heading_match:
                title = heading_match.group("title").strip().strip("*")
                markers.append(f"HEADING:{self._normalize_clause_label(title)}")
                continue

            named_match = NAMED_STRUCTURE_PATTERN.match(line.strip("*"))
            if named_match:
                prefix = self._normalize_clause_label(named_match.group("prefix"))
                identifier = self._normalize_clause_label(named_match.group("identifier"))
                markers.append(f"{prefix}:{identifier}")
                continue

            clause_match = CLAUSE_LABEL_PATTERN.search(line)
            if clause_match:
                label = self._normalize_clause_label(clause_match.group("label"))
                markers.append(f"CLAUSE:{label}")

        return markers

    def _normalize_clause_label(self, label: str) -> str:
        """Normalizes clause labels for consistent comparison."""
        normalized = unicodedata.normalize("NFD", label)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = re.sub(r"\s+", " ", normalized).strip().upper()
        return normalized

    def _format_section(self, title: str, body: str) -> str:
        """Formats a selected section for the prompt."""
        body = body.strip()
        if not body:
            return ""
        if title:
            return f"## {title}\n{body}"
        return body

    def _truncate_text(self, text: str, limit: int) -> str:
        """Truncates text without cutting a word in the middle."""
        if limit <= 0:
            return ""
        if len(text) <= limit:
            return text
        truncated = text[:limit].rsplit(" ", 1)[0].strip()
        return f"{truncated} ..." if truncated else text[:limit]
