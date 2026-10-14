#!/usr/bin/env python3
"""Draw the report figures as hand-written SVG from results/*.json (no
plotting library), then rasterize each to PNG with ImageMagick `convert`
when it is available.

figures/ir_per_word.svg    Ir per word by arm and distribution (cachegrind)
figures/distributions.svg  per-word histograms: longest runs c, gap-scan
                           rotations, refinement depth (uniform, structured)
figures/layout.svg         diagram: the 64/64/3 word, a zero run across a
                           limb boundary, and the three arms
"""
import json
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda f: json.load(open(os.path.join(HERE, "results", f)))
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

INK, MUTED, GRID = "#1f2328", "#59636e", "#d0d7de"
C_UNI, C_STR, C_REF = "#2f6db5", "#d08a1e", "#8250df"
FONT = "font-family='DejaVu Sans, Helvetica, Arial, sans-serif'"


def svg(w, h, body):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
            f"viewBox='0 0 {w} {h}' {FONT}><rect width='100%' height='100%' fill='white'/>"
            + body + "</svg>\n")


def text(x, y, s, size=12, anchor="start", color=INK, weight="normal", rot=None):
    t = f" transform='rotate({rot} {x} {y})'" if rot is not None else ""
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return (f"<text x='{x:.1f}' y='{y:.1f}' font-size='{size}' text-anchor='{anchor}' "
            f"fill='{color}' font-weight='{weight}'{t}>{s}</text>")


def save(name, content):
    p = os.path.join(FIG, name)
    open(p, "w").write(content)
    rasterize(p, p[:-4] + ".png")


def rasterize(src, dst, scale=2):
    """Render this script's SVG subset (rect, line, circle, polyline, text)
    with Pillow; ImageMagick on this host has no SVG delegate."""
    import xml.etree.ElementTree as ET
    from PIL import Image, ImageDraw, ImageFont
    ns = "{http://www.w3.org/2000/svg}"
    root = ET.parse(src).getroot()
    W, H = int(float(root.get("width"))), int(float(root.get("height")))
    im = Image.new("RGB", (W * scale, H * scale), "white")
    d = ImageDraw.Draw(im)
    fonts = {}

    def font(size, bold):
        key = (size, bold)
        if key not in fonts:
            name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            try:
                fonts[key] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, int(size * scale))
            except OSError:
                fonts[key] = ImageFont.load_default()
        return fonts[key]

    S = lambda v: float(v) * scale
    for el in root.iter():
        tag = el.tag.replace(ns, "")
        if tag == "rect" and el.get("width") != "100%":
            x, y = S(el.get("x", 0)), S(el.get("y", 0))
            d.rectangle([x, y, x + S(el.get("width")), y + S(el.get("height"))],
                        fill=el.get("fill"), outline=el.get("stroke"))
        elif tag == "line":
            d.line([S(el.get("x1")), S(el.get("y1")), S(el.get("x2")), S(el.get("y2"))],
                   fill=el.get("stroke"), width=max(1, int(S(el.get("stroke-width", 1)))))
        elif tag == "circle":
            cx, cy, r = S(el.get("cx")), S(el.get("cy")), S(el.get("r"))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=el.get("fill"))
        elif tag == "polyline":
            pts = [tuple(S(v) for v in p.split(",")) for p in el.get("points").split()]
            if len(pts) > 1:
                d.line(pts, fill=el.get("stroke"), width=max(1, int(S(el.get("stroke-width", 1)))))
        elif tag == "text":
            f = font(float(el.get("font-size", 12)), el.get("font-weight") == "bold")
            anchor = {"start": "ls", "middle": "ms", "end": "rs"}[el.get("text-anchor", "start")]
            d.text((S(el.get("x")), S(el.get("y"))), el.text or "", fill=el.get("fill"), font=f, anchor=anchor)
    im.save(dst)


def ir_figure():
    ins = R("instructions.json")
    rows = {(r["arm"], r["distribution"]): r["Ir_per_word"] for r in ins["rows"]}
    arms = ["exhaustive", "exhaustive_bf", "refine_bf", "gap_scan", "lift_scan"]
    label = {"exhaustive": "(a) exhaustive", "exhaustive_bf": "exhaustive, branch-free",
             "refine_bf": "(c) refine, branch-free", "gap_scan": "(b) zero-gap scan",
             "lift_scan": "lift + candidates (A-like)"}
    fm = rows.get(("fmul", "uniform"))
    W, H, L, T, B = 760, 400, 200, 50, 60
    vmax = max(v for v in rows.values() if v) * 1.08
    pw = W - L - 30
    bh = 13
    body = text(W / 2, 22, "Retired instructions per 131-bit word (cachegrind Ir, {:,} words per cell)".format(ins["words"]), 14, "middle", weight="bold")
    for k in range(0, int(vmax) + 1, 1000):
        x = L + pw * k / vmax
        body += f"<line x1='{x:.1f}' y1='{T}' x2='{x:.1f}' y2='{H-B}' stroke='{GRID}'/>"
        body += text(x, H - B + 16, f"{k:,}", 11, "middle", MUTED)
    body += text(L + pw / 2, H - B + 36, "Ir per word (deterministic count; lower is cheaper)", 12, "middle", MUTED)
    gh = (H - B - T) / len(arms)
    for i, a in enumerate(arms):
        y0 = T + i * gh + gh / 2 - bh - 1
        body += text(L - 8, y0 + bh + 4, label[a], 12, "end")
        for j, (d, c) in enumerate([("uniform", C_UNI), ("structured", C_STR)]):
            v = rows.get((a, d))
            if v is None:
                continue
            y = y0 + j * (bh + 2)
            body += f"<rect x='{L}' y='{y:.1f}' width='{pw*v/vmax:.1f}' height='{bh}' fill='{c}' rx='2'/>"
            body += text(L + pw * v / vmax + 4, y + bh - 2, f"{v:,.0f}", 10, "start", MUTED)
    if fm:
        x = L + pw * fm / vmax
        body += f"<line x1='{x:.1f}' y1='{T-6}' x2='{x:.1f}' y2='{H-B}' stroke='{C_REF}' stroke-dasharray='4 3' stroke-width='1.5'/>"
        body += text(x + 4, T - 8, f"one F(2^131) poly-basis multiply (proxy): {fm:,.0f} Ir", 11, "start", C_REF)
    lx = L + 10
    body += f"<rect x='{lx}' y='{H-18}' width='12' height='10' fill='{C_UNI}'/>" + text(lx + 16, H - 9, "uniform words", 11)
    body += f"<rect x='{lx+130}' y='{H-18}' width='12' height='10' fill='{C_STR}'/>" + text(lx + 146, H - 9, "structured (near-periodic) words", 11)
    null = rows.get(("null", "uniform"))
    body += text(W - 10, H - 9, f"call overhead (null arm) {null:,.0f} Ir included", 10, "end", MUTED)
    save("ir_per_word.svg", svg(W, H, body))


def hist_panel(x0, y0, w, h, title, series, xmax, xlabel, logy=False):
    import math
    body = text(x0 + w / 2, y0 - 8, title, 12, "middle", weight="bold")
    body += f"<line x1='{x0}' y1='{y0+h}' x2='{x0+w}' y2='{y0+h}' stroke='{INK}'/>"
    # fractions
    norm = []
    for name, c, hist in series:
        n = sum(hist.values())
        norm.append((name, c, {int(k): v / n for k, v in hist.items()}))
    ymax = max(max(d.values()) for _, _, d in norm)
    def Y(f):
        if logy:
            lo = -7
            v = max(math.log10(f), lo) if f > 0 else lo
            return y0 + h - h * (v - lo) / (0 - lo)
        return y0 + h - h * f / (ymax * 1.05)
    ticks = [10 ** -k for k in range(0, 8)] if logy else [ymax * t / 4 for t in range(5)]
    for t in ticks:
        y = Y(t)
        body += f"<line x1='{x0}' y1='{y:.1f}' x2='{x0+w}' y2='{y:.1f}' stroke='{GRID}'/>"
        lab = (f"1e-{-int(round(math.log10(t)))}" if t < 1 else "1") if logy else f"{t:.2f}"
        body += text(x0 - 4, y + 4, lab, 9, "end", MUTED)
    bw = w / (xmax + 1)
    for si, (name, c, d) in enumerate(norm):
        pts = []
        for k in range(0, xmax + 1):
            f = d.get(k, 0)
            if f > 0:  # every plotted value is >= 1e-7 (1 word in 10^7)
                x = x0 + (k + 0.5) * bw
                pts.append(f"{x:.1f},{Y(f):.1f}")
                body += f"<circle cx='{x:.1f}' cy='{Y(f):.1f}' r='2' fill='{c}'/>"
        if pts:
            body += f"<polyline points='{' '.join(pts)}' fill='none' stroke='{c}' stroke-width='1.3'/>"
    for k in range(0, xmax + 1, max(1, xmax // 6)):
        body += text(x0 + (k + 0.5) * bw, y0 + h + 14, str(k), 9, "middle", MUTED)
    body += text(x0 + w / 2, y0 + h + 30, xlabel, 11, "middle", MUTED)
    return body


def dist_figure():
    u, s = R("metrics_uniform.json"), R("metrics_structured.json")
    W, H = 960, 330
    body = text(W / 2, 20, "Per-word counts at n = 131: uniform (%s words) vs structured (%s words); "
                "fraction of words, log scale" % (f"{u['words']:,}", f"{s['words']:,}"), 13, "middle", weight="bold")
    pw, ph, top = 260, 200, 60
    panels = [("longest_runs_c", "longest zero runs c (A-type candidates)", 65),
              ("gap_scan_rotations", "zero-gap scan rotate-and-compares", 65),
              ("refine_depth", "refinement steps to one candidate", 130)]
    for i, (key, lab, xm) in enumerate(panels):
        x0 = 60 + i * (pw + 50)
        body += hist_panel(x0, top, pw, ph, lab,
                           [("uniform", C_UNI, u[key]["hist"]), ("structured", C_STR, s[key]["hist"])],
                           xm, f"uniform mean {u[key]['mean']:.2f}, max {u[key]['max']}; "
                               f"structured max {s[key]['max']}", logy=True)
    body += f"<rect x='60' y='{H-18}' width='12' height='10' fill='{C_UNI}'/>" + text(76, H - 9, "uniform", 11)
    body += f"<rect x='150' y='{H-18}' width='12' height='10' fill='{C_STR}'/>" + text(166, H - 9, "structured (period 2-20, <=1 flip)", 11)
    body += text(W - 10, H - 9, "refine_bf always runs 130 steps; its fixed count is the max of the right panel's support", 10, "end", MUTED)
    save("distributions.svg", svg(W, H, body))


def layout_figure():
    W, H = 900, 330
    body = text(W / 2, 22, "A 131-bit normal-basis word in [u64; 3] and the three exact arms", 14, "middle", weight="bold")
    x0, y0, cell = 40, 50, 820 / 131
    for lo, hi, name in [(0, 64, "limb 0: bits 0-63"), (64, 128, "limb 1: bits 64-127"), (128, 131, "limb 2: 128-130")]:
        # draw high bits on the left (bit 130 leftmost)
        xa = x0 + (130 - (hi - 1)) * cell
        xb = x0 + (131 - lo) * cell
        body += f"<rect x='{xa:.1f}' y='{y0}' width='{xb-xa:.1f}' height='26' fill='#f6f8fa' stroke='{INK}'/>"
        body += text((xa + xb) / 2, y0 + 44, name, 10, "middle", MUTED)
    # a zero run straddling bit 64
    za, zb = 58, 71
    xa, xb = x0 + (130 - zb) * cell, x0 + (131 - za) * cell
    body += f"<rect x='{xa:.1f}' y='{y0+2}' width='{xb-xa:.1f}' height='22' fill='#cfe3ff' stroke='{C_UNI}'/>"
    body += text((xa + xb) / 2, y0 - 6, "longest zero run Z = 14, bits 58-71 (crosses the 63|64 limb edge)", 10, "middle", C_UNI)
    body += text(x0, y0 + 64, "bit 130 (most significant)", 9, "start", MUTED)
    body += text(x0 + 820, y0 + 64, "bit 0", 9, "end", MUTED)
    body += text(x0, y0 + 84, "rotl(x, s) moves bit 130-s to the top; the least rotation starts at the top of a longest zero run: s = 130 - p (Lemma lem:zerogap)", 11)
    rows = [
        ("(a) exhaustive", "130 rotate-by-one steps, keep the first strict minimum", "reference; ties take the least s"),
        ("(b) zero-gap scan", "ctz over every set bit (~65 per uniform word); rotate-and-compare at each gap >= running max",
         "branchy; data-dependent trip counts"),
        ("(c) refine, branch-free", "candidate mask C; for t = 0..129: C' = C & ~rotl(x,t); C = C' if C' != 0 (mask select)",
         "fixed 130 steps; the first Z steps are the zero-gap filter"),
        ("", "then s = 130 - msb(C) (per-limb lzcnt + select), word = 8-stage masked barrel rotation",
         "one conditional jump: the loop counter"),
    ]
    y = y0 + 120
    for a, b, c in rows:
        body += text(x0, y, a, 12, weight="bold")
        body += text(x0 + 175, y, b, 11)
        body += text(x0 + 175, y + 15, c, 10, "start", MUTED)
        y += 42
    save("layout.svg", svg(W, H, body))


if __name__ == "__main__":
    layout_figure()
    ir_figure()
    dist_figure()
    print("figures written")
