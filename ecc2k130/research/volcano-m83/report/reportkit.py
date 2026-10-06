"""Layout helpers for the m=83 volcano report (reportlab), after the ECC2K-130 builder."""
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, LongTable, PageTemplate, Paragraph, Table,
                                TableStyle)

NAVY = HexColor('#0B1F33')
NAVY2 = HexColor('#16324F')
TEAL = HexColor('#0F766E')
BLUE = HexColor('#2563EB')
ORANGE = HexColor('#D97706')
RED = HexColor('#B91C1C')
GREEN = HexColor('#047857')
SLATE = HexColor('#475569')
MUTED = HexColor('#64748B')
LIGHT = HexColor('#F1F5F9')
LIGHT_BLUE = HexColor('#EFF6FF')
LIGHT_TEAL = HexColor('#ECFDF5')
LIGHT_ORANGE = HexColor('#FFF7ED')
LIGHT_RED = HexColor('#FEF2F2')
INK = HexColor('#172033')
WHITE = colors.white

FONT_REG, FONT_BOLD, FONT_MONO = 'Helvetica', 'Helvetica-Bold', 'Courier'
for candidate, name in [(Path('/System/Library/Fonts/Supplemental/Arial.ttf'), 'ReportSans'),
                        (Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf'), 'ReportSansBold'),
                        (Path('/System/Library/Fonts/Supplemental/Courier New.ttf'), 'ReportMono')]:
    if candidate.exists():
        pdfmetrics.registerFont(TTFont(name, str(candidate)))
names = pdfmetrics.getRegisteredFontNames()
if 'ReportSans' in names:
    FONT_REG = 'ReportSans'
if 'ReportSansBold' in names:
    FONT_BOLD = 'ReportSansBold'
if 'ReportMono' in names:
    FONT_MONO = 'ReportMono'

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='ReportBody', parent=styles['BodyText'], fontName=FONT_REG, fontSize=9.4,
                          leading=12.6, textColor=INK, spaceAfter=6, splitLongWords=False))
styles.add(ParagraphStyle(name='ReportSmall', parent=styles['BodyText'], fontName=FONT_REG, fontSize=7.5,
                          leading=9.5, textColor=SLATE, spaceAfter=3))
styles.add(ParagraphStyle(name='ReportTiny', parent=styles['BodyText'], fontName=FONT_REG, fontSize=6.5,
                          leading=8.0, textColor=SLATE))
styles.add(ParagraphStyle(name='ReportH1', parent=styles['Heading1'], fontName=FONT_BOLD, fontSize=18,
                          leading=21, textColor=NAVY, spaceBefore=4, spaceAfter=9, keepWithNext=True))
styles.add(ParagraphStyle(name='ReportH2', parent=styles['Heading2'], fontName=FONT_BOLD, fontSize=13,
                          leading=16, textColor=TEAL, spaceBefore=9, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name='ReportH3', parent=styles['Heading3'], fontName=FONT_BOLD, fontSize=10.5,
                          leading=13, textColor=NAVY2, spaceBefore=7, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name='ReportCaption', parent=styles['BodyText'], fontName=FONT_REG, fontSize=7.2,
                          leading=9.1, textColor=MUTED, alignment=TA_LEFT, spaceBefore=3, spaceAfter=8))
styles.add(ParagraphStyle(name='ReportCode', parent=styles['Code'], fontName=FONT_MONO, fontSize=7.7,
                          leading=10.2, textColor=NAVY2, backColor=LIGHT, borderPadding=6, leftIndent=6,
                          rightIndent=6, spaceBefore=4, spaceAfter=7))
styles.add(ParagraphStyle(name='CoverTitle', fontName=FONT_BOLD, fontSize=27, leading=31, textColor=WHITE,
                          alignment=TA_LEFT, spaceAfter=12))
styles.add(ParagraphStyle(name='CoverSubtitle', fontName=FONT_REG, fontSize=13.5, leading=18,
                          textColor=HexColor('#D9EAF7'), alignment=TA_LEFT, spaceAfter=10))
styles.add(ParagraphStyle(name='CoverMeta', fontName=FONT_REG, fontSize=8.5, leading=11,
                          textColor=HexColor('#C7D7E6'), alignment=TA_LEFT))
styles.add(ParagraphStyle(name='TOCHeading', fontName=FONT_BOLD, fontSize=18, leading=21, textColor=NAVY,
                          spaceAfter=12))
styles.add(ParagraphStyle(name='BulletText', parent=styles['ReportBody'], leftIndent=14, firstLineIndent=-7,
                          bulletIndent=3, spaceAfter=3))


def P(text, style='ReportBody'):
    return Paragraph(text, styles[style])


def H1(text):
    return Paragraph(text, styles['ReportH1'])


def H2(text):
    return Paragraph(text, styles['ReportH2'])


def H3(text):
    return Paragraph(text, styles['ReportH3'])


def bullet(text):
    return Paragraph('- ' + text, styles['BulletText'])


def code(text):
    return Paragraph(text.replace('\n', '<br/>'), styles['ReportCode'])


def mono(text):
    return "<font name='%s'>%s</font>" % (FONT_MONO, text)


def cell(value, style='ReportSmall', bold=False):
    if isinstance(value, Paragraph):
        return value
    text = str(value)
    if bold:
        text = '<b>%s</b>' % text
    return P(text, style)


def make_table(data, widths=None, header=True, tiny=False):
    style_name = 'ReportTiny' if tiny else 'ReportSmall'
    wrapped = []
    for r, row in enumerate(data):
        if header and r == 0:
            wrapped.append([P("<font color='white'><b>%s</b></font>" % v, style_name) for v in row])
        else:
            wrapped.append([cell(v, style_name) for v in row])
    tbl = LongTable(wrapped, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT', splitByRow=1)
    cmds = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4), ('TOPPADDING', (0, 0), (-1, -1), 3.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5), ('GRID', (0, 0), (-1, -1), 0.35, HexColor('#CBD5E1'))]
    if header:
        cmds.append(('BACKGROUND', (0, 0), (-1, 0), NAVY2))
        for r in range(1, len(data)):
            if r % 2 == 0:
                cmds.append(('BACKGROUND', (0, r), (-1, r), HexColor('#F8FAFC')))
    tbl.setStyle(TableStyle(cmds))
    return tbl


def callout(title, body, color=TEAL, background=LIGHT_TEAL):
    content = [P("<font color='%s'><b>%s</b></font>" % (color.hexval(), title), 'ReportH3'), P(body)]
    tbl = Table([[content]], colWidths=[7.0 * inch], hAlign='LEFT')
    tbl.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), background), ('BOX', (0, 0), (-1, -1), 0.8, color),
                             ('LINEBEFORE', (0, 0), (0, -1), 5, color), ('LEFTPADDING', (0, 0), (-1, -1), 10),
                             ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 7),
                             ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    return tbl


def figure(path, caption, max_width=7.0 * inch, max_height=6.1 * inch):
    with PILImage.open(path) as img:
        w, h = img.size
    scale = min(max_width / w, max_height / h)
    return [Image(str(path), width=w * scale, height=h * scale, hAlign='CENTER'), P(caption, 'ReportCaption')]


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename, running_title, running_right, footer):
        super().__init__(filename, pagesize=letter, rightMargin=0.55 * inch, leftMargin=0.55 * inch,
                         topMargin=0.62 * inch, bottomMargin=0.55 * inch, title=running_title,
                         author='Defensive cryptographic research')
        self.running_title, self.running_right, self.footer = running_title, running_right, footer
        cover = Frame(0.65 * inch, 0.55 * inch, 7.2 * inch, 9.9 * inch, leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0, id='cover')
        content = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, leftPadding=0,
                        rightPadding=0, topPadding=0, bottomPadding=0, id='content')
        self.addPageTemplates([PageTemplate(id='cover', frames=[cover], onPage=self.cover_page),
                               PageTemplate(id='content', frames=[content], onPage=self.content_page)])

    def cover_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, letter[0], letter[1], stroke=0, fill=1)
        canvas.setFillColor(TEAL)
        canvas.rect(0, letter[1] - 0.18 * inch, letter[0], 0.18 * inch, stroke=0, fill=1)
        canvas.setFillColor(BLUE)
        canvas.rect(0, 0, letter[0], 0.12 * inch, stroke=0, fill=1)
        canvas.restoreState()

    def content_page(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(HexColor('#CBD5E1'))
        canvas.setLineWidth(0.5)
        canvas.line(self.leftMargin, letter[1] - 0.40 * inch, letter[0] - self.rightMargin, letter[1] - 0.40 * inch)
        canvas.setFont(FONT_BOLD, 7.3)
        canvas.setFillColor(NAVY2)
        canvas.drawString(self.leftMargin, letter[1] - 0.30 * inch, self.running_title)
        canvas.setFont(FONT_REG, 7.0)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(letter[0] - self.rightMargin, letter[1] - 0.30 * inch, self.running_right)
        canvas.line(self.leftMargin, 0.38 * inch, letter[0] - self.rightMargin, 0.38 * inch)
        canvas.setFont(FONT_REG, 7.2)
        canvas.drawString(self.leftMargin, 0.24 * inch, self.footer)
        canvas.drawRightString(letter[0] - self.rightMargin, 0.24 * inch, 'Page %d' % doc.page)
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ('ReportH1', 'ReportH2'):
            level = 0 if flowable.style.name == 'ReportH1' else 1
            text = flowable.getPlainText()
            key = 'h%d-%s' % (level, self.seq.nextf('heading'))
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=False)
            self.notify('TOCEntry', (level, text, self.page, key))
