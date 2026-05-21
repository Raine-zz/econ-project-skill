"""
PDF Report generator — creates a formatted PDF of tracked programmes.
Uses fpdf2 for lightweight PDF generation.
"""

import logging
from datetime import date
from pathlib import Path

from fpdf import FPDF

logger = logging.getLogger(__name__)


def generate_pdf(
    records: list[dict],
    output_dir: str | None = None,
) -> str:
    """
    Generate a PDF report and return the file path.
    Columns: Institution | Program | Degree | Country | Deadline | Importance
    """
    if output_dir is None:
        output_dir = str(Path(__file__).resolve().parent.parent / "data")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = str(Path(output_dir) / f"econ_report_{date.today().isoformat()}.pdf")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Econ Programme Report — {date.today().isoformat()}", ln=True)
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Total programmes: {len(records)}", ln=True)
    pdf.ln(4)

    # Columns
    col_widths = [48, 58, 18, 22, 24, 16]  # total ≈ 186 (A4 is 190 with margins)
    headers = ["Institution", "Program", "Degree", "Country", "Deadline", "Imp"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    for i, (h, w) in enumerate(zip(headers, col_widths)):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    # Data rows
    pdf.set_font("Helvetica", "", 7)
    sorted_records = sorted(records, key=lambda r: r.get("importance", 0), reverse=True)

    for r in sorted_records:
        imp = r.get("importance", 0)
        # Highlight high importance
        if imp >= 7:
            pdf.set_text_color(200, 0, 0)
        else:
            pdf.set_text_color(0, 0, 0)

        values = [
            _truncate(r.get("institution", ""), 28),
            _truncate(r.get("program", ""), 34),
            _truncate(r.get("degree_type", ""), 10),
            _truncate(r.get("country", ""), 12),
            _truncate(r.get("due_date", "N/A"), 12),
            str(imp),
        ]
        for v, w in zip(values, col_widths):
            pdf.cell(w, 6, v, border=1)
        pdf.ln()

    pdf.output(filepath)
    logger.info(f"PDF generated: {filepath}")
    return filepath


def _truncate(text: str, max_len: int) -> str:
    if len(text) > max_len:
        return text[: max_len - 2] + ".."
    return text
