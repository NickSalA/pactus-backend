"""Módulo encargado de convertir el Markdown generado por el módulo de templates a PDF, utilizando WeasyPrint."""

from markdown2 import UnicodeWithAttrs, markdown
from weasyprint import CSS, HTML

from ..application.repositories.base_generate import IDocumentGenerator


class WeasyPrintGenerator(IDocumentGenerator):
    async def generate_pdf(self, markdown_content: str) -> bytes:
        """Convierte Markdown a PDF y retorna los bytes para que el módulo de documentos se encargue de guardarlos."""
        body_html: UnicodeWithAttrs = markdown(text=markdown_content, extras=["tables", "fenced_code-blocks"])
        style = """
        @page {
            size: A4;
            margin: 2.5cm;
            @bottom-right {
                content: "Página " counter(page) " de " counter(pages);
                font-size: 9pt;
            }
        }
        body {
            font-family: 'Times New Roman', serif;
            line-height: 1.5;
            text-align: justify;
            font-size: 11pt;
        }
        h1 {
            text-align: center;
            text-transform: uppercase;
            font-size: 16pt;
            margin: 0 0 18pt;
        }
        h2 {
            font-size: 13.5pt;
            margin: 18pt 0 10pt;
            font-weight: bold;
        }
        h3 {
            font-size: 12pt;
            margin: 14pt 0 8pt;
            font-weight: bold;
        }
        h4, h5, h6 {
            font-size: 11pt;
            margin: 12pt 0 6pt;
            font-weight: bold;
        }
        p {
            margin: 0 0 10pt;
        }

        .signature-section {
            margin-top: 56pt;
            page-break-inside: avoid;
        }
        .signature-grid {
            display: flex;
            justify-content: space-between;
            gap: 28pt;
        }
        .signature-card {
            width: 40%;
            text-align: center;
        }
        .signature-line {
            border-top: 1px solid black;
            margin: 0 auto 10pt;
            width: 85%;
        }
        .signature-title {
            font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 4pt;
        }
        .signature-name {
            font-size: 10.5pt;
            margin-bottom: 4pt;
        }
        .signature-meta {
            font-size: 9.5pt;
            color: #333;
        }
        """

        full_html = f"""
        <html>
        <head><meta charset="utf-8"></head>
        <body>
            {body_html}
        </body>
        </html>
        """
        pdf_bytes: bytes = HTML(string=full_html).write_pdf(stylesheets=[CSS(string=style)])

        return pdf_bytes
