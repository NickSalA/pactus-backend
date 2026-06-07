from pathlib import Path

from markdown2 import markdown
from weasyprint import CSS, HTML

INPUT_PATH = Path("/home/daminin/Documents/Repositorios/ContractAI-Backend/files/CONTRATO_BETA.md")
OUTPUT_PATH = Path("/home/daminin/Documents/Repositorios/ContractAI-Backend/files/CONTRATO_FINAL.pdf")


def generate_legal_pdf(md_content, output_path):
    # 1. Convertir Markdown a HTML
    # 'extras' permite tablas y atributos de HTML
    body_html = markdown(md_content, extras=["tables", "fenced-code-blocks"])

    # 2. Definir el CSS para que parezca un contrato real
    # Aquí controlamos los márgenes y las firmas a los extremos
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
    h1 { text-align: center; text-transform: uppercase; font-size: 14pt; }

    /* Contenedor de Firmas con Flexbox */
    .signature-container {
        display: flex;
        justify-content: space-between;
        margin-top: 80px;
        page-break-inside: avoid; /* Evita que la firma se parta entre páginas */
    }
    .sig-box {
        width: 40%;
        text-align: center;
    }
    .sig-line {
        border-top: 1px solid black;
        margin-bottom: 5px;
    }
    """

    # 3. Estructura completa del HTML con el bloque de firmas inyectado
    full_html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body>
        {body_html}
    </body>
    </html>
    """

    # 4. Generar el PDF
    HTML(string=full_html).write_pdf(output_path, stylesheets=[CSS(string=style)])
    print(f"✅ PDF generado en: {output_path}")


# --- PRUEBA CON TU CONTRATO ---
with INPUT_PATH.open(encoding="utf-8") as f:
    contenido_md = f.read()

generate_legal_pdf(contenido_md, OUTPUT_PATH)
