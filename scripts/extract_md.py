"""Extract markdown from a PDF contract using LlamaParse."""

import asyncio
from pathlib import Path

from pactus_backend.modules.documents.infrastructure.llama_parser import LlamaParseExtractor

input_pdf = Path("/home/daminin/Documents/Repositorios/ContractAI-Backend/files/contrato_003-1.pdf")
output_md = Path("/home/daminin/Documents/Repositorios/ContractAI-Backend/files/CONTRATO_BETA_003-1.md")


async def main():
    """Run the extraction workflow and persist the markdown output."""
    if not input_pdf.exists():
        print(f"❌ Error: No se encuentra el archivo {input_pdf}")
        return

    print(f"🚀 Iniciando extracción de: {input_pdf}...")

    # 2. Instanciar tu extractor
    extractor = LlamaParseExtractor()

    try:
        # 3. Leer el archivo en bytes
        with input_pdf.open("rb") as f:
            file_bytes = f.read()

        # 4. Llamar a tu método extract (que ya devuelve la lista de chunks con metadata)
        chunks = await extractor.extract(file=file_bytes, filename=str(input_pdf))

        print(f"✅ Se procesaron {len(chunks)} páginas.")

        with output_md.open("w", encoding="utf-8") as f_out:
            for chunk in chunks:
                if hasattr(chunk, "get_content"):
                    content = chunk.get_content()
                elif hasattr(chunk, "text"):
                    content = chunk.text
                else:
                    content = chunk["content"]

                f_out.write("\n")
                f_out.write(content)
                f_out.write("\n\n\n---\n\n")

        print(f"✨ ¡Listo! El Markdown ha sido guardado en: {output_md}")

    except Exception as e:
        print(f"💥 Error durante la extracción: {e!s}")


if __name__ == "__main__":
    # Ejecutamos el loop asíncrono
    asyncio.run(main())
