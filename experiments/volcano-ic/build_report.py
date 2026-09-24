"""Render report/index.html from results/summary.json and the raw records.

    sage -python analyze.py && sage -python build_report.py
"""
import base64
import collections
import glob
import html
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
TOTAL_CURVES_B = 31


def rows(pattern):
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, 'results', pattern))):
        out += [json.loads(l) for l in open(path) if l.strip()]
    return out


def img(name):
    path = os.path.join(HERE, 'figures', name)
    if not os.path.exists(path):
        return ''
    data = base64.b64encode(open(path, 'rb').read()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="">'


def f(x, d=3):
    return f'{x:,.{d}f}'


def pct(x):
    return f'{x:.0f}th' if int(round(x)) % 10 not in (1, 2, 3) or 10 < int(round(x)) % 100 < 14 else \
        f'{x:.0f}' + {1: 'st', 2: 'nd', 3: 'rd'}[int(round(x)) % 10]


def ecdlpTable(census):
    seen, recs = set(), []
    for r in rows('ecdlp-*.jsonl'):
        k = (r['curve'], r['instance'])
        if k not in seen:
            seen.add(k)
            recs.append(r)
    by = collections.defaultdict(list)
    for r in recs:
        by[r['curve']].append(r)
    order = sorted(by, key=lambda c: (c != 'E0', c))
    body = []
    for c in order:
        v = by[c]
        cen = census[c]
        att = statistics.mean(r['gb_calls'] for r in v)
        cpu = statistics.median(r['total_cpu_s'] for r in v)
        ok = sum(r['correct'] for r in v)
        body.append(
            f'<tr class="{"e0" if c == "E0" else ""}"><th scope="row">{c}</th><td>{cen["fb_size"]}</td>'
            f'<td>{cen["exact_decomp_prob"]:.4f}</td><td>{cen["expected_attempts_per_dlp"]:.1f}</td>'
            f'<td>{att:.1f}</td><td>{statistics.mean(r["relations"] for r in v):.0f}</td>'
            f'<td>{cpu:.0f}</td><td>{ok}/{len(v)}</td></tr>')
    return recs, len(order), '\n'.join(body)


def interleaveBlock(s):
    il = s.get('interleaved_gb')
    if not il:
        return ''
    rowsHtml = []
    for c in il['curves']:
        p = il['per_curve'][c]
        rowsHtml.append(f'<tr class="{"e0" if c == "E0" else ""}"><th scope="row">{c}</th><td>{p["mean_ms"]:.0f}</td>'
                        f'<td>{p["solvable_fraction"]:.2f}</td><td>{p["mean_ms_solvable"]:.0f}</td><td>{p["mean_ms_unsolvable"]:.0f}</td></tr>')
    sv, un = il['solvable_vs_unsolvable_ms']
    return f'''<h3>Drift-controlled comparison</h3>
<div class="prose">
<p>CPU time on this machine still drifts, because under heavy load macOS moves work between performance and
efficiency cores. Across all 457 curves, measured one after another, that drift produces an apparent curve effect
(Kruskal–Wallis p = {s["census"]["gb_cpu_seconds_per_call"]["kruskal_by_curve"]["p"]:.1g}). To separate curve from time, E0 and nine descendants
(the six yield extremes and three orbit representatives) were solved round-robin in one process, in a freshly shuffled order each
round, for {il["rounds"]} rounds. Each round is a block, so drift cancels.</p>
<p><b>No curve effect remains</b> (Friedman χ² = {il["friedman_curve"]["chi2"]:.1f}, p = {il["friedman_curve"]["p"]:.2f}). E0 costs
{il["e0_over_descendant_mean_ratio"]:.2f}× the descendant mean per decomposition (Wilcoxon p = {il["e0_vs_descendant_mean_wilcoxon_p"]:.2f}).
What does move the cost is the target: systems with solutions take {sv:.0f} ms against {un:.0f} ms for systems without.</p>
</div>
<div class="tw"><table>
<thead><tr><th>curve</th><th>mean ms</th><th>solvable share</th><th>ms, solvable</th><th>ms, unsolvable</th></tr></thead>
<tbody>{"".join(rowsHtml)}</tbody></table></div>'''


def ecdlpStats(s):
    ev = s['ecdlp']
    an = ev['anova_log_metrics']
    e0v = ev['e0_vs_descendants']
    pm = ev['predicted_vs_measured_attempts']
    names = {'gb_calls': 'decomposition attempts', 'total_cpu_s': 'total CPU seconds', 'gb_cpu_s': 'Gröbner CPU seconds',
             'linalg_s': 'linear-algebra seconds', 'total_s': 'wall-clock seconds'}
    body = []
    for k, label in names.items():
        a = an[k]
        body.append(f'<tr><th scope="row">{label}</th><td>{a["curve"]["F"]:.2f}</td><td>{a["curve"]["p"]:.2g}</td>'
                    f'<td>{a["curve"]["eta2"]:.2f}</td><td>{a["instance"]["F"]:.2f}</td><td>{a["instance"]["p"]:.2g}</td>'
                    f'<td>{a["instance"]["eta2"]:.2f}</td></tr>')
    g = e0v['gb_calls']
    t = e0v['total_cpu_s']
    return f'''<div class="key">
<div><b>{ev["correct_logs"][0]}/{ev["correct_logs"][1]}</b><span>discrete logs recovered and verified</span></div>
<div><b>{pm["mean_ratio_measured_over_predicted"]:.3f}</b><span>measured / census-predicted attempts (curve means correlate r = {pm["pearson_r_curve_means"]:.2f})</span></div>
<div><b>{g["ratio_e0_over_desc"]:.3f}×</b><span>E0 attempts relative to descendants, 95% CI {g["ratio_ci95"][0]:.3f}–{g["ratio_ci95"][1]:.3f} (Mann–Whitney p = {g["mannwhitney_p"]:.2f})</span></div>
<div><b>p = {an["gb_calls"]["instance"]["p"]:.2f}</b><span>scalar (instance) effect on attempts</span></div>
</div>
<div class="figure">{img("ecdlp.png")}</div>
<p class="cap">A: attempts per ECDLP for every Tier B curve; black ticks mark the census prediction (|F| + 10) / Pr[decomp].
B: curve means against prediction. C: the same 10 scalars across all 31 curves.</p>
<h3>Curve × instance analysis</h3>
<div class="prose"><p>Additive two-way ANOVA on log values, 31 curves × 10 shared scalars, one run per cell. Attempts are the
load-independent measure of work. They carry a small curve effect that the census already predicts from the factor base,
and no instance effect. The timing rows show large "curve" effects because each curve's ten runs happened in their own
time slot, so curve is confounded with machine load. E0 ran during the heaviest-load hour and so looks {100 * (t["ratio_e0_over_desc"] - 1):.0f}% slower
in CPU seconds, while its attempt count is {100 * (g["ratio_e0_over_desc"] - 1):+.1f}% and the interleaved test shows equal per-solve cost.</p></div>
<div class="tw"><table>
<thead><tr><th>measure (log)</th><th>curve F</th><th>curve p</th><th>curve η²</th><th>instance F</th><th>instance p</th><th>instance η²</th></tr></thead>
<tbody>{"".join(body)}</tbody></table></div>'''


def main():
    s = json.load(open(os.path.join(HERE, 'results', 'summary.json')))
    c = s['census']
    census = {r['curve']: r for r in rows('census-*.jsonl')}
    recs, nCurvesB, table = ecdlpTable(census)
    correct = sum(r['correct'] for r in recs)
    cpu = c.get('gb_cpu_seconds_per_call') or {}
    e0 = c['e0']
    dr = c['descendants_range']
    pc = c['e0_percentile']
    hit = c['gb_hit_rate']
    ev = s.get('ecdlp', {})
    an = ev.get('anova_log_metrics', {})
    e0v = ev.get('e0_vs_descendants', {})
    dregVals = ', '.join(f'{k} ({v})' for k, v in c['dreg']['values'].items())
    final = nCurvesB >= TOTAL_CURVES_B and 'curves' in s.get('ecdlp', {}) and len(s['ecdlp']['curves']) >= TOTAL_CURVES_B
    status = 'Final' if final else 'Partial'
    statusNote = ('All tiers complete.' if final else
                  f'Census complete for all 457 curves. End-to-end ECDLP runs: {len(recs)} of '
                  f'{TOTAL_CURVES_B * 10} solves across {nCurvesB} of {TOTAL_CURVES_B} curves; '
                  f'CPU-time Gröbner re-measure: {cpu.get("curves", 0)} of 457 curves.')

    page = f'''<title>Volcano Index Calculus</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:ital,wght@0,400;0,500;1,400&display=swap">
<style>
:root {{
  --ground: #F5F7F6; --panel: #FFFFFF; --ink: #1A2229; --muted: #58666F; --rule: #D6DDDA;
  --crater: #B5462B; --floor: #2F679E; --good: #2E7D55; --plate: #FFFFFF;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  --sans: "IBM Plex Sans", system-ui, -apple-system, Segoe UI, sans-serif;
  --cond: "IBM Plex Sans Condensed", "IBM Plex Sans", system-ui, sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground: #12171B; --panel: #192026; --ink: #E3E8E6; --muted: #9AA7AE; --rule: #2C363D;
    --crater: #E27B5E; --floor: #7FAAD8; --good: #6CC196; --plate: #F3F5F4; color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --ground: #12171B; --panel: #192026; --ink: #E3E8E6; --muted: #9AA7AE; --rule: #2C363D;
  --crater: #E27B5E; --floor: #7FAAD8; --good: #6CC196; --plate: #F3F5F4; color-scheme: dark;
}}
body {{ background: var(--ground); color: var(--ink); font: 16px/1.6 var(--sans); }}
.wrap {{ max-width: 1080px; margin: 0 auto; padding-inline: 20px; padding-block: 40px 72px; }}
.prose {{ max-width: 68ch; }}
h1, h2, h3 {{ font-family: var(--cond); text-wrap: balance; line-height: 1.15; }}
h1 {{ font-size: clamp(30px, 5vw, 44px); font-weight: 600; margin: 8px 0 12px; }}
h2 {{ font-size: 26px; font-weight: 600; margin: 56px 0 12px; padding-top: 20px; border-top: 1px solid var(--rule); }}
h3 {{ font-size: 18px; font-weight: 600; margin: 28px 0 8px; }}
p {{ margin: 0 0 14px; }}
.eyebrow {{ font: 500 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
.status {{ display: inline-flex; gap: 8px; align-items: center; font: 500 13px var(--mono); padding: 4px 10px;
  border: 1px solid var(--rule); border-radius: 999px; background: var(--panel); }}
.status i {{ width: 8px; height: 8px; border-radius: 50%; background: {"var(--good)" if final else "var(--crater)"}; }}
.lede {{ font-size: 19px; color: var(--muted); max-width: 64ch; }}
.answer {{ background: var(--panel); border: 1px solid var(--rule); border-radius: 6px; padding: 20px 24px; margin: 28px 0; }}
.answer ul {{ margin: 8px 0 0; padding-left: 20px; display: grid; gap: 8px; }}
code, .num {{ font-family: var(--mono); font-size: .92em; }}
.tw {{ overflow-x: auto; margin: 16px 0 8px; }}
table {{ border-collapse: collapse; font-variant-numeric: tabular-nums; font-size: 14px; min-width: 100%; }}
th, td {{ padding: 7px 12px; border-bottom: 1px solid var(--rule); text-align: right; white-space: nowrap; }}
thead th {{ font: 500 12px var(--mono); color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
th[scope=row], thead th:first-child, td:first-child {{ text-align: left; font-family: var(--mono); font-weight: 500; }}
tr.e0 th, tr.e0 td {{ color: var(--crater); }}
.figure {{ background: var(--plate); border-radius: 6px; padding: 12px; margin: 20px 0 6px; border: 1px solid var(--rule); }}
.figure img {{ display: block; width: 100%; height: auto; }}
.cap {{ font-size: 14px; color: var(--muted); max-width: 80ch; }}
.key {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 20px 0; }}
.key div {{ background: var(--panel); border: 1px solid var(--rule); border-radius: 6px; padding: 14px 16px; }}
.key b {{ display: block; font: 500 24px var(--mono); }}
.key span {{ font-size: 13px; color: var(--muted); }}
.crater {{ color: var(--crater); }} .floor {{ color: var(--floor); }}
.formula {{ font-family: var(--mono); background: var(--panel); border: 1px solid var(--rule); border-radius: 6px;
  padding: 12px 16px; overflow-x: auto; white-space: nowrap; }}
</style>
<div class="wrap">
<div class="eyebrow">ECC2K-130 volcano study · n = 19 analogue · {html.escape(status)} report</div>
<h1>Does descending the isogeny volcano change index calculus?</h1>
<p class="status"><i></i>{html.escape(statusNote)}</p>
<p class="lede">A scaled copy of ECC2K-130's volcano, small enough that complete index calculus finishes:
the Koblitz crater curve <span class="crater">E0</span> over F<sub>2</sub><sup>19</sup> and every one of its
<span class="floor">456 floor descendants</span>, measured on relation yield, point decomposition, Gröbner
degree of regularity, and end-to-end ECDLP runtime over 10 fixed scalars.</p>

<div class="answer">
<div class="eyebrow">Short answer{"" if final else " so far"}</div>
<ul>
<li><b>Relation yield differs between curves, but only through the factor base.</b> Yield is an exact function of
three counts (how many factor-base points carry each Z/4 torsion tag), verified on {c["eligible_formula_matches"][0]}/{c["eligible_formula_matches"][1]} curves.
Nothing about the endomorphism ring enters.</li>
<li><b>Those differences nearly cancel in total work.</b> Descendants range {dr["exact_decomp_prob"][0]:.3f}–{dr["exact_decomp_prob"][2]:.3f} in
decomposition probability, but a bigger factor base also needs more relations, so predicted attempts per ECDLP span only
{dr["expected_attempts_per_dlp"][0]:.0f}–{dr["expected_attempts_per_dlp"][2]:.0f} (±{100 * (dr["expected_attempts_per_dlp"][2] - dr["expected_attempts_per_dlp"][0]) / 2 / dr["expected_attempts_per_dlp"][1]:.1f}%). E0 needs {e0["expected_attempts_per_dlp"]:.0f}.</li>
<li><b>Degree of regularity is identical everywhere:</b> {dregVals} across all sampled systems. This is forced
algebraically: the curve coefficient only appears as a constant term.</li>
<li><b>End-to-end ECDLP:</b> {correct}/{len(recs)} logs recovered and verified across {nCurvesB} curves × 10 scalars. Work per ECDLP depends
weakly on the curve, and exactly as the census predicts (r = {ev["predicted_vs_measured_attempts"]["pearson_r_curve_means"]:.2f}; measured/predicted
= {ev["predicted_vs_measured_attempts"]["mean_ratio_measured_over_predicted"]:.3f}). It does not depend on the scalar (p = {an["gb_calls"]["instance"]["p"]:.2f}).
E0 needs {e0v["gb_calls"]["ratio_e0_over_desc"]:.3f}× the descendants' attempts (95% CI {e0v["gb_calls"]["ratio_ci95"][0]:.3f}–{e0v["gb_calls"]["ratio_ci95"][1]:.3f}).</li>
<li><b>Bottom line:</b> descending the volcano changes nothing structural for this attack. Curve-to-curve differences are
factor-base counting, a few percent at most, and they partly cancel. E0's one real advantage, the Frobenius endomorphism, is not exercised by this factor base.</li>
</ul>
</div>

<h2>Why a scaled analogue</h2>
<div class="prose">
<p>On ECC2K-130 itself, a natural relation at any feasible factor-base size has probability around 2<sup>−120</sup>;
earlier runs found zero relations on public targets, so no index-calculus runtime exists to compare. The
n = 19 curve keeps the structure that matters and is small enough to solve.</p>
</div>
<div class="tw"><table>
<thead><tr><th></th><th>ECC2K-130</th><th>n = 19 analogue</th></tr></thead>
<tbody>
<tr><th scope="row">curve</th><td>y² + xy = x³ + 1 over F<sub>2</sub><sup>131</sup></td><td>y² + xy = x³ + 1 over F<sub>2</sub><sup>19</sup></td></tr>
<tr><th scope="row">cofactor · prime</th><td>4 · N (129-bit)</td><td>4 · 130 873</td></tr>
<tr><th scope="row">End(E0)</th><td>ℤ[τ], disc −7</td><td>ℤ[τ], disc −7</td></tr>
<tr><th scope="row">Frobenius conductor</th><td>263, split in ℚ(√−7)</td><td>457, split in ℚ(√−7)</td></tr>
<tr><th scope="row">floor descendants</th><td>262 (2 Frobenius orbits)</td><td>456 (24 Frobenius orbits of 19)</td></tr>
</tbody></table></div>
<p class="cap">The 457-curve isogeny class was found by exhaustive point counting over all 2<sup>19</sup> values of b and matches
the class-number count 1 + (457 − 1) exactly.</p>

<h2>Method</h2>
<div class="prose">
<p><b>Factor base.</b> Points with x in V = span{{1, z, …, z<sup>9</sup>}}, up to sign: the same polynomial coordinate
subspace for every curve. <b>Decomposition.</b> Each target R = αP + βQ is split as ±P<sub>1</sub> ± P<sub>2</sub> through the
summation polynomial S<sub>3</sub>(x<sub>1</sub>, x<sub>2</sub>, x<sub>R</sub>) = (x<sub>1</sub>x<sub>2</sub>)² + x<sub>R</sub>²(x<sub>1</sub>² + x<sub>2</sub>²) + x<sub>R</sub>x<sub>1</sub>x<sub>2</sub> + b,
Weil-descended to 19 quadratic Boolean equations in 20 unknowns and solved with a PolyBoRi Gröbner basis.
<b>Linear algebra.</b> Relations on the cofactor-cleared factor base mod p; the log of Q comes from a left-kernel
vector and is checked against the known scalar.</p>
<p><b>Tier A</b> covers all 457 curves: exact yield by enumerating every factor-base pair, formal degree of regularity,
and Gröbner samples drawn from each of the 10 ECDLP instances. <b>Tier B</b> runs full index calculus with the same
10 scalars on E0, one seeded descendant per Frobenius orbit, and the three highest- and lowest-yield descendants.</p>
</div>

<h2>Relation yield</h2>
<div class="key">
<div><b>{c["eligible_formula_matches"][0]}/{c["eligible_formula_matches"][1]}</b><span>curves where eligible pairs equal the Z/4 tag formula exactly</span></div>
<div><b>{c["birthday_model_max_abs_error"]:.4f}</b><span>largest gap between exact yield and the birthday model</span></div>
<div><b>{e0["fb_size"]}</b><span>E0 factor-base size, {pct(pc["fb_size"])} percentile of descendants ({dr["fb_size"][0]}–{dr["fb_size"][2]})</span></div>
<div><b>{e0["expected_attempts_per_dlp"]:.0f}</b><span>E0 predicted attempts per ECDLP, {pct(pc["expected_attempts_per_dlp"])} percentile</span></div>
</div>
<div class="prose">
<p>E(F<sub>2</sub><sup>19</sup>) ≅ ℤ/4 × ℤ/p on every curve, so each factor-base point carries a torsion tag in ℤ/4. A sum or
difference lands in the prime subgroup only when the tags cancel. With n<sub>0</sub>, n<sub>2</sub>, n<sub>odd</sub> the tag counts:</p>
<p class="formula">eligible = 2·C(n₀,2) + n₀ + 2·C(n₂,2) + n₂ + C(n_odd,2)&nbsp;&nbsp;&nbsp;Pr[decomp] ≈ 1 − exp(−eligible / ((p−1)/2))</p>
<p>E0 has (n₀, n₂, n_odd) = ({e0["tag_counts"][0]}, {e0["tag_counts"][2]}, {e0["tag_counts"][1] + e0["tag_counts"][3]}), giving {e0["eligible_signed_pairs"]:,} eligible pairs and
Pr = {e0["exact_decomp_prob"]:.4f}. Every curve sits on the same birthday curve (panel B). Descendants reach
more targets only by having more rational points in V, and factor-base size is not explained by Frobenius orbit
(Kruskal–Wallis p = {c["fb_size_by_orbit_kruskal"]["p"]:.2f}).</p>
<p>A larger factor base raises the yield but also raises the number of relations needed, which is why
predicted attempts per ECDLP fall only from {dr["expected_attempts_per_dlp"][2]:.0f} to {dr["expected_attempts_per_dlp"][0]:.0f} as
factor-base size rises from {dr["fb_size"][0]} to {dr["fb_size"][2]} (r = {c["corr_fb_size_vs_expected_attempts"]:.2f}, panel C).</p>
</div>
<div class="figure">{img("census.png")}</div>
<p class="cap">Tier A over all 457 curves. D uses CPU time from a separate re-measurement
({cpu.get("curves", 0)} of 457 curves). The census wall-clock Gröbner timings drift with machine load in processing
order and are not used for between-curve comparison.</p>

<h2>Point decomposition and Gröbner bases</h2>
<div class="key">
<div><b>{hit["hits"]:,} / {hit["calls"]:,}</b><span>Gröbner decompositions that produced a relation; {hit["expected_hits"]:,.0f} expected from exact yield (z = {hit["z"]:.2f})</span></div>
<div><b>{hit["spurious_solutions"]}</b><span>spurious S₃ solutions rejected at lift time ({100 * hit["spurious_solutions"] / hit["calls"]:.2f}% of solves)</span></div>
<div><b>{dregVals.split(" ")[0]}</b><span>formal degree of regularity, every one of {sum(c["dreg"]["values"].values())} sampled systems</span></div>
<div><b>{1000 * cpu.get("median_s", 0):.0f} ms</b><span>median Gröbner CPU time per decomposition</span></div>
</div>
<div class="prose">
<p>The Gröbner solver finds exactly the relations the exact yield predicts: the pooled hit rate differs from
expectation by {abs(hit["z"]):.1f} standard deviations. The degree of regularity cannot differ between curves in this
formulation: squaring is linear over F<sub>2</sub>, so the quadratic part of every equation comes from
(x₁x₂)² + x<sub>R</sub>x₁x₂ and depends on the target alone. b only shifts constants.</p>
<p>Per-decomposition CPU cost does not track factor-base size (Spearman ρ = {cpu.get("spearman_mean_vs_fb_size", float("nan")):.2f} over
{cpu.get("curves", 0)} curves), and E0 sits at the {pct(cpu.get("e0_percentile_of_descendant_means", 50))} percentile of descendant means. The
all-curve test does flag differences between curves (Kruskal–Wallis p = {cpu.get("kruskal_by_curve", {}).get("p", float("nan")):.1g}), but the
drift-controlled comparison below shows that is machine drift, not the curve. Within one curve the cost varies a lot (median CV {cpu.get("within_curve_cv", 0):.2f}),
because it depends on the target, and in particular on whether the system has solutions.
In the census, Gröbner cost showed no dependence on which ECDLP instance generated the target (Kruskal–Wallis p = {c["gb_seconds_per_call"]["kruskal_by_instance"]["p"]:.2f}).</p>
</div>

{interleaveBlock(s)}

<h2>End-to-end ECDLP runs {"" if final else "(in progress)"}</h2>
<div class="prose">
<p>Each run collects |F| + 10 relations from targets αP + βQ, solves the relation matrix mod p, and checks the
recovered scalar. The same 10 scalars are used on every curve, so curve and instance effects can be separated.
Attempt counts are exact; CPU seconds carry the same machine drift as above, and E0's ten runs happened early under different load,
so compare curves on attempts. Runtime is attempts × per-decomposition cost, and the controlled test shows that cost does not depend on the curve.
{"" if final else "Tables and statistics below cover completed runs only; the full two-way analysis follows when all 310 solves finish."}</p>
</div>
{ecdlpStats(s) if final else ""}
<div class="tw"><table>
<thead><tr><th>curve</th><th>|F|</th><th>Pr[decomp]</th><th>predicted attempts</th><th>mean attempts</th><th>relations</th><th>median CPU s</th><th>logs correct</th></tr></thead>
<tbody>
{table}
</tbody></table></div>
<p class="cap">{correct}/{len(recs)} recovered logs verified. Runs with the same curve and scalar are seeded identically; six overlapping
duplicate runs reproduced the same attempt count and log exactly. Median CPU seconds are shown for scale only (see the drift note above).</p>

<h2>Caveats</h2>
<div class="prose">
<ul>
<li>This is an analogue. The mechanisms (tag-driven yield, curve-independent top-degree part) are structural and carry
over to F<sub>2</sub><sup>131</sup>, but the constants do not.</li>
<li>One factor-base choice (a polynomial-basis subspace, 2-point decompositions). E0's Frobenius endomorphism would allow a
τ-invariant factor base with n-fold fewer unknowns; descendants have no such endomorphism. That is the one
structural advantage E0 has, and it is not exercised here.</li>
<li>The machine was heavily loaded during all runs. Attempt counts and yields are exact and load-independent; comparisons
of cost use CPU time only.</li>
</ul>
</div>

<h2>Reproduce</h2>
<div class="prose">
<p><code>experiments/volcano-ic/</code> on PR #66 in aburan28/cryptanalysis: <code>sage run.sage census|gbcpu|ecdlp …</code>,
then <code>sage -python analyze.py</code> and <code>sage -python build_report.py</code>.</p>
</div>
</div>
'''
    os.makedirs(os.path.join(HERE, 'report'), exist_ok=True)
    with open(os.path.join(HERE, 'report', 'index.html'), 'w') as fh:
        fh.write(page)
    print('wrote report/index.html', len(page) // 1024, 'KB')


if __name__ == '__main__':
    main()
