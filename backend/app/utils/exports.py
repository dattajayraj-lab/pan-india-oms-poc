"""Bilingual exports: Hindi text placed before English text (TS Ch.9 p.59, Cl. 11.4.10 p.208; FRD MIS-05).

PDF uses a Devanagari-capable TrueType font when one is available on the host (Windows
'Nirmala UI'; on RHEL a licensed Noto/Lohit font). ReportLab does not perform complex-script
shaping, so conjunct rendering is approximate in this POC; production will use a shaping
engine (HarfBuzz via WeasyPrint/LibreOffice) — noted in README.
"""
import csv
import io
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FONT = "Helvetica"
_FONT_CANDIDATES = [
    ("C:/Windows/Fonts/Nirmala.ttc", 0), ("C:/Windows/Fonts/Nirmala.ttf", None), ("C:/Windows/Fonts/mangal.ttf", None),
    ("/usr/share/fonts/google-noto/NotoSansDevanagari-Regular.ttf", None),
    ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", None),
]
for _path, _idx in _FONT_CANDIDATES:
    if Path(_path).exists():
        try:
            pdfmetrics.registerFont(TTFont("Deva", _path, subfontIndex=_idx) if _idx is not None else TTFont("Deva", _path))
            _FONT = "Deva"
            break
        except Exception:  # noqa: BLE001
            continue

# column spec: (key, label_en, label_hi)
Column = tuple[str, str, str]


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d-%m-%Y %H:%M")
    return str(v)


def bilingual_pdf(title_en: str, title_hi: str, columns: list[Column], rows: list[dict],
                  subtitle: str = "", footer_note: str = "") -> bytes:
    buf = io.BytesIO()
    wide = len(columns) > 6
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4) if wide else A4, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title=title_en)
    h_hi = ParagraphStyle("hhi", fontName=_FONT, fontSize=14, leading=18, textColor=colors.HexColor("#0b3a6e"))
    h_en = ParagraphStyle("hen", fontName=_FONT, fontSize=12, leading=15, textColor=colors.HexColor("#0b3a6e"))
    small = ParagraphStyle("sm", fontName=_FONT, fontSize=8, leading=10, textColor=colors.grey)
    cell = ParagraphStyle("cell", fontName=_FONT, fontSize=7, leading=9)
    head = ParagraphStyle("head", fontName=_FONT, fontSize=7, leading=9, textColor=colors.white)
    story = [Paragraph("ग्रिड कंट्रोलर ऑफ इंडिया लिमिटेड · प्रचालन प्रबंधन प्रणाली", small),
             Paragraph("Grid Controller of India Ltd · Operations Management System", small), Spacer(1, 4),
             Paragraph(title_hi or title_en, h_hi), Paragraph(title_en, h_en)]
    if subtitle:
        story.append(Paragraph(subtitle, small))
    story.append(Paragraph(f"उत्पन्न / Generated: {datetime.now():%d-%m-%Y %H:%M}", small))
    story.append(Spacer(1, 6))
    data = [[Paragraph(f"{hi or en}<br/>{en}", head) for _, en, hi in columns]]
    for r in rows:
        data.append([Paragraph(_cell(r.get(k)).replace("&", "&amp;").replace("<", "&lt;"), cell) for k, _, _ in columns])
    if len(data) == 1:
        data.append([Paragraph("कोई रिकॉर्ड नहीं / No records", cell)] + [""] * (len(columns) - 1))
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3a6e")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    if footer_note:
        story += [Spacer(1, 6), Paragraph(footer_note, small)]
    doc.build(story)
    return buf.getvalue()


def bilingual_xlsx(title_en: str, title_hi: str, columns: list[Column], rows: list[dict],
                   sheets: dict[str, list[dict]] | None = None) -> bytes:
    """Single sheet (rows) or multiple named sheets (sheets) with identical columns."""
    wb = Workbook()
    wb.remove(wb.active)
    for name, data in (sheets or {"Report": rows}).items():
        ws = wb.create_sheet(name[:31])
        ws.append([title_hi or title_en])
        ws.append([title_en])
        ws["A1"].font = Font(bold=True, size=13, color="0B3A6E")
        ws["A2"].font = Font(bold=True, size=12, color="0B3A6E")
        ws.append([hi or en for _, en, hi in columns])
        ws.append([en for _, en, _ in columns])
        fill = PatternFill("solid", fgColor="0B3A6E")
        for row in (3, 4):
            for c in ws[row]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = fill
                c.alignment = Alignment(wrap_text=True)
        for r in data:
            ws.append([_cell(r.get(k)) if isinstance(r.get(k), datetime) else r.get(k) for k, _, _ in columns])
        for i, _ in enumerate(columns, start=1):
            ws.column_dimensions[ws.cell(row=4, column=i).column_letter].width = 22
        ws.freeze_panes = "A5"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_csv(columns: list[Column], rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"{hi} / {en}" if hi else en for _, en, hi in columns])
    for r in rows:
        w.writerow([_cell(r.get(k)) for k, _, _ in columns])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def file_response(content: bytes, filename: str):
    from fastapi.responses import Response

    media = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "csv": "text/csv"}[filename.rsplit(".", 1)[-1]]
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def export(fmt: str, title_en: str, title_hi: str, columns: list[Column], rows: list[dict], basename: str, **kw):
    fmt = fmt.lower()
    if fmt == "pdf":
        return file_response(bilingual_pdf(title_en, title_hi, columns, rows, **kw), f"{basename}.pdf")
    if fmt == "csv":
        return file_response(to_csv(columns, rows), f"{basename}.csv")
    return file_response(bilingual_xlsx(title_en, title_hi, columns, rows), f"{basename}.xlsx")
