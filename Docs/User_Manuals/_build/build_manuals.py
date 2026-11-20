"""Builds the OMS user-manual PDFs from manual_content.py and the captured screenshots.

Usage:  python build_manuals.py <screenshots_dir> <output_dir>
"""
import io
import os
import sys
from datetime import date

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image as RLImage, KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

sys.path.insert(0, os.path.dirname(__file__))
from manual_content import DEMO_USERS, MANUALS  # noqa: E402

SHOTS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

FONT_DIR = 'C:/Windows/Fonts'
try:
    pdfmetrics.registerFont(TTFont('UI', f'{FONT_DIR}/segoeui.ttf'))
    pdfmetrics.registerFont(TTFont('UI-B', f'{FONT_DIR}/segoeuib.ttf'))
    pdfmetrics.registerFont(TTFont('UI-I', f'{FONT_DIR}/segoeuii.ttf'))
    pdfmetrics.registerFont(TTFont('UI-SB', f'{FONT_DIR}/seguisb.ttf') if os.path.exists(f'{FONT_DIR}/seguisb.ttf') else TTFont('UI-SB', f'{FONT_DIR}/segoeuib.ttf'))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily('UI', normal='UI', bold='UI-B', italic='UI-I', boldItalic='UI-B')
    F, FB = 'UI', 'UI-B'
except Exception:  # fall back to built-in fonts
    F, FB = 'Helvetica', 'Helvetica-Bold'

NAVY = colors.HexColor('#0b1f3a')
NAVY2 = colors.HexColor('#12305a')
SAFFRON = colors.HexColor('#f08c1a')
INK = colors.HexColor('#1e293b')
MUTED = colors.HexColor('#64748b')
LINE = colors.HexColor('#e2e8f0')
TINT = colors.HexColor('#f1f5f9')
NOTE_BG = colors.HexColor('#fff7ed')

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN
TODAY = date.today().strftime('%d %B %Y')
VERSION = '1.0'

st = {
    'body': ParagraphStyle('body', fontName=F, fontSize=9.6, leading=14, textColor=INK, spaceAfter=5),
    'h1': ParagraphStyle('h1', fontName=FB, fontSize=19, leading=24, textColor=NAVY, spaceAfter=4),
    'h2': ParagraphStyle('h2', fontName=FB, fontSize=12.5, leading=17, textColor=NAVY, spaceBefore=10, spaceAfter=4),
    'chapno': ParagraphStyle('chapno', fontName=FB, fontSize=9, leading=12, textColor=SAFFRON),
    'caption': ParagraphStyle('caption', fontName=F, fontSize=8, leading=10, textColor=MUTED, spaceBefore=3, spaceAfter=8),
    'menu': ParagraphStyle('menu', fontName=FB, fontSize=8.6, leading=11, textColor=colors.white),
    'url': ParagraphStyle('url', fontName=F, fontSize=8, leading=11, textColor=MUTED),
    'note': ParagraphStyle('note', fontName=F, fontSize=9, leading=13, textColor=INK),
    'li': ParagraphStyle('li', fontName=F, fontSize=9.6, leading=14, textColor=INK, leftIndent=14, bulletIndent=2, spaceAfter=2.5),
    'step': ParagraphStyle('step', fontName=F, fontSize=9.6, leading=14, textColor=INK, leftIndent=18, bulletIndent=0, spaceAfter=3),
    'toc1': ParagraphStyle('toc1', fontName=FB, fontSize=10.5, leading=17, textColor=NAVY, leftIndent=0),
    'toc2': ParagraphStyle('toc2', fontName=F, fontSize=9.2, leading=13.5, textColor=INK, leftIndent=16),
    'cell': ParagraphStyle('cell', fontName=F, fontSize=8.6, leading=11.5, textColor=INK),
    'cellb': ParagraphStyle('cellb', fontName=FB, fontSize=8.6, leading=11.5, textColor=colors.white),
}

_img_cache = {}


def shot_image(name, width=CONTENT_W * 0.74):
    path = os.path.join(SHOTS, name + '.png')
    if not os.path.exists(path):
        return None
    if name not in _img_cache:
        im = Image.open(path).convert('RGB')
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=82, optimize=True)
        _img_cache[name] = (buf.getvalue(), im.size)
    data, (w, h) = _img_cache[name]
    img = RLImage(io.BytesIO(data), width=width, height=width * h / w)
    framed = Table([[img]], colWidths=[width + 2], hAlign='CENTER')
    framed.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, LINE), ('LEFTPADDING', (0, 0), (-1, -1), 1),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 1), ('TOPPADDING', (0, 0), (-1, -1), 1),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
    return framed


def menu_chip(menu, url=None):
    cells = [[Paragraph('MENU', ParagraphStyle('k', fontName=FB, fontSize=7, textColor=SAFFRON)), Paragraph(menu, st['menu'])]]
    t = Table(cells, colWidths=[13 * mm, None], hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), NAVY2), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                           ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                           ('ROUNDEDCORNERS', [4, 4, 4, 4])]))
    out = [t]
    if url and url.startswith('/'):
        out.append(Paragraph(f'Page address: http://&lt;oms-server&gt;{url.replace("&", "&amp;")}', st['url']))
    return out


def note_box(text):
    t = Table([[Paragraph('<b>Note</b>&nbsp;&nbsp;' + text, st['note'])]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), NOTE_BG), ('LINEBEFORE', (0, 0), (0, -1), 2.5, SAFFRON),
                           ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
                           ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    return t


class ManualDoc(BaseDocTemplate):
    def __init__(self, path, manual, **kw):
        super().__init__(path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=22 * mm, bottomMargin=18 * mm,
                         title=f'Grid-India OMS User Manual - {manual["title"]}', author='Grid-India OMS project team',
                         subject='User manual', **kw)
        self.manual = manual
        frame = Frame(MARGIN, 18 * mm, CONTENT_W, PAGE_H - 40 * mm, id='f', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate('cover', frames=[frame], onPage=self.cover),
                               PageTemplate('body', frames=[frame], onPage=self.chrome)])

    def cover(self, c, doc):
        m = self.manual
        c.saveState()
        c.setFillColor(NAVY)
        c.rect(0, PAGE_H * 0.42, PAGE_W, PAGE_H * 0.58, fill=1, stroke=0)
        c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.06))
        for i in range(0, int(PAGE_W), 18):
            c.line(i, PAGE_H * 0.42, i, PAGE_H)
        for j in range(int(PAGE_H * 0.42), int(PAGE_H), 18):
            c.line(0, j, PAGE_W, j)
        # logo
        c.setFillColor(SAFFRON)
        c.roundRect(MARGIN, PAGE_H - 40 * mm, 13 * mm, 13 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        p = c.beginPath()
        x0, y0 = MARGIN, PAGE_H - 40 * mm
        for (dx, dy) in [(7.5, 11.5), (3.8, 5.8), (6.4, 5.8), (5.2, 1.5), (9.3, 7.5), (6.6, 7.5)]:
            (p.moveTo if dx == 7.5 and dy == 11.5 else p.lineTo)(x0 + dx * mm, y0 + dy * mm)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.setFont(FB, 13)
        c.drawString(MARGIN + 17 * mm, PAGE_H - 32 * mm, 'Grid-India OMS')
        c.setFont(F, 8.5)
        c.setFillColor(colors.HexColor('#9fb3cf'))
        c.drawString(MARGIN + 17 * mm, PAGE_H - 37 * mm, 'OPERATIONS MANAGEMENT SYSTEM')
        # title block
        c.setFillColor(SAFFRON)
        c.setFont(FB, 10)
        c.drawString(MARGIN, PAGE_H * 0.62 + 34 * mm, f'USER MANUAL {MANUALS.index(m) + 1:02d}')
        c.setFillColor(colors.white)
        c.setFont(FB, 30)
        y = PAGE_H * 0.62 + 20 * mm
        words, line, lines = m['title'].split(), '', []
        for w in words:
            if c.stringWidth((line + ' ' + w).strip(), FB, 30) > CONTENT_W:
                lines.append(line); line = w
            else:
                line = (line + ' ' + w).strip()
        lines.append(line)
        for ln in lines:
            c.drawString(MARGIN, y, ln); y -= 12 * mm
        c.setFont(F, 11)
        c.setFillColor(colors.HexColor('#c9d6e8'))
        c.drawString(MARGIN, y - 2 * mm, 'Pan-Grid-India Operations Management System')
        c.setFillColor(SAFFRON)
        c.rect(MARGIN, PAGE_H * 0.42 + 14 * mm, 30 * mm, 1.2 * mm, fill=1, stroke=0)
        # details
        c.setFillColor(INK)
        rows = [('Intended for', m['audience']), ('Organisation', 'Grid Controller of India Ltd (Grid-India)'),
                ('Reference', 'GeM bid GEM/2026/B/8083674, proof of concept'), ('Version', f'{VERSION}, {TODAY}')]
        y = PAGE_H * 0.42 - 20 * mm
        for k, v in rows:
            c.setFont(FB, 9); c.setFillColor(MUTED); c.drawString(MARGIN, y, k.upper())
            c.setFont(F, 11); c.setFillColor(INK); c.drawString(MARGIN + 38 * mm, y, v)
            y -= 10 * mm
        c.setFont(F, 8)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, 16 * mm, 'Screenshots are from the OMS proof of concept with demo data. Names and figures are examples.')
        c.restoreState()

    def chrome(self, c, doc):
        c.saveState()
        c.setFillColor(NAVY)
        c.rect(0, PAGE_H - 12 * mm, PAGE_W, 12 * mm, fill=1, stroke=0)
        c.setFillColor(SAFFRON)
        c.rect(0, PAGE_H - 12.8 * mm, PAGE_W, 0.8 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(FB, 8.5)
        c.drawString(MARGIN, PAGE_H - 7.6 * mm, 'Grid-India OMS')
        c.setFont(F, 8.5)
        c.setFillColor(colors.HexColor('#c9d6e8'))
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 7.6 * mm, f'User Manual {MANUALS.index(self.manual) + 1:02d}  \u00b7  {self.manual["title"]}')
        c.setStrokeColor(LINE)
        c.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        c.setFont(F, 7.5)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, 8 * mm, f'Grid Controller of India Ltd  \u00b7  Version {VERSION}, {TODAY}')
        c.drawRightString(PAGE_W - MARGIN, 8 * mm, f'Page {doc.page}')
        c.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and getattr(f, '_toc', None):
            lvl, text, key = f._toc
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=lvl, closed=lvl > 0)
            self.notify('TOCEntry', (lvl, text, self.page, key))


def heading(text, style, level, key):
    p = Paragraph(text, style)
    p._toc = (level, text.replace('&amp;', '&'), key)
    return p


def build(manual):
    story = [NextPageTemplate('body'), PageBreak()]
    story.append(Paragraph('Contents', st['h1']))
    story.append(Spacer(1, 4 * mm))
    toc = TableOfContents()
    toc.levelStyles = [st['toc1'], st['toc2']]
    toc.dotsMinLevel = 0
    story += [toc, PageBreak()]

    for ci, ch in enumerate(manual['chapters'], 1):
        if ci > 1:
            story.append(PageBreak())
        story.append(Paragraph(f'CHAPTER {ci}', st['chapno']))
        story.append(heading(ch['title'].replace('&', '&amp;'), st['h1'], 0, f'c{ci}'))
        story.append(Table([['']], colWidths=[CONTENT_W], rowHeights=[1.2],
                           style=[('LINEABOVE', (0, 0), (-1, -1), 1.2, SAFFRON)]))
        story.append(Spacer(1, 2 * mm))
        for si, sec in enumerate(ch['sections'], 1):
            head = [heading(f'{ci}.{si}&nbsp;&nbsp;{sec["title"].replace("&", "&amp;")}', st['h2'], 1, f'c{ci}s{si}')]
            if sec.get('menu'):
                head += menu_chip(sec['menu'].replace('&', '&amp;'), sec.get('url'))
                head.append(Spacer(1, 2.5 * mm))
            block = []
            for t in sec.get('text', []):
                block.append(Paragraph(t, st['body']))
            for b in sec.get('bullets', []):
                block.append(Paragraph(b, st['li'], bulletText='\u2022'))
            if sec.get('steps'):
                if sec.get('bullets'):
                    block.append(Spacer(1, 3))
                for n, s in enumerate(sec['steps'], 1):
                    block.append(Paragraph(s, st['step'], bulletText=f'{n}.'))
                block.append(Spacer(1, 2))
            if sec.get('note'):
                block += [Spacer(1, 3), note_box(sec['note']), Spacer(1, 3)]
            section = head + block
            if sec.get('shot'):
                name, cap = sec['shot']
                img = shot_image(name)
                if img is not None:
                    section += [Spacer(1, 2 * mm), img, Paragraph(f'Figure {ci}.{si}: {cap}', ParagraphStyle('capc', parent=st['caption'], alignment=1))]
                else:
                    print('  missing screenshot', name)
            story.append(KeepTogether(section))
            story.append(Spacer(1, 3 * mm))

    if manual.get('appendix'):
        story.append(PageBreak())
        story.append(Paragraph('APPENDIX', st['chapno']))
        story.append(heading('Demo accounts (proof of concept)', st['h1'], 0, 'appx'))
        story.append(Paragraph('All demo users have the password <b>Grid@2026</b>. The OTP is displayed on screen in the demo system. '
                               'In production each user receives individual credentials and the OTP by SMS / e-mail.', st['body']))
        rows = [[Paragraph(h, st['cellb']) for h in ('Username', 'Login type', 'Role / access')]]
        rows += [[Paragraph(f'<b>{u}</b>', st['cell']), Paragraph(t, st['cell']), Paragraph(r, st['cell'])] for u, t, r in DEMO_USERS]
        tbl = Table(rows, colWidths=[40 * mm, 26 * mm, CONTENT_W - 66 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), NAVY), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, TINT]),
                                 ('GRID', (0, 0), (-1, -1), 0.4, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                 ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        story += [Spacer(1, 3 * mm), tbl]

    path = os.path.join(OUT, manual['file'])
    doc = ManualDoc(path, manual)
    doc.multiBuild(story)
    print(f'{manual["file"]}: {doc.page} pages, {os.path.getsize(path) / 1e6:.1f} MB')


for mnl in MANUALS:
    build(mnl)
