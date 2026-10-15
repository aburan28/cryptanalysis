#!/usr/bin/env python3
"""Figures from one run's analysis.json, as dependency-free SVG.

  make_figures.py <run_dir> [<fig_dir>]     default fig_dir: <run_dir>/figures

  step_price.svg   ns/step per arm with 95% intervals, n = 131 and n = 83
  shares.svg       canonicalization shares at n = 131 and n = 83 (timing and Ir)
  completion.svg   steps/floor per arm at n = 83 with 95% intervals and the
                   heuristic predictions
"""
import json
import sys
from pathlib import Path

INK, MUTED, GRID = "#1f2933", "#6b7785", "#d9dee4"
C1, C2, C3 = "#2f6fb0", "#c2571a", "#5b8c3a"


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="12">\n<rect width="{w}" height="{h}" fill="white"/>\n'
            f'<text x="16" y="22" font-size="14" font-weight="bold" fill="{INK}">{title}</text>\n{body}</svg>\n')


def hbars(rows, x0, y0, width, vmax, color, unit, ref=None):
    """rows: (label, value, lo, hi). Horizontal bars with interval whiskers."""
    out = []
    sc = width / vmax
    for t in range(0, 6):
        v = vmax * t / 5
        x = x0 + v * sc
        out.append(f'<line x1="{x:.1f}" y1="{y0 - 6}" x2="{x:.1f}" y2="{y0 + 22 * len(rows)}" stroke="{GRID}"/>')
        out.append(f'<text x="{x:.1f}" y="{y0 + 22 * len(rows) + 14}" text-anchor="middle" fill="{MUTED}">{v:.3g}</text>')
    out.append(f'<text x="{x0 + width / 2:.1f}" y="{y0 + 22 * len(rows) + 30}" text-anchor="middle" fill="{MUTED}">{unit}</text>')
    if ref is not None:
        x = x0 + ref * sc
        out.append(f'<line x1="{x:.1f}" y1="{y0 - 8}" x2="{x:.1f}" y2="{y0 + 22 * len(rows)}" stroke="{INK}" stroke-dasharray="4 3"/>')
    for i, (lab, v, lo, hi, *pred) in enumerate(rows):
        y = y0 + 22 * i
        col = color(lab) if callable(color) else color
        out.append(f'<text x="{x0 - 8}" y="{y + 12}" text-anchor="end" fill="{INK}">{lab}</text>')
        out.append(f'<rect x="{x0}" y="{y}" width="{max(0, v) * sc:.1f}" height="16" fill="{col}" opacity="0.85"/>')
        out.append(f'<line x1="{x0 + lo * sc:.1f}" y1="{y + 8}" x2="{x0 + hi * sc:.1f}" y2="{y + 8}" stroke="{INK}" stroke-width="1.5"/>')
        for e in (lo, hi):
            out.append(f'<line x1="{x0 + e * sc:.1f}" y1="{y + 3}" x2="{x0 + e * sc:.1f}" y2="{y + 13}" stroke="{INK}" stroke-width="1.5"/>')
        out.append(f'<text x="{x0 + max(v, hi) * sc + 6:.1f}" y="{y + 12}" fill="{INK}">{v:.4g}</text>')
        if pred:
            xp = x0 + pred[0] * sc
            out.append(f'<path d="M{xp - 5:.1f},{y - 2} L{xp + 5:.1f},{y - 2} L{xp:.1f},{y + 5} Z" fill="{INK}"/>')
    return "\n".join(out)


def main():
    run = Path(sys.argv[1])
    figs = Path(sys.argv[2]) if len(sys.argv) > 2 else run / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    a = json.loads((run / "analysis.json").read_text())
    run_id = run.name
    col = lambda lab: C1 if lab.startswith("bailey") else (C3 if "exh" in lab else C2)
    body = []
    for k, n in enumerate(("131", "83")):
        ns = a["timing"][n]["ns_per_step"]
        rows = [(arm, v["geomean"], *v["ci95"]) for arm, v in ns.items()]
        vmax = max(r[3] for r in rows) * 1.18
        body.append(f'<text x="16" y="{52 + k * 260}" font-weight="bold" fill="{INK}">n = {n} (gates: {a["timing"][n]["gates"]})</text>')
        body.append(hbars(rows, 130, 64 + k * 260, 520, vmax, col, "ns per lane-step (geometric mean of 30 rounds, 95% bootstrap interval)"))
    body.append(f'<text x="16" y="568" fill="{MUTED}">Tier 1, {run_id}; 64 lockstep lanes, pinned CPU; blue: Bailey arms, orange: adding arms, green: positive control.</text>')
    (figs / "step_price.svg").write_text(svg(780, 580, "\n".join(body), "Per-step price of the two walk designs"))

    body = []
    rows = []
    for n in ("131", "83"):
        for k, v in a["timing"][n]["shares"].items():
            rows.append((f"n={n} {k.split(' ')[0]}", v["estimate"], *v["ci95"]))
    body.append(hbars(rows, 260, 50, 420, 1.0, C2, "share of the step (1 - ablated/full), 95% interval"))
    if a.get("ir"):
        y = 50 + 22 * len(rows) + 60
        body.append(f'<text x="16" y="{y}" font-weight="bold" fill="{INK}">Ir-based (cachegrind, exact counts)</text>')
        irrows = []
        for n in ("131", "83"):
            d = a["ir"][n]
            for k in ("share_canonicalization_whole", "share_lift_scan", "share_bailey_at_dp"):
                irrows.append((f"n={n} {k[6:]}", d[k], d[k], d[k]))
        body.append(hbars(irrows, 260, y + 14, 420, 1.0, C1, "share of Ir per step"))
    (figs / "shares.svg").write_text(svg(780, 560, "\n".join(body), "Canonicalization's share of a step"))

    c = a["completion"]
    pred = c["heuristic_predictions"]
    rows = [(arm, v["mean_steps_over_floor"], *v["ci95"], pred.get(arm, v["mean_steps_over_floor"]))
            for arm, v in c["per_arm"].items()]
    body = [hbars(rows, 130, 50, 520, max(r[3] for r in rows) * 1.2, col,
                  "mean steps / sqrt(pi r / (2*166)), 95% target-bootstrap interval; triangles: heuristic 1/sqrt(1 - sum p_j^2)", ref=1.0)]
    y = 50 + 22 * len(rows) + 60
    for i, (k, v) in enumerate(c["ratios"].items()):
        body.append(f'<text x="16" y="{y + 18 * i}" fill="{INK}">{k}: {v["estimate"]:.4f} [{v["ci95"][0]:.4f}, {v["ci95"][1]:.4f}]</text>')
    body.append(f'<text x="16" y="{y + 18 * len(c["ratios"]) + 10}" fill="{MUTED}">n = 83, a = 1, r = 8569786107849059; 64 panel targets x 2 seeds per arm; '
                f'{c["rows"]} solves, {c["unverified"]} unverified; {run_id}</text>')
    (figs / "completion.svg").write_text(svg(780, y + 18 * len(c["ratios"]) + 30, "\n".join(body),
                                             "Steps to a verified collision at n = 83 (where walks complete)"))
    print("figures:", ", ".join(sorted(p.name for p in figs.glob("*.svg"))))


if __name__ == "__main__":
    main()
