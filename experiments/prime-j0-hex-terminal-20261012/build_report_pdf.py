#!/usr/bin/env python3
"""Build the visual report PDF from frozen scalar-format receipts and figures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "REPORT-2026-10-12.pdf"


def picture(name: str, width: float) -> Image:
    path = HERE / "figures" / name
    with PILImage.open(path) as source:
        w, h = source.size
    return Image(str(path), width=width, height=width * h / w)


def build(output: Path) -> None:
    census = json.loads((HERE / "search.json").read_text())
    mac = json.loads((HERE / "storage-macos.json").read_text())
    linux = json.loads((HERE / "storage-linux.json").read_text())
    replay = json.loads((HERE / "replay.json").read_text())
    assert census["table_point_entries"] == 174_883
    assert mac["runs"]["candidate"]["retained_bytes_exact_accounting"] == 11_505_936
    assert linux["runs"]["candidate"]["retained_bytes_exact_accounting"] == 11_505_936
    assert len(replay["panels"]) == 4

    page_w, _ = landscape(A4)
    doc = SimpleDocTemplate(
        str(output), pagesize=landscape(A4),
        leftMargin=37, rightMargin=37, topMargin=38, bottomMargin=37,
        title="Voronoi-clipped fixed-base scalar table",
        author="cryptanalysis scalar-format experiment",
    )
    usable = page_w - doc.leftMargin - doc.rightMargin
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCustom", parent=styles["Title"],
                              fontName="Helvetica-Bold", fontSize=22, leading=25,
                              textColor=colors.HexColor("#173451"), spaceAfter=11))
    styles.add(ParagraphStyle(name="LeadCustom", parent=styles["BodyText"],
                              fontSize=11.1, leading=15, spaceAfter=10))
    styles.add(ParagraphStyle(name="BodyCustom", parent=styles["BodyText"],
                              fontSize=9.6, leading=13.1, spaceAfter=7))
    styles.add(ParagraphStyle(name="SmallCustom", parent=styles["BodyText"],
                              fontSize=8.4, leading=11.2, spaceAfter=6))
    styles.add(ParagraphStyle(name="SectionCustom", parent=styles["Heading2"],
                              fontSize=12.2, leading=15, textColor=colors.HexColor("#14544f"),
                              spaceBefore=9, spaceAfter=6))
    styles.add(ParagraphStyle(name="CaptionCustom", parent=styles["BodyText"],
                              fontSize=8.4, leading=10.6, alignment=TA_CENTER,
                              textColor=colors.HexColor("#475569"), spaceAfter=6))
    p = lambda content, style="BodyCustom": Paragraph(content, styles[style])
    story = []

    story.append(p("Voronoi-clipped fixed-base scalar table", "TitleCustom"))
    story.append(p(
        "<b>Contribution.</b> An opt-in secp256k1 radix-256 evaluator intersects the "
        "terminal norm disk with three Eisenstein Voronoi support strips. Its terminal "
        "table has <b>11,023</b> unit-orbit entries versus <b>13,314</b> for the direct "
        "disk; the complete table has <b>174,883</b> stored point entries, saving "
        "<b>2,291 entries / 146,624 point-payload bytes</b>. The native audit records "
        "<b>11,505,936 retained bytes</b>.", "LeadCustom"))
    story.append(p(
        "<b>Instance.</b> secp256k1 over Fp, y^2=x^3+7, standard prime-order generator "
        "G. The exact p, subgroup order r, G, lattice basis U,V, and scalar fixtures are "
        "in REPORT-2026-10-12.md, search.json, and holdout.json. The domain is reduced "
        "public scalars 0 &lt;= k &lt; r. Up to sixteen point selections are used."))
    story.append(picture("pipeline.png", usable))
    story.append(p(
        "Figure 1. The exact terminal certificate combines 3N(t) &lt;= 66,051 with "
        "three support strips. The editable source is figures/make_figures.py; "
        "figures/sources.json binds the source receipts.", "CaptionCustom"))
    story.append(p(
        "<b>Method.</b> W=U-2V and W,V,W+V each have norm r. The four-corner minimum "
        "obeys the Voronoi inequalities; Cauchy bounds each ordinary radix-256 digit. "
        "Fifteen-step reconstruction bounds the terminal in all three strip directions. "
        "The Lean proof map and exact hypotheses are in PROOF.md."))
    story.append(PageBreak())

    story.append(p("Exact census and native evidence", "TitleCustom"))
    rows = [
        ["Quantity", "Direct disk", "Voronoi clipped", "Evidence"],
        ["Terminal orbit entries", "13,314", "11,023", "search.json; search.py"],
        ["Total point entries", "177,174", "174,883", "search.json; native audit"],
        ["Retained table bytes", "11,652,560", "11,505,936", "prior replay; storage-macos.json"],
        ["Independent point cases", "-", "2,048 / 2,048", "replay.json; macOS + Linux VM"],
    ]
    table = Table(rows, colWidths=[usable*.24, usable*.17, usable*.20, usable*.39],
                  repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173451")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#eef4f8")]),
        ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#cad6df")),
    ]))
    story.extend([table, Spacer(1, 7), picture("storage.png", usable*.83)])
    story.append(p(
        "Figure 2. Exact point counts and retained table accounting from one build per "
        "format. Sampling uncertainty does not apply to these integer counts. "
        "Native process RSS and placement are separate manifest fields.", "CaptionCustom"))
    story.append(PageBreak())

    story.append(p("Proof status, execution boundary, and sources", "TitleCustom"))
    story.append(p("Checked proof and open bridge", "SectionCustom"))
    story.append(p(
        "Lean 4.34.1 checks the lattice-neighbor norms, exact four-corner score identity, "
        "minimum-corner Voronoi strips, a reciprocal/product two-unit coordinate "
        "enclosure, fraction-score intervals and a composed theorem taking a "
        "strict classifier winner into all six Voronoi strips and actual "
        "lattice-neighbor inequalities. Exact floor quotients and all four "
        "corner offsets satisfy the checked scaled-coordinate identity; "
        "Euclidean remainders establish normalized cell bounds. "
        "Lean also checks Cauchy digit support, fifteen-step reconstruction, "
        "and conditional terminal inclusion. lean-build.txt retains the build and "
        "axiom audit output. Lean checks both native reciprocal constants against "
        "the floor inequalities and the reduced-scalar range; check.py matches all "
        "fourteen words to the Rust source. Lean also checks exact-product "
        "extraction, bounded carry propagation, and an indexed outer pass "
        "over the native offset and reciprocal-sized array slice. Four such "
        "passes have zero final carry and compute the exact scalar-times-"
        "reciprocal product under bounded-word inputs. The checked modeled "
        "loop includes all intermediate prefix-product equalities and the "
        "eleven-word capacity proof. Formal correspondence to the native "
        "Rust loop remains open. One checked theorem composes the four-pass "
        "product with its modeled high three words, word seven, and low seven "
        "words as the exact quotient, fractional word, and remainder; the "
        "native return-index correspondence remains "
        "open. The "
        "fallback remains to be composed with the four-corner theorem; the finite "
        "11,023-orbit census also lacks a Lean cardinality theorem. The exact exit "
        "criteria are in problems/prime-j0-hex-terminal-formal-coverage.md."))
    story.append(p("Native replay and placement", "SectionCustom"))
    story.append(p(
        "An exact-source wrapper compiled the native reciprocal word loop and "
        "matched all 5,197 deterministic cases against an independent Python "
        "integer product, including carry-heavy patterns and both production "
        "reciprocals. native-reciprocal-loop.json retains source, compiler, input, "
        "and output hashes. "
        "The source-frozen post-commit holdout has 512 distinct scalars disjoint from prior "
        "panels. Four 512-case panels match independently computed points on macOS ARM64; "
        "the same semantic receipt passed after offline Linux ARM64 Docker VM rebuild. "
        "storage-macos.json and storage-linux.json record CPU model/topology, cache exposure, "
        "affinity, cgroup limits, memory policy, co-runners, process RSS samples, and whether "
        "page placement was observable. The retained-byte value is internal exact table "
        "accounting, not resident memory."))
    story.append(p("Inconclusive measurements and next step", "SectionCustom"))
    story.append(p(
        "The available RunPod service is serial but its Docker/cgroup-v1 host has no isolated "
        "CPU partition or nohz_full set and currently has an active CryptoMiniSat job. "
        "The incidental audit wall and CPU times do not support an online speedup. "
        "The next proof step connects the exact 512-bit limb product to the checked "
        "two-unit interval theorem, then handles the fallback branch."))
    story.append(p("Canonical graphs and reproduction", "SectionCustom"))
    story.append(p(
        "Checked prime-j0-cost-aware-chain/orbit-graph-inputs.json, "
        "ec-arithmetic-optimizations/figures, and volcano-ic/figures. They encode graph, "
        "operation-layer, or isogeny facts unaffected by this scalar table. Rebuild "
        "with search.py --check, screen.py --check, check.py --check, and "
        "figures/make_figures.py. REPORT-2026-10-12.md links each exact receipt and source."))
    story.append(Spacer(1, 8))
    story.append(p(
        "Source files: search.json; screen.json; replay.json; storage-macos.json; "
        "storage-linux.json; VoronoiTerminal.lean; PROOF.md; figures/sources.json.",
        "SmallCustom"))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#ccd7e1"))
        canvas.line(37, 28, page_w-37, 28)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#526579"))
        canvas.drawString(37, 17, "Voronoi-clipped scalar table | 2026-10-12")
        canvas.drawRightString(page_w-37, 17, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
