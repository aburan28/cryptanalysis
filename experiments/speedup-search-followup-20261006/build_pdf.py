"""Build speedup_search_followup.pdf from README.md and the figures.

A small Markdown subset is rendered with reportlab: headings, paragraphs,
bullet lists, pipe tables, fenced code, inline `code`, **bold** and *italic*.
Figures are inserted after the section that cites them.
"""

from __future__ import annotations

import os
import re
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "README.md")
OUT = os.path.join(HERE, "speedup_search_followup.pdf")
FIG = os.path.join(HERE, "figures")

FONTDIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
for name, fn in [("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"), ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf"), ("DVM", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONTDIR, fn)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

INK, INK2, RULE, TINT = colors.HexColor("#0b0b0b"), colors.HexColor("#52514e"), colors.HexColor("#d9d8d2"), colors.HexColor("#f3f2ee")
body = ParagraphStyle("body", fontName="DV", fontSize=9, leading=12.6, textColor=INK, spaceAfter=5)
cell = ParagraphStyle("cell", parent=body, fontSize=7.4, leading=9.4, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="DV-B")
h1 = ParagraphStyle("h1", fontName="DV-B", fontSize=13, leading=16, spaceBefore=10, spaceAfter=6)
h2 = ParagraphStyle("h2", fontName="DV-B", fontSize=10.5, leading=13.5, spaceBefore=8, spaceAfter=4)
title = ParagraphStyle("title", fontName="DV-B", fontSize=18, leading=22, spaceAfter=8)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=3)
caption = ParagraphStyle("caption", parent=body, fontSize=8, leading=10.6, textColor=INK2, spaceBefore=2, spaceAfter=10)
code = ParagraphStyle("code", fontName="DVM", fontSize=7.6, leading=9.6, backColor=TINT, borderPadding=4, spaceAfter=8, leftIndent=4)

FIGURES_AFTER = {
    "## Question and scope": ("decision_map.png", 7.0, "Figure 1. The eight shipped items with their status and the shared claim boundary (source: figures/make_figures.py)."),
    "### 3. NFS density window": ("nfs_window.png", 6.2, "Figure 2. AVW exponent against sparse-block and exact-batch collectors as a function of theta; the window 0.437gamma < theta < 0.563gamma at gamma = 1/18 and the GNFS/SNFS inputs (source: nfs_density_window.py)."),
    "### 5. SSS five-fixture positive control": ("sss_benchmark.png", 6.2, "Figure 3. Per-fixture medians of three fresh-process runs for SSS, bundled pSIQS and SymPy SIQS; whiskers are min/max; log scale (source: figures/make_figures.py from results/sss/summary.json)."),
    "### 6. Joux advanced pinpointing": ("pinpointing_constants.png", 6.2, "Figure 4. L(1/3) constants: classical sieving, pinpointing relation collection and linear algebra against the factor-base exponent alpha; improvement range marked (source: pinpointing.py)."),
    "### 8. Two-product S4 evaluator": ("s4_bench.png", 6.6, "Figure 5. Wall time for 2^20 S4 = 0 tests per regime and evaluator over p = 2^61 - 1, medians of 7 rotated trials with the minimum as whisker; shared VM, exploratory (source: figures/make_figures.py from results/s4_bench.json)."),
}


def inline(md: str) -> str:
    """Markdown inline -> reportlab mini-HTML."""
    md = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f"{m.group(1)} (`{m.group(2)}`)" if not m.group(1).strip("`") == m.group(2) else f"`{m.group(2)}`", md)
    parts = re.split(r"(`[^`]*`)", md)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            out.append(f'<font face="DVM" size="7.6">{escape(part[1:-1])}</font>')
        else:
            t = escape(part)
            t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
            t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
            out.append(t)
    return "".join(out)


def table(rows: list[list[str]]):
    ncol = max(len(r) for r in rows)
    width = 7.0 * inch
    first = min(1.9 * inch, width / ncol * 1.3)
    rest = (width - first) / max(1, ncol - 1)
    widths = [first] + [rest] * (ncol - 1)
    data = [[Paragraph(inline(c), cellb if i == 0 else cell) for c in r + [""] * (ncol - len(r))] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK2), ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    for i in range(2, len(rows), 2):
        st.append(("BACKGROUND", (0, i), (-1, i), TINT))
    t.setStyle(TableStyle(st))
    return t


def figure(name: str, width_in: float, cap: str):
    path = os.path.join(FIG, name)
    iw, ih = ImageReader(path).getSize()
    w = width_in * inch
    return KeepTogether([Spacer(1, 4), Image(path, width=w, height=w * ih / iw), Paragraph(cap, caption)])


def render(md_lines: list[str]) -> list:
    flow = []
    para: list[str] = []
    tbl: list[list[str]] = []
    fence: list[str] | None = None
    pending_fig = None

    def flush_para():
        nonlocal para
        if para:
            flow.append(Paragraph(inline(" ".join(para)), body))
            para = []

    def flush_tbl():
        nonlocal tbl
        if tbl:
            flow.append(table(tbl))
            flow.append(Spacer(1, 6))
            tbl = []

    def flush_fig():
        nonlocal pending_fig
        if pending_fig:
            flow.append(figure(*pending_fig))
            pending_fig = None

    for raw in md_lines + [""]:
        line = raw.rstrip("\n")
        if fence is not None:
            if line.startswith("```"):
                flow.append(Preformatted("\n".join(fence), code))
                fence = None
            else:
                fence.append(line)
            continue
        if line.startswith("```"):
            flush_para(); flush_tbl()
            fence = []
            continue
        if line.startswith("|"):
            flush_para()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                continue
            tbl.append(cells)
            continue
        flush_tbl()
        if line.startswith("#"):
            flush_para(); flush_fig()
            level = len(line) - len(line.lstrip("#"))
            text = line[level:].strip()
            if level == 1:
                flow.append(Paragraph(inline(text), title))
            else:
                flow.append(Paragraph(inline(text), h1 if level == 2 else h2))
            key = f"{'#' * level} {text}"
            for k, v in FIGURES_AFTER.items():
                if key.startswith(k):
                    pending_fig = v
            continue
        if line.startswith("- "):
            flush_para()
            flow.append(Paragraph(inline(line[2:]), bullet, bulletText="•"))
            continue
        if line.startswith("  ") and flow and isinstance(flow[-1], Paragraph) and flow[-1].style is bullet:
            # continuation of a bullet
            prev = flow.pop()
            flow.append(Paragraph(prev.text + " " + inline(line.strip()), bullet, bulletText="•"))
            continue
        if not line.strip():
            flush_para()
            continue
        para.append(line.strip())
    flush_para(); flush_tbl(); flush_fig()
    return flow


def main() -> None:
    with open(SRC, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            title="Speedup-search follow-up: what ships from the AVW thin-product thread", author="cryptanalysis experiments")

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("DV", 7.5)
        canvas.setFillColor(INK2)
        canvas.drawString(0.75 * inch, 0.45 * inch, "experiments/speedup-search-followup-20261006 — 2026-10-06 — stage diagnostics, candidate_id null")
        canvas.drawRightString(letter[0] - 0.75 * inch, 0.45 * inch, f"page {d.page}")
        canvas.restoreState()

    doc.build(render(lines), onFirstPage=footer, onLaterPages=footer)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
