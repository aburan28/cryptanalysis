"""Render figures/replay.{svg,tex,pdf,png} from the archived replay artifact.

Reads run_github_39007026856/panel/replay_result.json and the archived K1 rank
records of koblitz-n83-stacked-20261016 (serials 42 and 43). Writes an SVG
directly and a TikZ source with the same numbers; the PDF and PNG are built
from the TikZ source (pdflatex, pdftoppm). Standard library only.
"""
import base64
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = json.loads((HERE / "run_github_39007026856/panel/replay_result.json").read_text())
ARCH = HERE.parent / "koblitz-n83-stacked-20261016/run_github_38862448935/panel/runs"


def archived_ns_per_probe(serial):
    text = (ARCH / f"{serial}.stdout.txt").read_text()
    raw = [l for l in text.splitlines() if l.startswith("raw_b64=")][0][8:]
    rec = json.loads(base64.b64decode(raw))
    summ = [r for r in rec["records"] if r.get("kind") == "compact_orbit_dlp_summary"][0]
    return rec["fields"]["rank_stage_ms"] * 1e6 / sum(summ["rank_attempt_probes"])


runs = {r["label"]: r for r in RES["runs"]}
bars = [  # (label, ns per probe, group)
    ("kS s42", archived_ns_per_probe("00042"), "amd"),
    ("kP s43", archived_ns_per_probe("00043"), "amd"),
    ("kS R1", runs["R1"]["ns_per_probe_rank_stage"], "intel"),
    ("kS R4", runs["R4"]["ns_per_probe_rank_stage"], "intel"),
    ("kP R2", runs["R2"]["ns_per_probe_rank_stage"], "intel"),
    ("kP R3", runs["R3"]["ns_per_probe_rank_stage"], "intel"),
]
ratio = RES["per_probe_wall_ratio_kP_over_kS"]
con = RES["construction"]
loads = [("R5 retained file", con["retained_base_load_ms_same_host"]),
         ("R6 constructed (X)", con["X_ms_constructed_base_load"])]
host = RES["host"]["cpu_model"]
orig = RES["host"]["original_cpu_model"]

# ---------- SVG ----------
W, H = 760, 380
col = {"amd": "#8a8f98", "intel": "#2f6db5", "load": "#c46a1b"}
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       'font-family="Helvetica, Arial, sans-serif" font-size="12">',
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
       '<text x="20" y="24" font-size="15" font-weight="bold">n = 83 K1 replay, run 39007026856: verdict replay_pass</text>']
# panel A
x0, y0, ph, pw = 70, 320, 240, 400
vmax = 700.0
svg.append(f'<text x="{x0}" y="56" font-weight="bold">(a) Rank-stage wall ns per probe (one process per bar; no interval)</text>')
for t in range(0, 701, 100):
    y = y0 - ph * t / vmax
    svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+pw}" y2="{y:.1f}" stroke="#e3e3e3"/>')
    svg.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end">{t}</text>')
svg.append(f'<text transform="translate(24,{y0-ph/2}) rotate(-90)" text-anchor="middle">ns per probe</text>')
bw = 44
for i, (lab, v, g) in enumerate(bars):
    bx = x0 + 18 + i * (bw + 20)
    h = ph * v / vmax
    svg.append(f'<rect x="{bx}" y="{y0-h:.1f}" width="{bw}" height="{h:.1f}" fill="{col[g]}"/>')
    svg.append(f'<text x="{bx+bw/2}" y="{y0-h-5:.1f}" text-anchor="middle" font-size="11">{v:.1f}</text>')
    svg.append(f'<text x="{bx+bw/2}" y="{y0+16}" text-anchor="middle" font-size="11">{lab}</text>')
svg.append(f'<line x1="{x0}" y1="{y0}" x2="{x0+pw}" y2="{y0}" stroke="#000"/>')
svg.append(f'<rect x="{x0}" y="{y0+28}" width="12" height="12" fill="{col["amd"]}"/>'
           f'<text x="{x0+18}" y="{y0+38}">archived, {orig} (serials 42, 43)</text>')
svg.append(f'<rect x="{x0}" y="{y0+46}" width="12" height="12" fill="{col["intel"]}"/>'
           f'<text x="{x0+18}" y="{y0+56}">replay, {host}</text>')
svg.append(f'<text x="{x0+pw-4}" y="76" text-anchor="end" font-size="11">kP/kS per-probe: replay {ratio["primary_rank_stage_pooled"]:.4f}, archived K1 {ratio["archived_K1_rank_stage"]:.4f}</text>')
# panel B
bx0, bpw = 520, 200
lmax = 500.0
svg.append(f'<text x="{bx0}" y="56" font-weight="bold">(b) K600 base load, ms (same host)</text>')
for t in range(0, 501, 100):
    y = y0 - ph * t / lmax
    svg.append(f'<line x1="{bx0+20}" y1="{y:.1f}" x2="{bx0+bpw}" y2="{y:.1f}" stroke="#e3e3e3"/>')
    svg.append(f'<text x="{bx0+14}" y="{y+4:.1f}" text-anchor="end">{t}</text>')
for i, (lab, v) in enumerate(loads):
    bx = bx0 + 40 + i * 80
    h = ph * v / lmax
    svg.append(f'<rect x="{bx}" y="{y0-h:.1f}" width="56" height="{h:.1f}" fill="{col["load"]}" opacity="{0.55 if i == 0 else 1}"/>')
    svg.append(f'<text x="{bx+28}" y="{y0-h-5:.1f}" text-anchor="middle" font-size="11">{v:.1f}</text>')
    svg.append(f'<text x="{bx+28}" y="{y0+16}" text-anchor="middle" font-size="10">{lab.split(" ", 1)[0]}</text>')
    svg.append(f'<text x="{bx+28}" y="{y0+29}" text-anchor="middle" font-size="10">{lab.split(" ", 1)[1]}</text>')
svg.append(f'<line x1="{bx0+20}" y1="{y0}" x2="{bx0+bpw}" y2="{y0}" stroke="#000"/>')
svg.append(f'<text x="{bx0+20}" y="{y0+50}" font-size="11">X - retained = {con["X_minus_retained_ms"]:.1f} ms; base hash equal</text>')
svg.append('</svg>')
(HERE / "figures/replay.svg").write_text("\n".join(svg) + "\n")

# ---------- TikZ (same numbers) ----------
def tex_esc(s):
    return s.replace("_", r"\_")

tik = [r"\documentclass[border=4pt]{standalone}", r"\usepackage{tikz}", r"\usepackage{lmodern}",
       r"\renewcommand{\familydefault}{\sfdefault}",
       r"\definecolor{amd}{HTML}{8A8F98}\definecolor{intel}{HTML}{2F6DB5}\definecolor{load}{HTML}{C46A1B}",
       r"\begin{document}\begin{tikzpicture}[x=1pt,y=-1pt,font=\scriptsize]"]
tik.append(r"\node[anchor=west,font=\small\bfseries] at (20,24) {n = 83 K1 replay, run 39007026856: verdict replay\_pass};")
tik.append(rf"\node[anchor=west,font=\scriptsize\bfseries] at ({x0},56) {{(a) Rank-stage wall ns per probe (one process per bar; no interval)}};")
for t in range(0, 701, 100):
    y = y0 - ph * t / vmax
    tik.append(rf"\draw[gray!25] ({x0},{y:.1f}) -- ({x0+pw},{y:.1f}); \node[anchor=east] at ({x0-4},{y:.1f}) {{{t}}};")
tik.append(rf"\node[rotate=90] at (24,{y0-ph/2}) {{ns per probe}};")
for i, (lab, v, g) in enumerate(bars):
    bx = x0 + 18 + i * (bw + 20)
    h = ph * v / vmax
    tik.append(rf"\fill[{g}] ({bx},{y0}) rectangle ({bx+bw},{y0-h:.1f}); \node at ({bx+bw/2},{y0-h-7:.1f}) {{{v:.1f}}}; \node at ({bx+bw/2},{y0+12}) {{{lab}}};")
tik.append(rf"\draw ({x0},{y0}) -- ({x0+pw},{y0});")
tik.append(rf"\fill[amd] ({x0},{y0+28}) rectangle +(10,10); \node[anchor=west] at ({x0+16},{y0+33}) {{archived, {orig} (serials 42, 43)}};")
tik.append(rf"\fill[intel] ({x0},{y0+46}) rectangle +(10,10); \node[anchor=west] at ({x0+16},{y0+51}) {{replay, {host}}};")
tik.append(rf"\node[anchor=east] at ({x0+pw-4},74) {{kP/kS per-probe: replay {ratio['primary_rank_stage_pooled']:.4f}, archived K1 {ratio['archived_K1_rank_stage']:.4f}}};")
tik.append(rf"\node[anchor=west,font=\scriptsize\bfseries] at ({bx0},56) {{(b) K600 base load, ms (same host)}};")
for t in range(0, 501, 100):
    y = y0 - ph * t / lmax
    tik.append(rf"\draw[gray!25] ({bx0+20},{y:.1f}) -- ({bx0+bpw},{y:.1f}); \node[anchor=east] at ({bx0+16},{y:.1f}) {{{t}}};")
for i, (lab, v) in enumerate(loads):
    bx = bx0 + 40 + i * 80
    h = ph * v / lmax
    op = 0.55 if i == 0 else 1
    a, b = lab.split(" ", 1)
    tik.append(rf"\fill[load,opacity={op}] ({bx},{y0}) rectangle ({bx+56},{y0-h:.1f}); \node at ({bx+28},{y0-h-7:.1f}) {{{v:.1f}}}; \node at ({bx+28},{y0+12}) {{{a}}}; \node at ({bx+28},{y0+24}) {{{b}}};")
tik.append(rf"\draw ({bx0+20},{y0}) -- ({bx0+bpw},{y0});")
tik.append(rf"\node[anchor=west] at ({bx0+20},{y0+46}) {{X $-$ retained = {con['X_minus_retained_ms']:.1f} ms; base hash equal}};")
tik.append(r"\end{tikzpicture}\end{document}")
(HERE / "figures/replay.tex").write_text("\n".join(tik) + "\n")

subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "replay.tex"],
               cwd=HERE / "figures", check=True, stdout=subprocess.DEVNULL)
subprocess.run(["pdftoppm", "-png", "-r", "160", "-singlefile", "replay.pdf", "replay"],
               cwd=HERE / "figures", check=True)
for ext in ("aux", "log"):
    (HERE / f"figures/replay.{ext}").unlink(missing_ok=True)
print(json.dumps({"bars_ns_per_probe": {l: round(v, 3) for l, v, _ in bars}, "loads_ms": dict(loads)}, indent=1))
