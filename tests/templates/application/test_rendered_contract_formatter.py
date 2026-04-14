"""Tests for rendered contract post-processing."""

from contractai_backend.modules.documents.domain import DocumentType
from contractai_backend.modules.templates.application.services.rendered_contract_formatter import RenderedContractFormatter


class TestRenderedContractFormatter:
    def test_formats_company_signature_block(self):
        formatter = RenderedContractFormatter()

        result = formatter.format(
            "En fe de lo cual, las partes firman el presente contrato.",
            document_type=DocumentType.COMPANY,
            payload={
                "empleador_razon_social": "Hoteles Andinos S.A.C.",
                "representante_nombre": "Juan Perez",
                "gerente_razon_social": "Management Corp S.A.C.",
                "gerente_representante_nombre": "Maria Garcia",
            },
        )

        assert 'data-generated-signatures="true"' in result
        assert "LA EMPRESA" in result
        assert "EL GERENTE" in result
        assert "Hoteles Andinos S.A.C." in result
        assert "Management Corp S.A.C." in result
        assert "Representante: Juan Perez" in result
        assert "Representante: Maria Garcia" in result

    def test_removes_legacy_signature_block_before_appending_generated_one(self):
        formatter = RenderedContractFormatter()

        result = formatter.format(
            "En fe de lo cual, las partes firman el presente contrato.\n\nLA EMPRESA\n\n____________________________\nACME S.A.C.\n\nEL GERENTE\n\n____________________________\nGESTION S.A.C.",
            document_type=DocumentType.COMPANY,
            payload={
                "empleador_razon_social": "ACME S.A.C.",
                "gerente_razon_social": "GESTION S.A.C.",
            },
        )

        assert result.count('data-generated-signatures="true"') == 1
        assert "____________________________" not in result

    def test_keeps_counterparty_representative_row_even_when_blank(self):
        formatter = RenderedContractFormatter()

        result = formatter.format(
            "En fe de lo cual, las partes firman el presente contrato.",
            document_type=DocumentType.COMPANY,
            payload={
                "empleador_razon_social": "ACME S.A.C.",
                "representante_nombre": "Juan Perez",
                "contratista_razon_social": "GESTION S.A.C.",
            },
        )

        assert result.count('class="signature-meta"') == 2
        assert "GESTION S.A.C." in result

    def test_formats_labor_signature_block_with_worker_label(self):
        formatter = RenderedContractFormatter()

        result = formatter.format(
            "En fe de lo cual, las partes firman el presente contrato.",
            document_type=DocumentType.LABOR,
            payload={
                "empleador_razon_social": "ACME S.A.C.",
                "representante_nombre": "Juan Perez",
                "trabajador_nombre": "Ana Torres",
            },
        )

        assert "EL EMPLEADOR" in result
        assert "EL TRABAJADOR" in result
        assert "Ana Torres" in result
