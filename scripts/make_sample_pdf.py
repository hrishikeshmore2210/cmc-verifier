"""Generate the sample CoA PDF fixture (run once).

    python scripts/make_sample_pdf.py

Produces data/sample/sources/coa_B007.pdf — a realistic single-page Certificate
of Analysis with a title, a key/value preamble (batch + date as free text), and a
bordered results table. Requires: pip install reportlab
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).parent.parent / "data" / "sample" / "sources" / "coa_B007.pdf"


def build():
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(OUT), pagesize=LETTER)
    story = [
        Paragraph("CERTIFICATE OF ANALYSIS", styles["Title"]),
        Paragraph("Product: Acme Tablets 10 mg", styles["Normal"]),
        Paragraph("Batch No.: B-007", styles["Normal"]),
        Paragraph("Date of Manufacture: 10-Apr-2026", styles["Normal"]),
        Spacer(1, 16),
    ]
    data = [
        ["Test", "Method", "Result", "Units"],
        ["Assay", "HPLC", "100.1 %", "%"],
        ["Related Substances - Total", "HPLC", "0.28 %", "%"],
        ["Water Content", "KF", "2.9 %", "%"],
    ]
    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(table)
    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
