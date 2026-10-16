"""Render REPORT.md (headings, paragraphs, bullets, pipe tables, ![](images)) to REPORT.pdf with reportlab."""
import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, ListFlowable, ListItem, Preformatted
from PIL import Image as PILImage

HERE = Path(__file__).resolve().parent
# Unicode TrueType fonts (ℓ, ψ, τ, sub/superscripts): matplotlib's bundled DejaVu, a dependency already
import matplotlib
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
_TTF = Path(matplotlib.__file__).parent / 'mpl-data' / 'fonts' / 'ttf'
for name, fn in (('DV', 'DejaVuSans.ttf'), ('DVB', 'DejaVuSans-Bold.ttf'), ('DVM', 'DejaVuSansMono.ttf')):
    pdfmetrics.registerFont(TTFont(name, str(_TTF / fn)))
addMapping('DV', 0, 0, 'DV'); addMapping('DV', 1, 0, 'DVB'); addMapping('DV', 0, 1, 'DV'); addMapping('DV', 1, 1, 'DVB')
ss = getSampleStyleSheet()
for _st in ss.byName.values():
    _st.fontName = 'DVB' if 'Bold' in getattr(_st, 'fontName', '') or _st.name.startswith(('Heading', 'Title')) else 'DV'
body = ParagraphStyle('b', parent=ss['BodyText'], fontSize=9.2, leading=12.2)
cell = ParagraphStyle('c', parent=body, fontSize=7.6, leading=9.4)
H = {1: ss['Title'], 2: ParagraphStyle('h2', parent=ss['Heading2'], fontSize=12.5), 3: ss['Heading3']}


def inline(t):
    t = t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'`([^`]+)`', r'<font face="DVM">\1</font>', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<u>\1</u> (\2)', t)
    return t


def build(md=HERE / 'REPORT.md', pdf=HERE / 'REPORT.pdf'):
    lines = md.read_text().splitlines(); out = []; i = 0
    while i < len(lines):
        l = lines[i]
        if not l.strip(): i += 1; continue
        if l.startswith('```'):
            j = i + 1; code = []
            while j < len(lines) and not lines[j].startswith('```'): code.append(lines[j]); j += 1
            out += [Preformatted('\n'.join(code), ParagraphStyle('pre', fontName='DVM', fontSize=7.5, leading=9)), Spacer(1, 6)]
            i = j + 1; continue
        m = re.match(r'(#+) (.*)', l)
        if m: out.append(Paragraph(inline(m.group(2)), H[min(len(m.group(1)), 3)])); i += 1; continue
        m = re.match(r'!\[[^\]]*\]\(([^)]+)\)', l)
        if m:
            p = (HERE / m.group(1)).resolve(); w, h = PILImage.open(p).size; W = 6.9 * inch
            out += [Image(str(p), W, W * h / w), Spacer(1, 6)]; i += 1; continue
        if l.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                if not re.match(r'\|\s*:?-', lines[i]):
                    rows.append([Paragraph(inline(c.strip()), cell) for c in lines[i].strip('|').split('|')])
                i += 1
            t = Table(rows, repeatRows=1)
            t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), .3, colors.grey), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f7')),
                                   ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            out += [t, Spacer(1, 8)]; continue
        if re.match(r'\s*[-*] ', l):
            items = []
            while i < len(lines) and re.match(r'\s*[-*] ', lines[i]):
                txt = re.sub(r'^\s*[-*] ', '', lines[i]); i += 1
                while i < len(lines) and lines[i].startswith('  ') and not re.match(r'\s*[-*] ', lines[i]):
                    txt += ' ' + lines[i].strip(); i += 1
                items.append(ListItem(Paragraph(inline(txt), body), leftIndent=12))
            out += [ListFlowable(items, bulletType='bullet', leftIndent=12), Spacer(1, 4)]; continue
        para = [l]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'(#|\||!\[|\s*[-*] )', lines[i]):
            para.append(lines[i]); i += 1
        out += [Paragraph(inline(' '.join(para)), body), Spacer(1, 4)]
    SimpleDocTemplate(str(pdf), pagesize=letter, leftMargin=.75 * inch, rightMargin=.75 * inch,
                      topMargin=.7 * inch, bottomMargin=.7 * inch, title='volcano-m83 twist yield census').build(out)


if __name__ == '__main__':
    build()
