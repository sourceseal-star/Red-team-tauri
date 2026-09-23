from pathlib import Path

import fitz


pdf_path = Path("attached_assets/Documento_(2)_1790122694499.pdf")
output_dir = Path(".agents/outputs/supergate-pdf")
output_dir.mkdir(parents=True, exist_ok=True)

with fitz.open(pdf_path) as document:
    print(f"pages={document.page_count}")
    for index, page in enumerate(document):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        output = output_dir / f"page-{index + 1:02d}.png"
        pixmap.save(output)
        print(output)