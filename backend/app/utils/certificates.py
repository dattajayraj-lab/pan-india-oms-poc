"""Template-driven certificate / letter / annexure PDFs with optional signature (TS Cl. 11.2(h); FRD CMN-22).

Production signs with the officer's DSC (PKCS#7 / PAdES) via the e-Sign/DSC integration (TS Cl. 10.3(j));
the POC embeds the uploaded signature image and records signer, time and SHA-256 in the footer.
"""
import hashlib
import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.utils import exports  # registers the Devanagari font

FONT = exports._FONT


def render_pdf(title_en: str, title_hi: str, ref: str, fields: list[tuple[str, object]], body: str = "",
               signer=None, signer_role: str = "", draft: bool = False) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title=title_en)
    st = lambda size, **kw: ParagraphStyle("x", fontName=FONT, fontSize=size, leading=size * 1.35, **kw)  # noqa: E731
    story = [Paragraph("ग्रिड कंट्रोलर ऑफ इंडिया लिमिटेड", st(12, textColor=colors.HexColor("#0b3a6e"))),
             Paragraph("Grid Controller of India Limited", st(12, textColor=colors.HexColor("#0b3a6e"))),
             Paragraph("(A Government of India Enterprise)", st(8, textColor=colors.grey)), Spacer(1, 8),
             Paragraph(title_hi, st(14)), Paragraph(title_en, st(13)),
             Paragraph(f"Ref: {ref} &nbsp;&nbsp; Date: {datetime.now():%d-%m-%Y}", st(9, textColor=colors.grey)), Spacer(1, 8)]
    if draft:
        story.append(Paragraph("DRAFT - NOT YET SIGNED / प्रारूप - हस्ताक्षरित नहीं", st(10, textColor=colors.red)))
    if body:
        story += [Paragraph(body, st(10)), Spacer(1, 6)]
    data = [[Paragraph(str(k), st(9)), Paragraph(str(v if v is not None else ""), st(9))] for k, v in fields]
    if data:
        t = Table(data, colWidths=[60 * mm, 110 * mm])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                               ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    story.append(Spacer(1, 18))
    if signer is not None:
        sig = getattr(signer, "signature_file_path", None)
        if sig and Path(sig).exists():
            story.append(Image(sig, width=40 * mm, height=15 * mm, kind="proportional"))
        story += [Paragraph(f"Digitally signed by {signer.full_name}", st(9)),
                  Paragraph(f"{signer_role} · DSC: {getattr(signer, 'dsc_serial', None) or 'image signature (POC)'}", st(8, textColor=colors.grey)),
                  Paragraph(f"Signed at {datetime.now():%d-%m-%Y %H:%M:%S}", st(8, textColor=colors.grey))]
    doc.build(story)
    pdf = buf.getvalue()
    return pdf


def fingerprint(pdf: bytes) -> str:
    return hashlib.sha256(pdf).hexdigest()
