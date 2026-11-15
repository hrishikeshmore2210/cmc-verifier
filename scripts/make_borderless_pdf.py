"""Generate a BORDERLESS sample CoA (run once) — the hard extraction case.

    python scripts/make_borderless_pdf.py

Produces data/sample/sources/coa_B008.pdf: same shape as coa_B007 but the table
has NO ruling lines, so pdfplumber cannot find it by lines and must fall back to
text-alignment. Requires: pip install reportlab
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).parent.parent / "data" / "sample" / "sources" / "coa_B008.pdf"


def build():
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(OUT), pagesize=LETTER)
    story = [
        Paragraph("CERTIFICATE OF ANALYSIS", styles["Title"]),
        Paragraph("Product: Acme Tablets 10 mg", styles["Normal"]),
        Paragraph("Batch No.: B-008", styles["Normal"]),
        Paragraph("Date of Manufacture: 25-Apr-2026", styles["Normal"]),
        Spacer(1, 16),
    ]
    data = [
        ["Test", "Method", "Result", "Units"],
        ["Assay", "HPLC", "98.9 %", "%"],
        ["Related Substances - Total", "HPLC", "0.41 %", "%"],
        ["Water Content", "KF", "3.5 %", "%"],
    ]
    # wide first column so nothing wraps; NO grid style -> borderless
    table = Table(data, colWidths=[210, 90, 90, 60], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()