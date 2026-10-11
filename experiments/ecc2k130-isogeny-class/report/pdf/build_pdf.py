"""Build ecc2k130_isogeny_class_hardness.pdf from the verified results."""
import csv
import json
import os

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(WORK, "report", "ecc2k130_isogeny_class_hardness.pdf")

FONTDIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
for name, fn in [("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"), ("DV-I", "DejaVuSans-Oblique.ttf"),
                 ("DV-BI", "DejaVuSans-BoldOblique.ttf"), ("DVM", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONTDIR, fn)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

INK = colors.HexColor("#0b0b0b")
INK2 = colors.HexColor("#52514e")
RULE = colors.HexColor("#d9d8d2")
TINT = colors.HexColor("#f3f2ee")
BLUE = colors.HexColor("#2a78d6")
BLUE_TINT = colors.HexColor("#eaf2fc")

body = ParagraphStyle("body", fontName="DV", fontSize=9, leading=12.6, textColor=INK, spaceAfter=5)
small = ParagraphStyle("small", parent=body, fontSize=8, leading=10.6, textColor=INK2)
cell = ParagraphStyle("cell", parent=body, fontSize=7.7, leading=9.8, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="DV-B")
h1 = ParagraphStyle("h1", fontName="DV-B", fontSize=13, leading=16, textColor=INK, spaceBefore=10, spaceAfter=6)
h2 = ParagraphStyle("h2", fontName="DV-B", fontSize=10, leading=13, textColor=INK, spaceBefore=6, spaceAfter=4)
title = ParagraphStyle("title", fontName="DV-B", fontSize=19, leading=23, textColor=INK, spaceAfter=4)
subtitle = ParagraphStyle("subtitle", fontName="DV", fontSize=10.5, leading=14, textColor=INK2, spaceAfter=10)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=3)
caption = ParagraphStyle("caption", parent=small, spaceBefore=2, spaceAfter=10)
callout = ParagraphStyle("callout", parent=body, fontSize=9.5, leading=13.4, spaceAfter=0)


def P(t, s=body):
    return Paragraph(t, s)


def B(items):
    return [Paragraph(t, bullet, bulletText="•") for t in items]


def tbl(rows, widths, header=True, zebra=True, font=cell):
    data = [[c if not isinstance(c, str) else Paragraph(c, cellb if (header and i == 0) else font) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK2),
          ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), TINT))
    t.setStyle(TableStyle(st))
    return t


def fig(name, width, cap):
    from reportlab.lib.utils import ImageReader
    path = os.path.join(HERE, name)
    iw, ih = ImageReader(path).getSize()
    return KeepTogether([Image(path, width=width, height=width * ih / iw), P(cap, caption)])


def box(flowables):
    t = Table([[flowables]], colWidths=[7.0 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE_TINT), ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def on_page(c, doc):
    c.saveState()
    c.setFont("DV", 7.5)
    c.setFillColor(INK2)
    if doc.page > 1:
        c.drawString(0.75 * inch, 10.62 * inch, "ECDLP hardness across the ECC2K-130 isogeny class")
        c.setStrokeColor(RULE)
        c.line(0.75 * inch, 10.56 * inch, 7.75 * inch, 10.56 * inch)
    c.drawRightString(7.75 * inch, 0.5 * inch, f"{doc.page}")
    c.drawString(0.75 * inch, 0.5 * inch, "2026-09-24 · work directory /Volumes/SSD990/ecdlp-hardness-work")
    c.restoreState()


def e(x):  # exponent helper
    return f"2<super>{x}</super>"


def build():
    info = json.load(open(os.path.join(HERE, "figure_info.json")))
    rows = list(csv.DictReader(open(os.path.join(WORK, "report", "per_curve_hardness.csv"))))
    W = 7.0 * inch
    s = []

    # ---------------- Title + answer ----------------
    s.append(P("ECDLP hardness across the ECC2K-130 isogeny class", title))
    s.append(P("E0, all 262 conductor-263 floor curves, and the unenumerated conductor-p and conductor-263p levels: "
               "a per-curve validation with adversarial verification", subtitle))
    s.append(box([
        P("<b>Answer.</b> No curve in the class is easier than E0. The best known ECDLP cost is "
          f"<b>{e('60.81')} ideal Pollard-rho iterations for E0 and for every one of the 262 floor curves</b> "
          f"({e('60.91')} with the Bailey et al. 2009 walk). A floor curve is intrinsically √131 ≈ 11.4× (3.52 bits) "
          "harder for rho because it has no Frobenius self-map, but its unique rational 263-isogeny up to E0 was built "
          f"and verified on all 262 curves and costs at most {e('15.6')} field multiplications, which removes the gap. "
          "The only levels where hardness could differ are conductor p and 263p "
          "(p = 146505763881528721 ≈ " + e('57') + "); there it lies between "
          f"{e('60.81')} and {e('64.33')}, and no such curve can be constructed at feasible cost.", callout)]))
    s.append(Spacer(1, 8))
    s.append(tbl([
        ["Level (conductor)", "End", "# curves", "Explicitly known", "Native rho (log2)", "Effective (log2)",
         "Why"],
        ["1 (crater)", "O<sub>K</sub> = Z[τ]", "1", "E0", "<b>60.81</b>", "<b>60.81</b>",
         "rho on ⟨−1, τ⟩ classes of size 262"],
        ["263 (floor)", "Z + 263·O<sub>K</sub>", "262", "all 262", "64.33", "<b>60.81</b>",
         f"unique rational 263-isogeny to E0, verified 262/262; ≤ {e('15.6')} F<sub>q</sub>-mults per instance"],
        ["p", "Z + p·O<sub>K</sub>", f"p + 1 ≈ {e('57.02')}", "none", "64.33", "<b>[60.81, 64.33]</b>",
         "lower end needs an unimplemented characteristic-2 Kani (higher-dimensional) isogeny pipeline"],
        ["263p (= Z[π])", "Z[π]", f"262(p + 1) ≈ {e('65.06')}", "none", "64.33", "<b>[60.81, 64.33]</b>",
         "cheap 263-step, then as level p"],
    ], [0.85 * inch, 0.8 * inch, 0.8 * inch, 0.65 * inch, 0.7 * inch, 0.75 * inch, 2.45 * inch]))
    s.append(Spacer(1, 8))
    s.append(fig("fig_levels.png", W * 0.92,
                 "<b>Figure 1.</b> Expected rho iterations by volcano level. Orange: rho run on the curve itself. "
                 "Blue: best known route (for the floor, transport to E0 first). For the p-levels the effective cost "
                 "is only known to lie in the shaded interval."))

    # ---------------- Scope ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("1. Scope and method", h1))
    s.append(P("Target: every curve F<sub>q</sub>-isogenous to the Certicom ECC2K-130 Koblitz curve "
               "E0 : y<super>2</super> + xy = x<super>3</super> + 1 over F<sub>q</sub>, q = 2<super>131</super> "
               "(polynomial basis modulo z<super>131</super> + z<super>13</super> + z<super>2</super> + z + 1). "
               "Isogenous curves share the group order 4N, so the question is whether the extra structure of each curve "
               "(endomorphism ring, coefficient b, twist, torsion) or its position in the isogeny volcano changes "
               "the cost of the discrete logarithm in the order-N subgroup."))
    s.append(P("The analysis ran as two multi-agent workflows: 184 agents in total. Two agents built the ground "
               "truth independently. Twelve attack-vector sweeps each covered all 263 explicit curves, and every "
               "claim was checked by two further verifiers, one recomputing with independent code and one auditing "
               "the original scripts. Three red-team agents looked for curve-specific weaknesses, a completeness "
               "critic ran six gap-fill tasks, and a synthesis agent merged the per-curve table. "
               "129 agents completed; 55 were lost to account usage limits and backfilled as described in §9. "
               "No attempt was made on the real challenge DLP; every solved DLP is a toy instance with a planted "
               "logarithm."))
    s.append(P("Constants (all re-derived): trace t = −22283658519494248867; #E = 4N with "
               "N = 680564733841876926932320129493409985129 (prime, Pocklington and Morrison proofs, "
               "log<sub>2</sub> N = 129.0); t<super>2</super> − 4q = −7f<super>2</super> with f = 263 · p, "
               "p = 146505763881528721 prime and inert in Q(√−7), 263 split. Class numbers of the four orders: "
               "h = 1, 262, p + 1, 262(p + 1) for conductors 1, 263, p, 263p.", small))

    # ---------------- Ground truth ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("2. The isogeny class and its ground truth", h1))
    s.append(fig("fig_volcano.png", W * 0.88,
                 "<b>Figure 2.</b> The ℓ = 263 volcano. E0 alone on the crater; 262 floor curves in two Frobenius "
                 "orbits of 131. Levels p and 263p hang below through degree-p isogenies and are not enumerated."))
    s.extend(B([
        "<b>Build.</b> Ring class polynomial H<sub>−7·263²</sub> (PARI polclass) is squarefree mod 2 and splits "
        "into two irreducible factors of degree 131, giving 262 roots in F<sub>q</sub>. All 263 curves were point-counted "
        "in both twists; a<sub>2</sub> = 0 is the order-4N twist on all 263, confirmed by point-order proofs.",
        "<b>Independent derivation.</b> Vélu isogenies from a basis of E0[263] over F<sub>q²</sub>, using neither "
        "H<sub>D</sub> nor Φ<sub>263</sub>: <b>262/262 j-invariants match, none extra on either side.</b> "
        "PARI polmodular confirms Φ<sub>263</sub>(1, Y) ≡ (Y + 1)<super>2</super> · H<sub>D</sub>(Y) mod 2.",
        "<b>Labels.</b> Codex's labels (A000–A130, B000–B130, X<sub>k</sub> with j = j(X000)<super>2^k</super>) "
        "are reproduced exactly, confirmed four ways including the H<sub>D</sub> coefficient hash.",
        "<b>Structural point.</b> Coordinate Frobenius (x, y) ↦ (x<super>2^k</super>, y<super>2^k</super>) is a "
        "free group isomorphism A000 → A<sub>k</sub>, so up to relabelling the 262 floor curves are two curves.",
    ]))

    # ---------------- Attack vectors ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("3. Attack vectors, curve by curve", h1))
    s.append(P("Every row covers all 263 explicit curves. “Verification” is the outcome of the independent recompute "
               "and audit.", small))
    s.append(tbl([
        ["Vector", "Result on all 263 explicit curves", "Effect", "Verification"],
        ["Group order / Pohlig–Hellman", "#E = 4N on 263/263; E(F<sub>q</sub>) ≅ Z/4N cyclic, 2-part Z/4 "
         "(never Z/2 × Z/2)", "0 bits (N prime)", "confirmed ×2 (C1–C3); C4 recompute confirmed"],
        ["Endomorphism ring", "End(E0) = O<sub>K</sub>; End = O<sub>263</sub> on 262/262 by ≥ 3 criteria "
         "(H<sub>D</sub> root, Vélu to j = 1, Φ<sub>263</sub> root structure, 263-Sylow of E(F<sub>q²</sub>): "
         "cyclic Z/263² on the floor, (Z/263)² on E0)", "defines the levels", "confirmed ×2 (C1–C3, C5); C4 by gap G1"],
        ["MOV / Frey–Rück", "embedding degree k = ord<sub>N</sub>(q) = 216464610000596986937760855436835237 "
         "(118 bits), identical on every curve by Tate's theorem", "0 bits", "confirmed ×2"],
        ["Anomalous / supersingular", "not applicable anywhere in the class (char 2, N ≠ 2, ordinary)", "0 bits",
         "confirmed ×2"],
        ["Pairings on 263-torsion", "t<sub>263</sub>(P, Q<sub>N</sub>) = 1 on every curve: blind to the N-part",
         "0 bits", "confirmed (recompute + gap G6)"],
        ["GHS / Weil descent", "magic number m = 1 on E0 (the cover is E0 over F<sub>2</sub>, order 4, kills the "
         f"N-part); m = 131 on all 262 floor curves (genus {e('130')}). 131 is prime, so F<sub>2</sub> is the only "
         "subfield", "0 bits", "re-verified on all 263 (gap G2)"],
        ["Rho automorphisms / endomorphisms", "Aut = {±1}; E0 adds τ (eigenvalue order 131 mod N). On the floor any "
         f"endomorphism with eigenvalue order &lt; {e('20')} (swept exactly to {e('32')}) has degree ≥ {e('114.6')}; "
         "Codex's ψ = (11-isogeny)∘Frob<super>16</super> has eigenvalue order (N − 1)/3",
         "E0 class 262; floor class 2", "re-verified with independent code (gap G1)"],
        ["Isogeny transport (floor → E0)", "unique rational 263-isogeny built on 262/262; codomain j = 1; "
         "planted-scalar homomorphism checks pass; dual composition = −[263]; three implementations agree",
         "floor effective = 60.81", "9 confirmed, 1 partially (cost wording)"],
        ["Index calculus (summation polynomials)", "rational-x densities indistinguishable from random curves "
         "(Figure 4); no method family beats rho, the closest non-generic model is ≥ 23.6 bits slower; Codex's E0 "
         "d<sub>reg</sub> advantage is a basis-presentation effect (0 bits after minimising over presentations)",
         "0 bits", "7 confirmed, 3 partially; gaps G3, G5"],
        ["Twist / x-only oracle", "leaks ±k mod 526 on E0 (8.04 bits), ±k mod 2·263² on floor curves (16.08 bits); "
         f"twist rho {e('53.27')} (E0's twist, ±τ) and {e('56.79')} (floor twists)",
         "unvalidated implementations only; ECDLP unchanged", "partially confirmed (corrected)"],
        ["Batch / multi-instance", "L pooled instances: amortised gain 0.5·log<sub>2</sub>L − 0.675 bits "
         "(3.35 bits at L = 263)", f"no single DLP below {e('60.81')}", "partially confirmed"],
    ], [1.2 * inch, 3.3 * inch, 1.05 * inch, 1.45 * inch]))

    # ---------------- Toys ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("4. Toy-scale end-to-end evidence", h1))
    s.append(P("Koblitz analogues over F<sub>2<super>n</super></sub> were chosen so that a small split prime ℓ divides "
               "the Frobenius conductor, giving the same volcano shape. For each, DLPs with planted logarithms were "
               "solved three ways: rho on a floor curve (negation only), rho on E0 (negation and τ classes), and "
               "transport floor → E0 followed by E0 rho. All 24,300 distinct planted DLPs (52,600 solver runs) were "
               "recovered and checked against the planted scalar. Two independent implementations were used."))
    s.append(fig("fig_toy.png", W * 0.9,
                 "<b>Figure 3.</b> Ratios of mean rho iterations with 95% intervals. Floor/E0 tracks √n, the size of "
                 "E0's Frobenius equivalence classes; transport-then-E0 matches E0 (ratio 1). Toy B's excess at "
                 "n = 179 comes from fruitless-cycle handling on the floor walk."))
    toy = json.load(open(os.path.join(HERE, "toy_a.json")))
    trows = [["Toy", "n", "ℓ", "N (bits)", "floor / E0 (± s.e.)", "√n", "(transport + E0) / E0"]]
    for r in toy:
        trows.append(["A", str(r["n"]), str(r["l"]), f"{r['log2N']:.1f}",
                      f"{r['i_over_ii_merge'][0]:.2f} ± {r['i_over_ii_merge'][1]:.2f}", f"{r['n'] ** 0.5:.2f}",
                      f"{r['iii_over_ii_merge'][0]:.3f} ± {r['iii_over_ii_merge'][1]:.3f}"])
    trows.append(["B", "179", "359", "35.8", f"{info['toy_b_ratio']:.2f} ± {info['toy_b_se']:.2f}",
                  f"{179 ** 0.5:.2f}", f"{info['toy_b_transport']:.3f} ± {info['toy_b_transport_se']:.3f}"])
    s.append(tbl(trows, [0.45 * inch, 0.5 * inch, 0.6 * inch, 0.8 * inch, 1.6 * inch, 0.7 * inch, 1.6 * inch]))
    s.append(Spacer(1, 4))
    s.append(P("A second toy level with a larger conductor prime (1721) mirrors the p-level situation: there, "
               "transport cost about 4,800× the rho cost on the level curve itself, so the level curve was effectively "
               "as hard as its native rho.", small))

    # ---------------- p levels ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("5. The conductor-p and conductor-263p levels", h1))
    s.extend(B([
        "Frobenius acts on E0[p] as the scalar c = t/2 mod p = 65861677189822723, of multiplicative order "
        f"r = 12208813656794060 ≈ {e('53.44')} = (p − 1)/12. Points of order p therefore exist only over "
        f"F<sub>q<super>r</super></sub>; their x-coordinates lie in F<sub>q<super>r/2</super></sub>, and one such "
        f"field element is about {e('59.5')} bits.",
        f"Classical routes are infeasible: kernel points ≥ {e('111.9')} F<sub>q</sub>-mults; the modular polynomial "
        f"Φ<sub>p</sub> Õ(p<super>2</super>) ≈ {e('114')}; complex multiplication with |D| = 7p<super>2</super> ≈ "
        f"{e('116.9')}.",
        "<b>Galbraith, “Climbing and descending tall isogeny volcanos”</b> (Research in Number Theory 11, 2025; "
        "ePrint 2024/924): Theorem 1 computes an evaluable representation of an unknown N-isogeny between two "
        "<i>given</i> curves in Õ(N<super>1/2</super>), using Kani/Robert embeddings of dimension 4, 6 or 8. For "
        f"N = p that climbs a presented level-p curve to E0 in Õ({e('28.5')}). But the theorem as proved uses "
        f"dimension 8, which models at ≥ {e('72')} F<sub>q</sub>-mults: worse than native rho, whose break-even "
        f"point is ≈ {e('66.5')}–{e('67.2')}.",
        f"Dimension-2 (not in the paper) and dimension-4 (heuristic) variants model at about {e('52.5')}–{e('55.5')} "
        "· κ F<sub>q</sub>-mults. Every published implementation of such isogeny chains assumes odd characteristic, "
        "and Theorem 1 uses E[4] and level-2 theta structures that do not carry over to characteristic 2 directly. "
        "A characteristic-2 Kani pipeline (gluing and splitting) does not exist.",
        "<b>Hence the effective hardness is in [60.81, 64.33].</b> If the characteristic-2 machinery were built with "
        "modest overhead, it would be about 60.9–62.0.",
        f"<b>Construction.</b> There is no structural shortcut. Generic search needs ≈ {e('64.94')} candidates per "
        "hit; with free 2-adic prefilters (#E mod 16, 32 and 64 read off low coefficients of b's characteristic "
        f"polynomial), the best known cost is ≈ {e('70.0')}–{e('71.3')} F<sub>q</sub>-mults, "
        f"about {e('7')}–{e('8')} E0 rho solves. That is more than solving natively on the curve once found, "
        "so no ECDLP instance can feasibly sit on these levels.",
    ]))

    # ---------------- IC ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("6. Index calculus across the class", h1))
    s.append(fig("fig_ic.png", W * 0.9,
                 f"<b>Figure 4.</b> Rational-x density z-scores over {info['n_class_cells']:,} (curve, subspace, k) "
                 f"cells for the 263 class curves, against {info['n_null_cells']:,} cells for 526 random, non-isogenous "
                 "curves over the same field. The two distributions coincide with each other and with a standard "
                 "normal. The class sample is effectively two curves, one per Frobenius orbit."))
    s.extend(B([
        "Relation probability ≈ |F|<super>m</super>/(m!·2<super>131</super>) depends on the factor-base size and the "
        "rational-lift condition Tr(x + b/x<super>2</super>) = 0, not on the endomorphism ring.",
        "Only E0 admits a τ-invariant factor base (Galbraith–Granger–Merz–Petit), worth up to m! in relation "
        "collection; that gain carries over to the floor curves through the isogeny.",
        "Per-curve Semaev point-decomposition problem at n = 131 (gap G5): Codex's E0 d<sub>reg</sub> 8 vs 10–11 is "
        "reproduced but is a polynomial-basis presentation effect. Every class curve reaches 7 on "
        "span{(b + 1)<super>j</super>}, a 0-bit difference after minimising over presentations.",
        "Cost model (gap G3): no method family beats rho; the tightest non-generic margin is +23.6 bits "
        "(Semaev 2015, D ≤ 4). As for every such claim at n = 131, this rests on extrapolation from small parameters.",
    ]))

    # ---------------- Red team ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("7. Red team", h1))
    s.append(P("Three agents generated 44 attack ideas from three angles: generic and endomorphism tricks, algebraic "
               "and cover attacks, and structure and edge cases. 37 self-refuted with computations; 4 work only "
               "amortised or against flawed implementations; 2 are plausible; 1 is open. The seven that were not "
               "self-refuted were each checked by two verifiers."))
    s.append(tbl([
        ["Idea", "Verdicts", "Outcome"],
        ["RT0-6 Kuhn–Struik batch over the 263 curves", "partial, confirmed",
         f"no single DLP below {e('60.81')}; 263 instances cost {e('65.50')} in total ({e('57.46')} each)"],
        ["RT0-7 Bernstein–Lange precomputation on E0", "partial ×2",
         f"precomputation {e('70.8')}–{e('80.8')} exceeds one rho; batch rho is better for known instance sets"],
        ["RT0-8 twist / x-only oracle", "partial ×2",
         "leaks k mod 2·263 on E0 (not 2·263²); stopped by an on-curve check; ECDLP unchanged"],
        ["RT2-13 pooling on E0 across curves", "partial ×2", "0.5·log<sub>2</sub>L − 0.675 bits amortised"],
        ["RT15 / RT2-01 Kani transport of the p-levels", "partial ×4",
         "conditional on a characteristic-2 dimension-2/4 algorithm; dimension 8 as proved gives no gain (§5)"],
        ["RT8 small-genus cover of the 130-dim Weil factor", "refuted numbers, partial",
         "break-even genus ≈ 273–314; cyclic order-131/263 covers excluded below genus 525; no construction "
         "known; open"],
    ], [2.2 * inch, 1.2 * inch, 3.6 * inch]))

    # ---------------- Corrections ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("8. Corrections made during verification", h1))
    s.append(P("All corrections below are already folded into the tables and figures above.", small))
    s.extend(B([
        f"Level 263p has 262(p + 1) ≈ {e('65.06')} curves, not about p; p is inert, not split.",
        "The GHS magic number on the floor is exactly 131, not “130 or 131”.",
        "The claim that transport from the p-levels is “infeasible by known methods” was refuted; it is "
        "conditional (§5).",
        f"The x-only twist leak on E0 is ±k mod 2·263, not mod 2·263². {e('53.27')} is E0's twist and {e('56.79')} "
        "the floor twists'. Subtract 1 bit for the sign.",
        f"Transport evaluation takes 788 additions, not 787. {e('15.59')} is the maximum over 262 measurements; "
        f"a full rebuild is ≈ {e('16.19')}.",
        "Batching gains were overstated: 0.5·log<sub>2</sub>L − 0.675 bits with independent base points.",
        f"The p-level construction cost is a best-known {e('70.0')}–{e('71.3')}, not a {e('72.97')} lower bound.",
        "The isogeny-walk reference to “Menezes–Qu–Teske” in the original prompt was wrong; the relevant work is "
        "Galbraith–Hess–Smart and Hess.",
    ]))

    # ---------------- Codex ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("9. Relation to the Codex investigation (Runs 01–13)", h1))
    s.append(P("Codex's numbers are correct (0 mismatches across 263 curves) and its “no advantage from descending” "
               "verdict stands. However, its per-descendant signals are artefacts:"))
    s.extend(B([
        "The 262 descendants are two curves up to coordinate Frobenius, so per-descendant differences are "
        "factor-base presentation effects.",
        "Run-08's best ratios (0.7075 → 0.9766 as k grows) match a pure-chance best-of-(262 × 64) model. Its "
        "“membership degree no worse” gate is a parity coin flip.",
        "E0's d<sub>reg</sub> 8 vs 10–11 comes from b = 1 being short in the polynomial basis; curves with b = t reach 7.",
        "B067's +20.7% attempt reduction is reproducible on E0's own subspaces (a selection effect).",
        "“Zero natural rows” was certain: expected relations were " + e('−96') + " … " + e('−108') + " per probe.",
        "Runs 09–12 measured quantities fixed by isomorphism invariance; Run-12's 4.07% is unstable (8.8% in Run-13). "
        "Run-13 counts targets in the whole group rather than the order-N subgroup (3.68–4.08× overstatement).",
        "What survives: a clean, verified CM and volcano dataset, including the Run-11 CM scalar alignment "
        "(δ ≡ 775 − ω, βγ ≡ −11 from the reverse map being −φ̂).",
    ]))

    # ---------------- Coverage ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("10. Coverage and residual uncertainty", h1))
    s.append(tbl([
        ["Stage", "Planned", "Returned", "Outcome"],
        ["Workflow 1: sweep-claim verifiers", "120", "67", "54 confirmed, 12 partially, 1 refuted; 53 lost to session limit"],
        ["Gap fills G1–G6", "6", "6", "rho endomorphisms and GHS re-verified on all 263; literature and levels "
         "reconciled; 48,220 cross-sweep comparisons, 12 errata"],
        ["Workflow 2: backfill verifiers", "22", "20", "all group-order, endomorphism-ring and pairing claims "
         "confirmed except group-order C5 (partially, corrected); 2 audits lost to the weekly limit"],
        ["Workflow 2: p-level crux", "3", "3", "interval [60.81, 64.33] confirmed; Galbraith 2024 read from source; "
         "construction figure corrected"],
        ["Red-team idea verifiers", "14", "14", "1 confirmed, 12 partially, 1 refuted"],
    ], [1.9 * inch, 0.6 * inch, 0.7 * inch, 3.8 * inch]))
    s.append(Spacer(1, 6))
    s.extend(B([
        "<b>Not established:</b> whether a characteristic-2 dimension-2/4 Kani isogeny pipeline can be built. That "
        "decides where in [60.81, 64.33] the p-levels sit. The small-genus cover question (RT8) is also open. "
        "Neither affects any curve that anyone can write down today.",
        "Two audit verifiers (group-order C4, C5) never ran; both claims have confirming or correcting recomputes.",
        "Index-calculus statements extrapolate from small parameters; the margin to rho is ≥ 23.6 bits.",
    ]))

    # ---------------- Files ----------------
    s.append(CondPageBreak(2.2 * inch))
    s.append(P("11. Files and reproduction", h1))
    s.append(P("All paths are relative to /Volumes/SSD990/ecdlp-hardness-work/.", small))
    s.append(tbl([
        ["Path", "Contents"],
        ["report/per_curve_hardness.csv", "263 rows × 19 columns, 0 empty cells (Appendix A)"],
        ["report/REPORT.md, report/claims_ledger.json", "Markdown report; every claim with verdicts and corrections"],
        ["ground_truth/, ground_truth_check/", "curve build (≈ 61 s: sage -python build_ground_truth.py), loader, "
         "independent Vélu derivation"],
        ["group-order/ … literature/ (12 sweeps)", "scripts, raw outputs, per_curve.json per attack vector"],
        ["verify/, verify2/, gaps/G1…G6/, redteam-*/", "verifier, gap-fill and red-team scripts and results"],
        ["codex-review/REVIEW.md", "run-by-run review of the Codex investigation"],
        ["report/pdf/", "this PDF's figure and layout scripts"],
    ], [2.6 * inch, 4.4 * inch]))

    # ---------------- Appendix ----------------
    s.append(PageBreak())
    s.append(P("Appendix A. Per-curve hardness table (all 263 explicit curves)", h1))
    s.append(P("j in hex (bit i = z<super>i</super> of the ECC2K-130 polynomial basis). All curves use a<sub>2</sub> = 0 "
               "and have #E = 4N, E(F<sub>q</sub>) ≅ Z/4N, embedding degree 118 bits. Native and effective costs are "
               "log<sub>2</sub> rho iterations. Transport is log<sub>2</sub> F<sub>q</sub>-multiplications to build the "
               "263-isogeny and evaluate two points. m is the GHS magic number. IC z is the canonical-subspace "
               "density z-score at k = 16.", small))
    mono = ParagraphStyle("mono", parent=cell, fontName="DVM", fontSize=6.3, leading=7.6)
    ap = [["Curve", "Level", "j (hex)", "m", "Class", "Native", "Transp.", "Effective", "IC z"]]
    for r in rows:
        ap.append([r["label"], r["level"], Paragraph(r["j_hex"], mono), r["ghs_magic_number"], r["aut_class_size"],
                   f"{float(r['intrinsic_rho_log2']):.2f}",
                   "—" if r["label"] == "E0" else f"{float(r['transport_cost']):.2f}",
                   f"{float(r['effective_hardness_log2']):.2f}", f"{float(r['ic_density_z_k16']):+.2f}"])
    small_cell = ParagraphStyle("sc", parent=cell, fontSize=6.6, leading=7.6)
    t = tbl(ap, [0.5 * inch, 0.45 * inch, 2.75 * inch, 0.4 * inch, 0.45 * inch, 0.55 * inch, 0.65 * inch,
                 0.65 * inch, 0.5 * inch], font=small_cell)
    t.setStyle(TableStyle([("TOPPADDING", (0, 1), (-1, -1), 0.8), ("BOTTOMPADDING", (0, 1), (-1, -1), 0.8)]))
    s.append(t)

    doc = BaseDocTemplate(OUT, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                          topMargin=0.8 * inch, bottomMargin=0.75 * inch,
                          title="ECDLP hardness across the ECC2K-130 isogeny class", author="Adam Buran",
                          subject="Per-curve ECDLP hardness validation for ECC2K-130 and its isogeny volcano")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
    doc.build(s)
    print(OUT)


if __name__ == "__main__":
    build()
