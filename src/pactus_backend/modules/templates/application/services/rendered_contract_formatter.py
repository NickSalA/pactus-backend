"""Post-processes rendered contracts for preview and PDF output."""

import html
from dataclasses import dataclass
from typing import Any

from ....documents.domain import DocumentType
from ...domain.patterns import (
    CLOSING_LINE_PATTERN,
    SIGNATURE_BLOCK_MARKER,
    SIGNATURE_PLACEHOLDER_KEYS,
    SIGNATURE_PLACEHOLDER_PATTERN,
    SIGNATURE_TITLE_PATTERN,
    UNDERSCORE_LINE_PATTERN,
)


@dataclass(frozen=True)
class SignatureParty:
    title: str
    name: str | None = None
    subtitle: str | None = None


class RenderedContractFormatter:
    """Applies output-only formatting such as signature blocks."""

    def format(self, markdown: str, *, document_type: DocumentType, payload: dict[str, Any]) -> str:
        """Formats rendered markdown for output-specific presentation."""
        normalized_markdown = self.strip_signature_blocks(markdown)
        if signature_block := self._build_signature_block(
            document_type=document_type, payload=payload
        ):
            return f"{normalized_markdown}\n\n{signature_block}" if normalized_markdown else signature_block
        else:
            return normalized_markdown

    def strip_signature_blocks(self, markdown: str) -> str:
        """Removes generated or legacy signature sections from markdown."""
        normalized_markdown = markdown.rstrip()
        normalized_markdown = self._strip_generated_signature_block(normalized_markdown)
        return self._strip_legacy_signature_block(normalized_markdown)

    def _strip_generated_signature_block(self, markdown: str) -> str:
        """Avoids duplicating a previously formatted signature block."""
        marker_index = markdown.find(SIGNATURE_BLOCK_MARKER)
        if marker_index == -1:
            return markdown
        start_index = markdown.rfind("<div", 0, marker_index)
        if start_index == -1:
            return markdown[:marker_index].rstrip()
        return markdown[:start_index].rstrip()

    def _strip_legacy_signature_block(self, markdown: str) -> str:
        """Removes old plain-text signature areas based on underscore lines."""
        lines = markdown.splitlines()
        if not lines:
            return markdown

        last_non_empty_index = next((index for index in range(len(lines) - 1, -1, -1) if lines[index].strip()), -1)
        if last_non_empty_index == -1:
            return markdown

        search_start = max(0, last_non_empty_index - 18)
        underscore_index = next(
            (index for index in range(last_non_empty_index, search_start - 1, -1) if UNDERSCORE_LINE_PATTERN.match(lines[index].strip())),
            None,
        )
        if underscore_index is None:
            return markdown

        trim_index = underscore_index
        while trim_index > 0 and self._looks_like_signature_line(lines[trim_index - 1]):
            trim_index -= 1

        return "\n".join(lines[:trim_index]).rstrip()

    def _looks_like_signature_line(self, line: str) -> bool:
        """Heuristically identifies lines that belong to a legacy signature block."""
        stripped = line.strip().strip("*")
        if not stripped:
            return True
        if UNDERSCORE_LINE_PATTERN.match(stripped):
            return True
        if SIGNATURE_TITLE_PATTERN.fullmatch(stripped):
            return True
        if self._is_signature_placeholder_line(stripped):
            return True
        if CLOSING_LINE_PATTERN.match(stripped):
            return False
        alpha_count = sum(bool(char.isalpha())
                        for char in stripped)
        uppercase_ratio = sum(bool(char.isupper())
                        for char in stripped) / max(1, alpha_count)
        if len(stripped) <= 60 and uppercase_ratio >= 0.35:
            return True
        if len(stripped) > 90:
            return False
        if stripped.endswith(".") or stripped.endswith(":"):
            return False
        return uppercase_ratio >= 0.45 or stripped.replace(" ", "").isalnum()

    def _is_signature_placeholder_line(self, stripped_line: str) -> bool:
        """Detects placeholder-only lines commonly used inside legacy signature blocks."""
        match = SIGNATURE_PLACEHOLDER_PATTERN.fullmatch(stripped_line)
        if match is None:
            return False
        return match.group("key") in SIGNATURE_PLACEHOLDER_KEYS

    def _build_signature_block(self, *, document_type: DocumentType, payload: dict[str, Any]) -> str:
        """Builds a standardized HTML signature block."""
        parties = self._resolve_signature_parties(document_type=document_type, payload=payload)
        cards = "".join(self._build_signature_card(party) for party in parties)
        return f'<div class="signature-section" data-generated-signatures="true"><div class="signature-grid">{cards}</div></div>'

    def _resolve_signature_parties(self, *, document_type: DocumentType, payload: dict[str, Any]) -> list[SignatureParty]:
        """Resolves signer blocks according to contract type."""
        employer_name = self._first_non_empty_value(payload, "empleador_razon_social")
        employer_representative = self._first_non_empty_value(payload, "representante_nombre", "representante_nombre_empresa")

        if document_type == DocumentType.LABOR:
            worker_name = self._first_non_empty_value(payload, "trabajador_nombre", "cliente_nombre")
            worker_identifier = self._first_non_empty_value(payload, "trabajador_dni")
            return [
                SignatureParty(
                    title="EL EMPLEADOR",
                    name=employer_name,
                    subtitle=self._build_representative_subtitle(employer_representative),
                ),
                SignatureParty(
                    title="EL TRABAJADOR",
                    name=worker_name,
                    subtitle=f"DNI: {worker_identifier}" if worker_identifier else None,
                ),
            ]

        counterparty_name = self._first_non_empty_value(
            payload,
            "gerente_razon_social",
            "contratista_razon_social",
            "cliente_nombre",
            "trabajador_nombre",
        )
        counterparty_representative = self._first_non_empty_value(
            payload,
            "gerente_representante_nombre",
            "contratista_representante_nombre",
            "representante_nombre_contratista",
            "representante_nombre_gerente",
            "contratista_nombre_representante",
            "gerente_nombre_representante",
        )
        counterparty_title = self._resolve_company_counterparty_title(payload=payload)
        return [
            SignatureParty(
                title="LA EMPRESA",
                name=employer_name,
                subtitle=self._build_representative_subtitle(employer_representative),
            ),
            SignatureParty(
                title=counterparty_title,
                name=counterparty_name,
                subtitle=self._build_representative_subtitle(counterparty_representative),
            ),
        ]

    def _resolve_company_counterparty_title(self, *, payload: dict[str, Any]) -> str:
        """Picks the most natural label for the second signer in company contracts."""
        if self._first_non_empty_value(payload, "gerente_razon_social", "gerente_representante_nombre"):
            return "EL GERENTE"
        if self._first_non_empty_value(payload, "contratista_razon_social", "representante_nombre_contratista"):
            return "LA CONTRATISTA"
        return "LA CONTRAPARTE"

    def _build_signature_card(self, party: SignatureParty) -> str:
        """Builds one signature card HTML snippet."""
        escaped_title = html.escape(party.title)
        escaped_name = html.escape(party.name) if party.name else "&nbsp;"
        escaped_subtitle = html.escape(party.subtitle) if party.subtitle else "&nbsp;"
        subtitle_html = f'<div class="signature-meta">{escaped_subtitle}</div>'
        return (
            '<div class="signature-card">'
            '<div class="signature-line"></div>'
            f'<div class="signature-title">{escaped_title}</div>'
            f'<div class="signature-name">{escaped_name}</div>'
            f"{subtitle_html}"
            "</div>"
        )

    def _build_representative_subtitle(self, representative_name: str | None) -> str | None:
        """Builds a representative subtitle when present."""
        return f"Representante: {representative_name}" if representative_name else None

    def _first_non_empty_value(self, payload: dict[str, Any], *keys: str) -> str | None:
        """Returns the first non-empty value among the provided keys."""
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                if cleaned := value.strip():
                    return cleaned
                continue
            return str(value)
        return None
