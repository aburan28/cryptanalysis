"""Regenerate the gap-scan SVG figures and concise evidence PDF from JSON."""

import io
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.fonttype'] = 'none'
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak


ROOT = Path(__file__).resolve().parent


def tidy_svg(path):
    """Keep the generated SVG diff readable and free of trailing whitespace."""
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')


def figures(data):
    hits = data['ranked_hits'][:10][::-1]
    fig, ax = plt.subplots(figsize=(9.3, 5.0))
    fig.patch.set_facecolor('#f7f9fc')
    ax.set_facecolor('#f7f9fc')
    ys = list(range(len(hits)))
    bars = ax.barh(ys, [h['log2_prime_approx'] for h in hits],
                   color=['#087e8b' if h['m'] in (127, 131) else '#455f86' for h in hits])
    ax.set_yticks(ys, [f"m={h['m']}" for h in hits])
    ax.set_xlim(0, 70)
    ax.set_xlabel('log2 of prime conductor factor (degree, not work)')
    ax.set_title('Largest conductor factors in the bounded Koblitz scan', loc='left', pad=16)
    ax.grid(axis='x', alpha=0.25)
    ax.set_axisbelow(True)
    for bar, h in zip(bars, hits):
        ax.text(bar.get_width()+0.5, bar.get_y()+bar.get_height()/2,
                f"{h['log2_prime_approx']:.2f}", va='center', fontsize=8)
    ax.text(0, -0.16, '119 degrees checked, 46 factors >=20 bits; all factorizations complete',
            transform=ax.transAxes, fontsize=8, color='#334155')
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(ROOT/'conductor-gap-ranking.svg')
    tidy_svg(ROOT/'conductor-gap-ranking.svg')
    chart = io.BytesIO()
    fig.savefig(chart, format='png', dpi=180)
    chart.seek(0)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.3, 3.4))
    fig.patch.set_facecolor('#f7f9fc')
    ax.set(xlim=(0, 10), ylim=(0, 4))
    ax.axis('off')
    def box(x, y, title, subtitle, fill):
        ax.add_patch(FancyBboxPatch((x, y), 3.65, 1.02, boxstyle='round,pad=0.08',
                                    facecolor=fill, edgecolor='#334155', lw=1.2))
        ax.text(x+0.16, y+0.7, title, fontsize=11, weight='bold')
        ax.text(x+0.16, y+0.27, subtitle, fontsize=8.2)
    box(0.4, 2.24, 'm=127: order conductor 1', 'Known abstract source; no EC1 ID', '#d9eef0')
    box(5.95, 2.24, 'm=127: order conductor p', 'Possible stratum; no target curve', '#f7e8cf')
    box(0.4, 0.55, 'm=131: order conductor 1', 'EC1N131Ckb1h136f03e58c98', '#d9eef0')
    box(5.95, 0.55, 'm=131: order conductor p', 'Possible stratum; no target curve', '#f7e8cf')
    for y, label in [(2.75, 'p = 3293187233103900007'),
                     (1.06, 'p = 146505763881528721')]:
        ax.add_patch(FancyArrowPatch((4.17, y), (5.86, y), arrowstyle='-|>',
                                      mutation_scale=14, linestyle='--', color='#9b6525'))
        ax.text(5.0, y+0.20, label, ha='center', fontsize=7.4)
    ax.text(0.4, 3.64, 'Order strata and required prime degree; dashed arrows are unconstructed',
            fontsize=10, color='#334155')
    fig.tight_layout()
    fig.savefig(ROOT/'conductor-gap-orders.svg')
    tidy_svg(ROOT/'conductor-gap-orders.svg')
    diagram = io.BytesIO()
    fig.savefig(diagram, format='png', dpi=180)
    diagram.seek(0)
    plt.close(fig)
    return chart, diagram


def build(data, chart, diagram):
    fonts = Path('/usr/share/fonts/truetype/dejavu')
    regular = fonts/'DejaVuSans.ttf'
    if regular.exists():
        pdfmetrics.registerFont(TTFont('DejaVu', str(regular)))
        font = 'DejaVu'
    else:
        font = 'Helvetica'
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportTitle', parent=styles['Title'], fontName=font,
                              fontSize=17, leading=23, textColor=colors.HexColor('#17324d')))
    styles.add(ParagraphStyle(name='ReportBody', parent=styles['BodyText'], fontName=font,
                              fontSize=9, leading=14, spaceAfter=7))
    styles.add(ParagraphStyle(name='ReportHeading', parent=styles['Heading2'], fontName=font,
                              fontSize=12, leading=17, spaceBefore=10))
    P = lambda s: Paragraph(s, styles['ReportBody'])
    path = ROOT/'conductor-gap-scan-20261007.pdf'
    story = [Paragraph('Conductor gaps in a Koblitz curve family', styles['ReportTitle']),
             P('Research record | 2026-10-06 Pacific time | exact arithmetic, bounded scan'),
             P('Question: Find known-source ordinary curve families whose Frobenius order permits '
               'a large prime conductor transition. Scan E_m: y² + xy = x³ + 1 over F_(2^m), '
               '13 ≤ m ≤ 131. The source End order is maximal of discriminant -7.'),
             Paragraph('Observed results', styles['ReportHeading']),
             P('119/119 degree rows have complete conductor factorizations verified by '
               'recomposition and deterministic prime checks below 2^64. '
               '46 factor hits have bit length at least 20. Top hits:'),
            ]
    table = [['m', 'largest prime p in f_pi', 'log2(p)', 'h(O_p) / h(O_K)']]
    for hit in data['ranked_hits'][:5]:
        table.append([str(hit['m']), hit['prime'], f"{hit['log2_prime_approx']:.3f}",
                      hit['class_number_ratio_to_maximal']])
    t = Table(table, colWidths=[32, 205, 68, 170], repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND', (0,0),(-1,0),colors.HexColor('#e4edf4')),
                           ('FONTNAME',(0,0),(-1,-1),font), ('FONTSIZE',(0,0),(-1,-1),7.5),
                           ('BOTTOMPADDING',(0,0),(-1,-1),7),
                           ('TOPPADDING',(0,0),(-1,-1),7),
                           ('LINEBELOW',(0,0),(-1,0),0.7,colors.HexColor('#708499'))]))
    story += [t, Spacer(1, 8),
              P('For m=127 the prime factor is 3293187233103900007 '
                '(about 2^61.514). This is an isogeny degree in the order graph, '
                'not a time bound. Its destination order has discriminant -7p² '
                'and class number p-1; no destination curve or map was constructed.'),
              Image(chart, width=510, height=274), PageBreak(),
              Paragraph('What the gap identifies', styles['ReportTitle']),
              P('The source tau satisfies tau²+tau+2=0 over F_2. The corresponding '
                'discriminant -7 is fundamental. For tau^m=a_m+b_m tau, the exact '
                'identity t_m²-4·2^m=-7b_m² gives f_pi=|b_m|. '
                'A prime p dividing f_pi yields the candidate order Z+p O_K; '
                'h(O_p)/h(O_K)=p-(-7/p).'),
              Image(diagram, width=510, height=187),
              Paragraph('Evidence boundaries', styles['ReportHeading']),
              P('The m=131 source has exact ID EC1N131Ckb1h136f03e58c98. '
                'Other source rows in this scan specify the abstract curve model '
                'but no particular field representation or EC1 ID. Destination '
                'strata are arithmetic possibilities. Curve models, maps, subgroup '
                'preservation, relation cost, and DLP advantage remain unknown.'),
              P('Scope of completion: all degrees 13..131 in this family were checked. '
                'The scan does not survey all elliptic curves or certify that a '
                'specific destination across the largest factor has an advantage. '
                'The m=19 conductor-457 descendants and m=131 degree-263 '
                'descendants are existing constructed controls.'),
              Paragraph('Source links', styles['ReportHeading']),
              P('<link href="https://arxiv.org/abs/1208.5370">Sutherland, Isogeny volcanoes</link> '
                '(ordinary levels and orders). '
                '<link href="https://github.com/aburan28/cryptanalysis/blob/claude/cryptanalysis-repo-setup-p59kek/experiments/ic-candidate-catalog/curves.yaml">'
                'Exact m=131 curve registry</link>. '
                '<link href="https://github.com/aburan28/cryptanalysis/tree/claude/cryptanalysis-repo-setup-p59kek/experiments/ecc2k130-isogeny-class">'
                'Prior m=131 evidence</link>. Source script and every raw row accompany this PDF.'),
             ]
    SimpleDocTemplate(str(path), pagesize=(595.28,841.89), leftMargin=42,
                      rightMargin=42, topMargin=35, bottomMargin=37).build(story)


if __name__ == '__main__':
    data = json.loads((ROOT/'conductor-gap-scan-20261007.json').read_text())
    build(data, *figures(data))
