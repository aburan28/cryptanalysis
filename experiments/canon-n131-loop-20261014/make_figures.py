#!/usr/bin/env python3
"""Figures for canon-n131-loop-20261014, as hand-written SVG (no plotting
library on the host), rasterized to PNG by a small Pillow renderer of the same SVG subset
(ImageMagick on this host has no SVG delegate).

  figures/loop.svg     the loop and its dependency structure (diagram)
  figures/counts.svg   cachegrind Ir, Bc and modelled Bcm per key (results/counts.json)
  figures/timing.svg   Tier 1 ratios to lift_scan with adjusted CIs, from the newest
                       non-smoke results/ci/*/analysis.json; skipped when none exists

usage: python3 make_figures.py
"""
import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
ARMS = ["exhaustive", "gap_scan", "refine_bf", "exhaustive_bf", "lift_scan", "null"]
COL = {"exhaustive": "#4269d0", "gap_scan": "#efb118", "refine_bf": "#ff725c", "exhaustive_bf": "#6cc5b0",
       "lift_scan": "#3ca951", "lift_scan_aa": "#97bbf5", "null": "#9498a0"}
FONT = 'font-family="DejaVu Sans, Helvetica, Arial, sans-serif"'


def save(name, w, h, body):
    os.makedirs(FIG, exist_ok=True)
    p = os.path.join(FIG, name)
    with open(p, "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {FONT}>\n')
        f.write(f'<rect width="{w}" height="{h}" fill="white"/>\n{body}</svg>\n')
    rasterize(p, p[:-4] + ".png")
    print("wrote", p)


def rgb(c, op=1.0):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    v = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    return tuple(int(255 - (255 - x) * op) for x in v)


def rasterize(src, dst, scale=2):
    """Render this script's SVG subset (rect, line, circle, polyline, polygon, text)."""
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
            fonts[key] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, int(size * scale))
        return fonts[key]

    def col(el, key, opkey):
        c = el.get(key)
        if not c or c == "none":
            return None
        if c == "white":
            return (255, 255, 255)
        return rgb(c, float(el.get(opkey, 1)))

    S = lambda v: float(v) * scale
    for el in root.iter():
        tag = el.tag.replace(ns, "")
        if tag == "rect":
            x, y = S(el.get("x", 0)), S(el.get("y", 0))
            d.rectangle([x, y, x + S(el.get("width")), y + S(el.get("height"))],
                        fill=col(el, "fill", "fill-opacity"), outline=col(el, "stroke", "stroke-opacity"),
                        width=max(1, int(S(el.get("stroke-width", 1)))))
        elif tag == "line":
            d.line([S(el.get("x1")), S(el.get("y1")), S(el.get("x2")), S(el.get("y2"))],
                   fill=col(el, "stroke", "stroke-opacity"), width=max(1, int(S(el.get("stroke-width", 1)))))
        elif tag == "circle":
            cx, cy, r = S(el.get("cx")), S(el.get("cy")), S(el.get("r"))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col(el, "fill", "fill-opacity"))
        elif tag in ("polyline", "polygon"):
            pts = [tuple(S(v) for v in q.split(",")) for q in el.get("points").split()]
            if tag == "polygon":
                d.polygon(pts, fill=col(el, "fill", "fill-opacity"))
            else:
                d.line(pts, fill=col(el, "stroke", "stroke-opacity"), width=max(1, int(S(el.get("stroke-width", 1)))))
        elif tag == "text":
            f = font(float(el.get("font-size", 12)), el.get("font-weight") == "bold")
            anchor = {"start": "ls", "middle": "ms", "end": "rs"}[el.get("text-anchor", "start")]
            d.text((S(el.get("x")), S(el.get("y"))), el.text or "", fill=col(el, "fill", "x") or (34, 34, 34),
                   font=f, anchor=anchor)
    im.save(dst)


def text(x, y, s, size=12, anchor="start", weight="normal", fill="#222222"):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}">{s}</text>\n'


def box(x, y, w, h, label, sub="", fill="#eef2fb", stroke="#4269d0"):
    b = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
    b += text(x + w / 2, y + h / 2 - (4 if sub else -4), label, 13, "middle", "bold")
    if sub:
        b += text(x + w / 2, y + h / 2 + 13, sub, 10.5, "middle")
    return b


def arrow(x1, y1, x2, y2, color="#333333"):
    L = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    bx, by = x2 - 9 * ux, y2 - 9 * uy
    pts = f"{x2},{y2} {bx - 4 * uy},{by + 4 * ux} {bx + 4 * uy},{by - 4 * ux}"
    return (f'<line x1="{x1}" y1="{y1}" x2="{bx}" y2="{by}" stroke="{color}" stroke-width="1.6"/>\n'
            f'<polygon points="{pts}" fill="{color}"/>\n')


def loop_diagram():
    w, h = 900, 400
    b = text(20, 28, "One key of the loop (per key i); the field chain is the only loop-carried dependency", 15, weight="bold")
    # chain row
    b += box(20, 60, 170, 64, "state s(i-1)", "polynomial basis (f131.h)")
    b += box(250, 60, 210, 64, "field step", "W1: 1M + 1S   W5: 5M + 1S (proxy)", "#fdf3dc", "#b8860b")
    b += box(520, 60, 170, 64, "state s(i)", "next key's input")
    b += arrow(190, 92, 250, 92) + arrow(460, 92, 520, 92)
    b += '<polyline points="690,92 740,92 740,46 105,46" fill="none" stroke="#b8860b" stroke-width="1.6"/>\n'
    b += arrow(105, 46, 105, 60, "#b8860b")
    b += text(420, 42, "serial chain: s(i) feeds key i+1", 11, "middle", fill="#8a6408")
    # side row
    b += box(520, 170, 170, 64, "to normal basis", "fromPolynomial + 131-bit perm")
    b += box(270, 170, 190, 64, "canonicalize", "arm under test (canon-n131)", "#e8f6ec", "#3ca951")
    b += box(20, 170, 190, 64, "probe table", "hash, bucket, exact compare", "#fde9e6", "#ff725c")
    b += arrow(605, 124, 605, 170) + arrow(520, 202, 460, 202) + arrow(270, 202, 210, 202)
    b += box(20, 290, 190, 54, "hits, key fold, shift sum", "accumulators only")
    b += arrow(115, 234, 115, 290)
    b += text(720, 196, "off the critical path:", 11, weight="bold")
    b += text(720, 212, "overlaps with the chain of", 11)
    b += text(720, 228, "keys i+1, i+2, ... as far as", 11)
    b += text(720, 244, "the reorder window allows", 11)
    b += text(270, 268, "arms: exhaustive, gap_scan, refine_bf, exhaustive_bf, lift_scan,", 11)
    b += text(270, 284, "lift_scan_aa (A/A copy), null (no canonicalization: loop floor)", 11)
    b += text(270, 316, "table: small 2^14 records (0.41 MB) or large 2^22 records (104.9 MB),", 11)
    b += text(270, 332, "mean bucket load 4; planted hits = canonical keys of 1/64 of the stream", 11)
    b += text(20, 382, "Proxy labels: the field elements are real F_2^131 elements in the ECC2K-130 walk's normal basis, "
              "not curve x-coordinates.", 10.5, fill="#555555")
    save("loop.svg", w, h, b)


def counts_figure():
    p = os.path.join(HERE, "results", "counts.json")
    if not os.path.exists(p):
        print("no counts.json; skipping counts figure")
        return
    d = json.load(open(p))
    iso = json.load(open(os.path.join(HERE, "results", "isolated_ir.json")))
    wl = ["w1-small", "w5-small"]
    w, h = 900, 470
    b = text(20, 26, "Deterministic counts per key inside the loop (cachegrind, 65,536 keys per symbol)", 15, weight="bold")
    # panel 1: Ir per key
    x0, y0, pw, ph = 80, 60, 480, 330
    vmax = max(d["workloads"][x]["arms"][a]["Ir_per_key"] for x in wl for a in ARMS) * 1.08
    b += text(x0, y0 - 10, "Ir per key (bars) and null loop + isolated canon Ir (ticks)", 12, weight="bold")
    ticks = range(0, 10001, 1000)
    for t in ticks:
        if t > vmax:
            break
        y = y0 + ph - ph * t / vmax
        b += f'<line x1="{x0}" y1="{y}" x2="{x0 + pw}" y2="{y}" stroke="#ddd"/>\n' + text(x0 - 6, y + 4, f"{t:,}", 10, "end")
    gw = pw / len(ARMS)
    for i, a in enumerate(ARMS):
        for j, x in enumerate(wl):
            v = d["workloads"][x]["arms"][a]["Ir_per_key"]
            bx = x0 + i * gw + 8 + j * (gw - 16) / 2
            bw = (gw - 16) / 2 - 3
            y = y0 + ph - ph * v / vmax
            op = "1" if j == 0 else "0.55"
            b += f'<rect x="{bx}" y="{y}" width="{bw}" height="{ph * v / vmax}" fill="{COL[a]}" fill-opacity="{op}"/>\n'
            b += text(bx + bw / 2, y - 3, f"{v:,.0f}", 8.5, "middle")
            if a in iso:
                pv = d["workloads"][x]["arms"]["null"]["Ir_per_key"] + iso[a] - 6.0
                py = y0 + ph - ph * pv / vmax
                b += f'<line x1="{bx - 2}" y1="{py}" x2="{bx + bw + 2}" y2="{py}" stroke="#111" stroke-width="2"/>\n'
        b += text(x0 + i * gw + gw / 2, y0 + ph + 16, a, 10.5, "middle")
    b += f'<line x1="{x0}" y1="{y0 + ph}" x2="{x0 + pw}" y2="{y0 + ph}" stroke="#333"/>\n'
    b += text(x0, y0 + ph + 38, "left bar W1 (1M+1S), right bar W5 (5M+1S); small table. Large-table Ir is in counts.json.", 10)
    b += text(x0, y0 + ph + 52, "tick = null loop Ir + isolated canon-n131 Ir - 6 (its call overhead): the additive prediction", 10)
    # panel 2: branches
    x1, pw2 = 640, 190
    bmax = max(d["workloads"]["w1-small"]["arms"][a]["Bc_per_key"] for a in ARMS) * 1.1
    b += text(x1, y0 - 10, "W1: Bc and modelled Bcm per key", 12, weight="bold")
    rh = ph / len(ARMS)
    for i, a in enumerate(ARMS):
        A = d["workloads"]["w1-small"]["arms"][a]
        y = y0 + i * rh + 6
        bc, bm = A["Bc_per_key"], A["Bcm_per_key"]
        b += f'<rect x="{x1}" y="{y}" width="{pw2 * bc / bmax}" height="{rh / 2 - 6}" fill="{COL[a]}"/>\n'
        b += text(x1 + pw2 * bc / bmax + 4, y + rh / 4 + 1, f"Bc {bc:,.1f}", 9.5)
        mm = max(A["Bcm_per_key"] for A in d["workloads"]["w1-small"]["arms"].values()) * 1.1
        b += f'<rect x="{x1}" y="{y + rh / 2 - 4}" width="{pw2 * bm / mm}" height="{rh / 2 - 6}" fill="{COL[a]}" fill-opacity="0.45"/>\n'
        b += text(x1 + pw2 * bm / mm + 4, y + rh * 3 / 4 - 1, f"Bcm {bm:,.2f}", 9.5)
        b += text(x1 - 6, y + rh / 2, a, 10, "end")
    b += text(x1 - 60, y0 + ph + 38, "Bcm scale is separate from Bc;", 10)
    b += text(x1 - 60, y0 + ph + 52, "Bcm is cachegrind's predictor MODEL, not hardware", 10)
    save("counts.svg", w, h, b)


def timing_figure():
    cands = []
    for p in glob.glob(os.path.join(HERE, "results", "ci", "*", "analysis.json")):
        a = json.load(open(p))
        if not a.get("smoke"):
            cands.append((os.path.getmtime(p), p, a))
    if not cands:
        print("no Tier 1 analysis yet; skipping timing figure")
        return
    _, p, a = max(cands)
    run = os.path.basename(os.path.dirname(p))
    arms = ["exhaustive", "gap_scan", "refine_bf", "exhaustive_bf", "lift_scan_aa", "null"]
    wls = list(a["workloads"])
    w, h = 900, 120 + 70 * len(wls) * 1 + 30 * len(arms) * len(wls) // 2
    rows = [(x, arm) for x in wls for arm in arms]
    h = 110 + 22 * len(rows) + 14 * len(wls)
    b = text(20, 26, f"In-loop time per key relative to lift_scan (Tier 1, {run})", 15, weight="bold")
    b += text(20, 44, f"geometric mean over {a['meta']['rounds']} paired rounds; bar = Bonferroni CI "
              f"({a['adjusted_level']:.4f}), thin = 95%; log scale", 11)
    vals = [a["workloads"][x]["contrasts"][arm] for x, arm in rows]
    lo = min(v["ci_adjusted"][0] for v in vals) * 0.9
    hi = max(v["ci_adjusted"][1] for v in vals) * 1.1
    x0, pw = 260, 560

    def X(v):
        return x0 + pw * (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo))
    y = 70
    for t in [0.05, 0.1, 0.2, 0.5, 1, 2, 3, 5, 8, 10]:
        if lo <= t <= hi:
            b += f'<line x1="{X(t)}" y1="60" x2="{X(t)}" y2="{h - 40}" stroke="{"#333" if t == 1 else "#ddd"}"/>\n'
            b += text(X(t), h - 26, f"{t:g}", 10, "middle")
    cur = None
    for (x, arm), v in zip(rows, vals):
        if x != cur:
            y += 14
            b += text(20, y + 4, x, 12, weight="bold")
            cur = x
        b += text(x0 - 8, y + 4, arm, 10.5, "end")
        b += f'<line x1="{X(v["ci95"][0])}" y1="{y}" x2="{X(v["ci95"][1])}" y2="{y}" stroke="{COL[arm]}" stroke-width="1.5"/>\n'
        b += f'<line x1="{X(v["ci_adjusted"][0])}" y1="{y}" x2="{X(v["ci_adjusted"][1])}" y2="{y}" stroke="{COL[arm]}" stroke-width="5" stroke-opacity="0.6"/>\n'
        b += f'<circle cx="{X(v["ratio_vs_lift_scan_geomean"])}" cy="{y}" r="3.5" fill="#111"/>\n'
        b += text(x0 + pw + 8, y + 4, f'{v["ratio_vs_lift_scan_geomean"]:.3f}', 10)
        y += 22
    b += text(x0 + pw / 2, h - 10, "t(arm) / t(lift_scan) per key  (<1: arm faster)", 11, "middle")
    save("timing.svg", w, h, b)


if __name__ == "__main__":
    loop_diagram()
    counts_figure()
    timing_figure()
