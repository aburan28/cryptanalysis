"""Render report/index.html from results/summary.json and the raw records.

    sage -python analyze.py && sage -python build_report.py
"""
import base64
import collections
import glob
import html
import json
import os
import re
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
    cm = s.get('cost_model')
    model = (f''' A curve's solvable share is its decomposition probability, so the expected cost per decomposition is
{un:.0f} + {sv - un:.0f}·Pr ms. That ranges from {cm["per_call_ms_range"][0]:.0f} to {cm["per_call_ms_range"][1]:.0f} ms
({cm["per_call_spread_pct"]:.1f}%) across the 457 curves, too little for this test to resolve.''' if cm else '')
    return f'''<h3>Drift-controlled comparison</h3>
<div class="prose">
<p>CPU time on this machine still drifts, because under heavy load macOS moves work between performance and
efficiency cores. Across all 457 curves, measured one after another, that drift produces an apparent curve effect
(Kruskal–Wallis p = {s["census"]["gb_cpu_seconds_per_call"]["kruskal_by_curve"]["p"]:.1g}). To separate curve from time, E0 and nine descendants
(the six attempt extremes and three orbit representatives) were solved round-robin in one process, in a freshly shuffled order each
round, for {il["rounds"]} rounds. Each round is a block, so drift cancels.</p>
<p><b>No curve effect is detectable</b> (Friedman χ² = {il["friedman_curve"]["chi2"]:.1f}, p = {il["friedman_curve"]["p"]:.2f}).
Differences of a few percent are below this test's resolution: one curve's mean over {il["rounds"]} rounds has a standard error of
{il["curve_mean_se_pct"]:.1f}% (within-curve CV {il["within_curve_cv"]:.2f}). E0 costs
{il["e0_over_descendant_mean_ratio"]:.2f}× the descendant mean per decomposition (Wilcoxon p = {il["e0_vs_descendant_mean_wilcoxon_p"]:.2f}).
What moves the cost is whether the system has solutions: solvable systems take {sv:.0f} ms and unsolvable ones {un:.0f} ms.{model}</p>
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
    la = ev['linalg']
    return f'''<div class="key">
<div><b>{ev["correct_logs"][0]}/{ev["correct_logs"][1]}</b><span>discrete logs recovered and verified</span></div>
<div><b>{pm["mean_ratio_measured_over_predicted"]:.3f}</b><span>measured / census-predicted attempts (curve means correlate r = {pm["pearson_r_curve_means"]:.2f};
residual χ² = {pm["residual_chi2"]:.1f} on {pm["residual_df"]} df, p = {pm["residual_p"]:.2f})</span></div>
<div><b>{g["ratio_e0_over_desc"]:.3f}×</b><span>E0 attempts relative to descendants, 95% CI {g["ratio_ci95"][0]:.3f}–{g["ratio_ci95"][1]:.3f} (Mann–Whitney p = {g["mannwhitney_p"]:.2f});
the census predicts {pm["census_predicted_e0_over_desc"]:.3f}×</span></div>
<div><b>p = {an["gb_calls"]["instance"]["p"]:.2f}</b><span>scalar (instance) effect on attempts, null by construction: a target αP + βQ is uniform whatever the scalar</span></div>
</div>
<div class="figure">{img("ecdlp.png")}</div>
<p class="cap">A: attempts per ECDLP for every Tier B curve; black ticks mark the census prediction (|F| + 10) / Pr[decomp].
B: curve means against prediction. C: the same 10 scalars across all 31 curves.</p>
<h3>Curve × instance analysis</h3>
<div class="prose"><p>Additive two-way ANOVA on log values, 31 curves × 10 shared scalars, one run per cell. Attempts are the
load-independent measure of work. They carry a small curve effect that the census predicts from the factor base: after subtracting
the prediction, curve means scatter exactly as negative-binomial sampling noise would (χ² = {pm["residual_chi2"]:.1f} on {pm["residual_df"]} df,
p = {pm["residual_p"]:.2f}), and r = {pm["pearson_r_curve_means"]:.2f} is what that noise allows ({pm["expected_r_if_census_exact"]:.2f} expected for
an exact prediction). There is no instance effect, as expected.</p>
<p>The timing rows mix in two confounds. Each curve's ten runs happened in their own time slot, so "curve" includes
machine load. For {100 * ev["instance_is_worker_process_fraction"]:.0f}% of runs, instance k ran in worker process k, so "instance" includes
which cores that process got. That explains the instance effect in CPU seconds (p = {an["total_cpu_s"]["instance"]["p"]:.1g}), which attempts do
not show. Linear algebra takes {la["curve_mean_s_range"][0]:.2f}–{la["curve_mean_s_range"][1]:.2f} s per ECDLP, {100 * la["median_share_of_total_cpu"]:.1f}% of CPU time.
Its curve effect is mostly the time slot: a log–log fit against |F| gives slope {la["loglog_slope_vs_fb_size"]:.1f} but is not
significant (p = {la["loglog_p"]:.2f}). E0 ran during the heaviest-load hour and so looks {100 * (t["ratio_e0_over_desc"] - 1):.0f}% slower
in CPU seconds, while its attempt count is {100 * (g["ratio_e0_over_desc"] - 1):+.1f}% and the interleaved test shows no per-solve difference.</p></div>
<div class="tw"><table>
<thead><tr><th>measure (log)</th><th>curve F</th><th>curve p</th><th>curve η²</th><th>instance F</th><th>instance p</th><th>instance η²</th></tr></thead>
<tbody>{"".join(body)}</tbody></table></div>'''


def tauBullet(s):
    t = s.get('tau', {}).get('variants')
    if not t or 'tau6' not in t:
        return ''
    best = min((v for v in t if v != 'base'), key=lambda v: t[v]['total_cpu_s_mean'])
    b = t[best]
    return (f'<li><b>E0\'s real advantage is Frobenius, and it is large.</b> A τ-invariant factor base cuts the unknowns from '
            f'{t["base"]["unknowns"]} to {b["unknowns"]} and makes E0\'s ECDLP {b["speedup_vs_base_mean"]:.1f}× cheaper '
            f'(95% CI {b["speedup_ci95"][0]:.1f}–{b["speedup_ci95"][1]:.1f}×). No descendant can do this, because none has the endomorphism.</li>')


def satSummary(v):
    n = v.get('nb3sat')
    if not n:
        return ''
    return (f'<p>The textbook weight-≤ 3 base behaves differently. Nearly every target decomposes ({n["relations_mean"]:.0f} relations from '
            f'{n["targets_mean"]:.0f} targets), and the first SAT model was always a valid relation. But each call costs about '
            f'{n["gb_ms_per_call"] / 1000:.0f} CPU s against milliseconds for the small Gröbner systems. End to end it runs at '
            f'{n["speedup_vs_base_mean"]:.2f}× the baseline\'s speed, so the orbit-closure bases are about '
            f'{n["total_cpu_s_mean"] / v["tau6"]["total_cpu_s_mean"]:.0f}× cheaper than it. Fewer unknowns only pay off if each decomposition stays cheap.</p>'
            '<p class="cap">Timing windows: the τ runs and 4 baseline runs shared one window; the other 6 baseline runs and the SAT runs ran later, '
            'after the external drive dropped out and came back. All runs are CPU-timed on the same machine, but these ratios carry the drift caveat above.</p>')


def satNote(s):
    v = s.get('tau', {}).get('variants', {}).get('nb3sat')
    if not v:
        return ''
    return f', which dominates the cost: {v["correct"][1]} runs averaged {v["gb_calls_mean"]:.0f} SAT calls at {v["gb_ms_per_call"] / 1000:.1f} s each'


def tauBlock(s):
    t = s.get('tau')
    if not t or 'variants' not in t:
        return ''
    v = t['variants']
    rowsHtml = []
    label = {'base': 'baseline: x in V, dim 10 (Gröbner)', 'tau6': "τ-invariant: orbits of x in V′, dim 6 (Gröbner)",
             'tau7': "τ-invariant: orbits of x in V′, dim 7 (Gröbner)", 'nb3sat': 'τ-invariant: normal-basis weight ≤ 3 (SAT)'}
    for k in ('base', 'tau6', 'tau7', 'nb3sat'):
        if k not in v:
            continue
        e = v[k]
        sp = f'{e["speedup_vs_base_mean"]:.2f}× ({e["speedup_ci95"][0]:.2f}–{e["speedup_ci95"][1]:.2f})' if k != 'base' else '1×'
        rowsHtml.append(f'<tr class="{"" if k == "base" else "e0"}"><th scope="row">{label[k]}</th><td>{e["unknowns"]}</td>'
                        f'<td>{e["relations_mean"]:.0f}</td><td>{e["gb_calls_mean"]:,.0f}</td><td>{e["gb_ms_per_call"]:.1f}</td>'
                        f'<td>{e["total_cpu_s_mean"]:.0f}</td><td>{sp}</td><td>{e["correct"][0]}/{e["correct"][1]}</td></tr>')
    b6 = v.get('tau6', {})
    return f'''<h2>E0 with a τ-invariant factor base</h2>
<div class="prose">
<p>E0 is the only curve in the class with the Frobenius endomorphism τ(x, y) = (x², y²). On the prime subgroup τ acts as
multiplication by λ, a root of λ² + λ + 2 mod p, so a factor base closed under τ needs one unknown per Frobenius orbit:
log τ<sup>e</sup>P = λ<sup>e</sup> log P.</p>
<p><b>The textbook choice fails for Gröbner bases.</b> Over F<sub>2</sub><sup>19</sup> no subspace of useful size is closed
under squaring: 2 is a primitive root mod 19, so the only ones are 0, F<sub>2</sub>, the trace-zero hyperplane and the whole field.
The usual τ-invariant base is therefore x of Hamming weight ≤ 3 in a normal basis:
665 points in 35 orbits. Its decomposition system has 38 variables plus 7,752 degree-4 weight constraints, and not one
PolyBoRi solve finished within 15 minutes. That matches Galbraith–Gebregiyorgis, who moved to SAT solvers for this shape.</p>
<p><b>SAT handles it.</b> The same 19 descended equations go to CryptoMiniSat as XOR clauses, with one auxiliary variable per
product c<sub>i</sub>d<sub>j</sub> and sequential-counter cardinality constraints for the weight bound. The search stops at the first model that
lifts to a real relation. Targets with a decomposition take seconds; a target without one needs a full UNSAT proof{satNote(s)}.</p>
<p><b>What works:</b> the Frobenius-orbit closure of a small polynomial subspace, F = {{τ<sup>j</sup>P : x(P) ∈ V′}}. Squaring is
F<sub>2</sub>-linear, so decomposing R = P<sub>1</sub> ± τ<sup>j</sup>P<sub>2</sub> with P<sub>1</sub>, P<sub>2</sub> ∈ V′ is still a quadratic
system, now in only 2k′ variables. Each target is tried against the 19 shifts j until one yields a relation. The same 10 scalars
were run under each factor base, with the baseline re-run in the same time window so CPU times are comparable.</p>
</div>
<div class="tw"><table>
<thead><tr><th>E0 factor base</th><th>unknowns</th><th>relations</th><th>solver calls</th><th>ms per call</th><th>CPU s per ECDLP</th><th>speedup (95% CI)</th><th>logs correct</th></tr></thead>
<tbody>{"".join(rowsHtml)}</tbody></table></div>
<div class="figure">{img("tau.png")}</div>
<p class="cap">Speedup is the mean of per-scalar ratios (baseline CPU / τ CPU), paired by scalar, with a bootstrap 95% interval.
Each τ solve has 2k′ ≤ 14 variables, against 20 for the baseline.</p>
<div class="prose">
<p>The trade is many more, much cheaper decompositions for far fewer relations. The τ-invariant runs need only about
{b6.get("relations_mean", 0):.0f} relations instead of ~{v["base"]["relations_mean"]:.0f}. Each solve is small, but most shifts fail, so
the solve count goes up. The net is a clear end-to-end win that only E0 can claim. For ECC2K-130 this is the analogue of the known √(2·131) Frobenius
speedup for Pollard rho: the endomorphism, not the position in the volcano, is what separates the crater curve from its descendants.</p>
{satSummary(v)}
</div>'''


def runtimeModel(cm, e0AttemptsPct):
    if not cm:
        return ''
    g = cm['gb_cpu_s_per_dlp']
    return (f'Runtime is not attempts times a fixed cost, though. Each relation needs one solvable system ({1000 * cm["solvable_s"]:.0f} ms), '
            f'and each failed attempt costs an unsolvable one ({1000 * cm["unsolvable_s"]:.0f} ms). The modelled Gröbner CPU per ECDLP, '
            f'(|F| + 10)·(c<sub>s</sub> + c<sub>u</sub>(1/Pr − 1)), spans {g["range"][0]:.0f}–{g["range"][1]:.0f} s across the 457 curves '
            f'(±{g["halfwidth_pct"]:.1f}%). Its order is the reverse of the attempt order: its correlation with |F| is {g["corr_with_fb_size"]:+.2f}, '
            f'against {cm["corr_attempts_with_fb_size"]:+.2f} for attempts. So E0 sits at the {pct(g["e0_percentile"])} percentile in modelled time '
            f'but the {pct(e0AttemptsPct)} in attempts. Either way, the curve moves the work by a couple of percent.')


def crosscheckBlock(s):
    cc = s.get('crosscheck')
    if not cc:
        return ''
    cen, sub, tz, s3 = cc['census'], cc['subspaces'], cc['trace_zero'], cc['s3']
    cm = s.get('cost_model', {})
    ca = s.get('crosscheck_algebra', {})
    curves = [sub[k] for k in ('E0', 'lowest_yield', 'median_fb_size')]
    tzSaving = 100 * (1 - tz['attempts_mean'] / tz['attempts_mean_on_V'])
    time = (f' Solvable systems cost more, so under the cost model above modelled Gröbner time falls by less, about '
            f'{cm["trace_zero_saving_pct"]:.0f}%.' if 'trace_zero_saving_pct' in cm else '')
    pb = ca.get('s3_solutions_polybori')
    polybori = ''
    if pb:
        built = sum(r['x_is_zero'] for r in pb['built_targets'])
        polybori = (f' On the real PolyBoRi pipeline, {pb["random_targets"]} random E0 targets gave {pb["random"]["genuine"]} genuine solutions, '
                    f'{pb["random"]["x_is_zero"]} with x = 0 and {pb["random"]["other"]} of any other kind. {len(pb["built_targets"])} targets '
                    f'R = P + T<sub>2</sub>, built to have x = 0 solutions, gave {built} of them and '
                    f'{sum(r["other"] for r in pb["built_targets"])} of any other kind.')
    return f'''<h2>Independent cross-check</h2>
<div class="key">
<div><b>{cen["exact_matches"]}/{cen["curves_compared"]}</b><span>census records reproduced exactly by an implementation that shares no code with ic.sage</span></div>
<div><b>{min(c["attempts_mean"] for c in curves):.0f}–{max(c["attempts_mean"] for c in curves):.0f}</b><span>mean predicted attempts for E0, {sub["lowest_yield"]["curve"]} and {sub["median_fb_size"]["curve"]} over {sub["E0"]["draws"]} random subspaces each</span></div>
<div><b>−{tzSaving:.0f}%</b><span>predicted attempts on every curve with a trace-zero factor-base subspace ({tz["attempts_mean_on_V"]:.0f} → {tz["attempts_mean"]:.0f})</span></div>
<div><b>{s3["solutions"]["twist"]}</b><span>twist solutions among {s3["targets"]:,} E0 decomposition systems</span></div>
</div>
<div class="prose">
<p><code>crosscheck.py</code> redoes Tier A in numpy: log tables for F<sub>2</sub><sup>19</sup>, Z/4 tags from the halving criterion,
and no Sage. One FFT over all b recovers the same {cen["isogeny_class_size"]}-curve class. Every curve's |F|, tag counts, eligible
pairs and distinct targets match the census exactly.</p>
<p><b>The curve is not the variable; the subspace is.</b> Each curve was measured on one subspace, V. Given {sub["E0"]["draws"]} random
subspaces g·V each, E0, the lowest-yield descendant {sub["lowest_yield"]["curve"]} and the median descendant {sub["median_fb_size"]["curve"]} average
{curves[0]["attempts_mean"]:.1f}, {curves[1]["attempts_mean"]:.1f} and {curves[2]["attempts_mean"]:.1f} predicted attempts (sd ≈ {curves[0]["attempts_sd"]:.0f}),
against {sub["descendants_on_V"]["attempts_mean"]:.1f} for all descendants on V. {sub["lowest_yield"]["curve"]}'s |F| = {sub["lowest_yield"]["fb_size_on_V"]} on V is the
smallest of its own {sub["lowest_yield"]["draws"]} draws, and E0's {sub["E0"]["fb_size_on_V"]} sits at the {pct(sub["E0"]["fb_size_on_V_percentile"])} percentile of E0's draws.
So the spread between curves on V is the luck of the draw of V.</p>
<p><b>A better subspace helps every curve alike.</b> One of E0's draws landed inside the trace-zero hyperplane (predicted attempts
{sub["E0"]["trace_zero_draws_attempts"][0] if sub["E0"]["trace_zero_draws_attempts"] else float("nan"):.0f}; such draws are left out of the averages above). With a = 0 a point lies in 2E exactly
when Tr(x) = 0, so on such a subspace every factor-base point has an even tag. Odd pairs, which give one prime-subgroup
combination instead of two, disappear, and the eligible count roughly doubles. The condition is linear: {tz["solutions_g"]} multipliers
g put g·V inside ker Tr. With the smallest, g = {tz["g"]}, {"no curve among the 457 has an odd tag" if tz["odd_tags_total"] == 0 else f'{tz["odd_tags_total"]} odd tags remain'}.
Predicted attempts fall from {tz["attempts_mean_on_V"]:.0f} to {tz["attempts_mean"]:.0f} on average (range {tz["attempts_range"][0]:.0f}–{tz["attempts_range"][1]:.0f}),
and E0 needs {tz["e0_attempts"]:.0f}.{time} This is a census-level prediction; it has not been run end to end.</p>
<p><b>Decomposition systems.</b> Solving S<sub>3</sub> over V × V directly for {s3["targets"]:,} random E0 targets, {100 * s3["solvable_share"]:.1f}% ± {100 * s3["solvable_share_se"]:.1f}%
of systems have a genuine solution, against the exact {100 * s3["exact_decomp_prob"]:.2f}%. {100 * s3["x_is_zero_per_system"]:.2f}% have x = 0 solutions
(theory {100 * s3["x_is_zero_per_system_theory"]:.2f}%), and none has a twist solution.{polybori}</p>
<p><code>crosscheck.sage</code> recomputes the conductors in the comparison table, the Frobenius-stable subspaces behind the τ section,
where b sits in S<sub>3</sub> and S<sub>4</sub>, and the degree-of-regularity controls.</p>
</div>'''


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
    dregText = (f'{next(iter(c["dreg"]["values"]))} on all {sum(c["dreg"]["values"].values())} sampled systems'
                if len(c['dreg']['values']) == 1 else f'{dregVals} (value, count) across the sampled systems')
    op, bias = c['operating_point'], c['saturation_model_bias']
    cc, ca, cm = s.get('crosscheck', {}), s.get('crosscheck_algebra', {}), s.get('cost_model', {})
    pmv = ev.get('predicted_vs_measured_attempts', {})
    ctl = ca.get('dreg_controls')
    dregControl = (f'Random bilinear systems of the same shape give {", ".join(sorted({str(v) for v in ctl["random_bilinear"]}))}, '
                   f'and random quadratic systems give {", ".join(sorted({str(v) for v in ctl["random_quadratic"]}))}. ' if ctl else '')
    s4 = ca.get('weil_descent_bit_degrees', {}).get('S4')
    # Sage prints e.g. 'xR * x3^3 * x2^3 * x1^3'; render the variables and powers.
    poly = lambda p: re.sub(r'\^(\d+)', r'<sup>\1</sup>',
                            re.sub(r'x(R|\d)', r'x<sub>\1</sub>', html.escape(p))).replace(' * ', '·')
    s4Sentence = (f' The b-independence carries over to three-point decompositions: after Weil descent the top part of S<sub>4</sub> is '
                  f'{poly(s4["top_part"])}, and b appears only at bit-degree {max(s4["bit_degrees_with_b"])} and below.' if s4 else '')
    sub = cc.get('subspaces')
    subSentence = (f' Given {sub["E0"]["draws"]} random subspaces each, E0 and two descendants all average '
                   f'{min(sub[k]["attempts_mean"] for k in ("E0", "lowest_yield", "median_fb_size")):.0f}–'
                   f'{max(sub[k]["attempts_mean"] for k in ("E0", "lowest_yield", "median_fb_size")):.0f} predicted attempts, so a curve\'s '
                   f'rank on V is the luck of that one subspace.' if sub else '')
    tz = cc.get('trace_zero')
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
<p class="lede">A scaled copy of the reachable part of ECC2K-130's isogeny volcano, small enough that complete index
calculus finishes: the Koblitz crater curve <span class="crater">E0</span> over F<sub>2</sub><sup>19</sup> and every one of its
<span class="floor">456 floor descendants</span>, measured on relation yield, point decomposition, Gröbner
systems, and end-to-end ECDLP runtime over 10 fixed scalars.{" An independent reimplementation reproduces every census record." if cc else ""}</p>

<div class="answer">
<div class="eyebrow">Short answer{"" if final else " so far"}</div>
<ul>
<li><b>Relation yield differs between curves, but only through the factor base.</b> Three counts fix the eligible pairs:
how many factor-base points carry each Z/4 torsion tag. Yield then follows a birthday curve in that count, to within
{c["saturation_model_max_abs_error"]:.4f}. With this shared factor base, nothing about the endomorphism ring enters.{subSentence}</li>
<li><b>Those differences nearly cancel in total work.</b> Descendants range {dr["exact_decomp_prob"][0]:.3f}–{dr["exact_decomp_prob"][2]:.3f} in
decomposition probability, but a bigger factor base also needs more relations, so predicted attempts per ECDLP span only
{dr["expected_attempts_per_dlp"][0]:.0f}–{dr["expected_attempts_per_dlp"][2]:.0f} (±{100 * (dr["expected_attempts_per_dlp"][2] - dr["expected_attempts_per_dlp"][0]) / 2 / dr["expected_attempts_per_dlp"][1]:.1f}%). E0 needs {e0["expected_attempts_per_dlp"]:.0f}.
The factor base sits near its attempts-optimal size, where first-order changes cancel.{f" In modelled Gröbner CPU time the spread is ±{cm['gb_cpu_s_per_dlp']['halfwidth_pct']:.1f}% and the order reverses, because solvable systems cost more." if cm else ""}</li>
<li><b>The formal degree of regularity cannot tell curves apart.</b> It is {dregText}. The quadratic part of
every system is bilinear in the x<sub>1</sub> and x<sub>2</sub> bits, which forces the value to be at least dim V + 1 = 11 for any curve and any target.
{dregControl}The curve coefficient enters only as a constant term.</li>
<li><b>End-to-end ECDLP:</b> {correct}/{len(recs)} logs recovered and verified across {nCurvesB} curves × 10 scalars. Work per ECDLP depends
weakly on the curve, exactly as the census predicts: after subtracting the prediction, curve means scatter as sampling noise would
(χ² = {pmv.get("residual_chi2", float("nan")):.1f} on {pmv.get("residual_df", 0)} df, p = {pmv.get("residual_p", float("nan")):.2f}). It does not depend on the scalar (p = {an["gb_calls"]["instance"]["p"]:.2f}).
E0 needs {e0v["gb_calls"]["ratio_e0_over_desc"]:.3f}× the descendants' attempts (95% CI {e0v["gb_calls"]["ratio_ci95"][0]:.3f}–{e0v["gb_calls"]["ratio_ci95"][1]:.3f}),
against a census prediction of {pmv.get("census_predicted_e0_over_desc", float("nan")):.3f}×.</li>
{f"""<li><b>The factor base matters far more than the curve.</b> A subspace inside the trace-zero hyperplane makes every factor-base
point halvable, which roughly doubles the eligible pairs. On all 457 curves it cuts predicted attempts from {tz["attempts_mean_on_V"]:.0f}
to {tz["attempts_mean"]:.0f} on average ({100 * (1 - tz["attempts_mean"] / tz["attempts_mean_on_V"]):.0f}% fewer), against ±{100 * (dr["expected_attempts_per_dlp"][2] - dr["expected_attempts_per_dlp"][0]) / 2 / dr["expected_attempts_per_dlp"][1]:.1f}% between curves.</li>""" if tz else ""}
<li><b>Bottom line:</b> descending the volcano changes nothing structural for this attack. Curve-to-curve differences are
factor-base counting, a few percent at most, and they partly cancel.</li>
{tauBullet(s)}
</ul>
</div>

<h2>Why a scaled analogue</h2>
<div class="prose">
<p>On ECC2K-130 itself, a natural relation at any feasible factor-base size has probability around 2<sup>−120</sup>;
earlier runs found zero relations on public targets, so no index-calculus runtime exists to compare. The
n = 19 curve reproduces the part of ECC2K-130's volcano that can be reached from E0, and is small enough to solve.</p>
</div>
<div class="tw"><table>
<thead><tr><th></th><th>ECC2K-130</th><th>n = 19 analogue</th></tr></thead>
<tbody>
<tr><th scope="row">curve</th><td>y² + xy = x³ + 1 over F<sub>2</sub><sup>131</sup></td><td>y² + xy = x³ + 1 over F<sub>2</sub><sup>19</sup></td></tr>
<tr><th scope="row">cofactor · prime</th><td>4 · N (129-bit)</td><td>4 · 130 873</td></tr>
<tr><th scope="row">End(E0)</th><td>ℤ[τ], disc −7</td><td>ℤ[τ], disc −7</td></tr>
<tr><th scope="row">Frobenius conductor [O<sub>K</sub> : ℤ[π]]</th><td>263 · 146 505 763 881 528 721</td><td>457</td></tr>
<tr><th scope="row">volcano prime modelled</th><td>263, split in ℚ(√−7)</td><td>457, split in ℚ(√−7)</td></tr>
<tr><th scope="row">descendants one isogeny below E0</th><td>262 (2 Frobenius orbits)</td><td>456 (24 Frobenius orbits of 19)</td></tr>
<tr><th scope="row">whole isogeny class</th><td>263 · (P + 2) ≈ 2<sup>65.1</sup> curves</td><td>457 curves</td></tr>
</tbody></table></div>
<p class="cap">The 457-curve isogeny class was found by exhaustive point counting over all 2<sup>19</sup> values of b and matches
the class-number count 1 + (457 − 1) exactly. ECC2K-130's conductor has a second prime factor, P = 146 505 763 881 528 721
(57 bits, inert in ℚ(√−7)). Any isogeny that changes the P-part of the endomorphism ring has degree divisible by P. So from E0 only the
262 curves one 263-isogeny below it are reachable, and the other ≈ 2<sup>65</sup> curves in the class are not. The analogue's conductor, 457,
is prime, so there the reachable part is the whole class. <code>crosscheck.sage</code> recomputes the orders, conductors and
class sizes in this table.</p>

<h2>Method</h2>
<div class="prose">
<p><b>Field.</b> F<sub>2</sub><sup>19</sup> = F<sub>2</sub>[z]/(z<sup>19</sup> + z<sup>18</sup> + z<sup>16</sup> + z<sup>11</sup> + z<sup>8</sup> + z<sup>6</sup> + z<sup>4</sup> + z + 1),
PARI's default for F<sub>2</sub><sup>19</sup> (<code>MODULUS</code> in <code>run.sage</code>). V, and so every factor base below, depends on
this choice. With Sage's default Conway modulus, E0 has |F| = 502 instead of 494.</p>
<p><b>Factor base.</b> Points with x in V = span{{1, z, …, z<sup>9</sup>}}, up to sign: the same polynomial coordinate
subspace for every curve. <b>Decomposition.</b> Each target R = αP + βQ is split as ±P<sub>1</sub> ± P<sub>2</sub> through the
summation polynomial S<sub>3</sub>(x<sub>1</sub>, x<sub>2</sub>, x<sub>R</sub>) = (x<sub>1</sub>x<sub>2</sub>)² + x<sub>R</sub>²(x<sub>1</sub>² + x<sub>2</sub>²) + x<sub>R</sub>x<sub>1</sub>x<sub>2</sub> + b,
Weil-descended to 19 quadratic Boolean equations in 20 unknowns and solved with a PolyBoRi Gröbner basis.
<b>Linear algebra.</b> Relations on the cofactor-cleared factor base mod p; the log of Q comes from a left-kernel
vector and is checked against the known scalar.</p>
<p><b>Tier A</b> covers all 457 curves: exact yield by enumerating every factor-base pair, formal degree of regularity,
and Gröbner samples drawn from each of the 10 ECDLP instances. <b>Tier B</b> runs full index calculus with the same
10 scalars on E0, one seeded descendant per Frobenius orbit, and the three descendants with the fewest and the three with the most
predicted attempts per ECDLP. These are not the yield extremes: the highest-yield descendant, {c["highest_yield_descendant"]["curve"]}
(|F| = {c["highest_yield_descendant"]["fb_size"]}, Pr = {c["highest_yield_descendant"]["exact_decomp_prob"]:.4f}), ranks {pct(c["highest_yield_descendant"]["attempts_rank"])} by predicted attempts and is not in Tier B.</p>
</div>

<h2>Relation yield</h2>
<div class="key">
<div><b>{c["eligible_formula_matches"][0]}/{c["eligible_formula_matches"][1]}</b><span>curves where eligible pairs equal the Z/4 tag formula (a counting identity, so this checks the code)</span></div>
<div><b>{c["saturation_model_max_abs_error"]:.4f}</b><span>largest gap between exact yield and the birthday model, which runs {bias["mean_exact_minus_model"]:.4f} low on average</span></div>
<div><b>{e0["fb_size"]}</b><span>E0 factor-base size, {pct(pc["fb_size"])} percentile of descendants ({dr["fb_size"][0]}–{dr["fb_size"][2]})</span></div>
<div><b>{e0["expected_attempts_per_dlp"]:.0f}</b><span>E0 predicted attempts per ECDLP, {pct(pc["expected_attempts_per_dlp"])} percentile</span></div>
</div>
<div class="prose">
<p>E(F<sub>2</sub><sup>19</sup>) ≅ ℤ/4 × ℤ/p on every curve, so each factor-base point carries a torsion tag in ℤ/4. A sum or
difference lands in the prime subgroup only when the tags cancel. With n<sub>0</sub>, n<sub>2</sub>, n<sub>odd</sub> the tag counts:</p>
<p class="formula">eligible = 2·C(n₀,2) + n₀ + 2·C(n₂,2) + n₂ + C(n_odd,2)&nbsp;&nbsp;&nbsp;Pr[decomp] ≈ 1 − exp(−eligible / ((p−1)/2))</p>
<p>E0 has (n₀, n₂, n_odd) = ({e0["tag_counts"][0]}, {e0["tag_counts"][2]}, {e0["tag_counts"][1] + e0["tag_counts"][3]}), giving {e0["eligible_signed_pairs"]:,} eligible pairs.
From that count the birthday formula predicts Pr = {c["e0_saturation_prob"]:.4f}. Enumerating every pair gives the exact Pr = {e0["exact_decomp_prob"]:.4f}.
The formula runs slightly low: exact minus formula averages {bias["mean_exact_minus_model"]:+.4f} and is positive on {100 * bias["fraction_exact_above_model"]:.0f}% of
curves, because sums of distinct factor-base points collide less often than independent random targets would.
Every curve sits on the same birthday curve (panel B). Descendants reach
more targets only by having more rational points in V, and factor-base size is not explained by Frobenius orbit
(Kruskal–Wallis p = {c["fb_size_by_orbit_kruskal"]["p"]:.2f}).</p>
<p>A larger factor base raises the yield but also raises the number of relations needed, which is why
predicted attempts per ECDLP fall only from {dr["expected_attempts_per_dlp"][2]:.0f} to {dr["expected_attempts_per_dlp"][0]:.0f} as
factor-base size rises from {dr["fb_size"][0]} to {dr["fb_size"][2]} (r = {c["corr_fb_size_vs_expected_attempts"]:.2f}, panel C). The flatness comes
from where this operating point sits. With λ = eligible / ((p−1)/2), attempts scale as √λ / (1 − e<sup>−λ</sup>), which is smallest at
λ = {op["lambda_attempts_optimum"]:.3f}. Every curve sits at λ = {op["lambda_range"][0]:.2f}–{op["lambda_range"][1]:.2f}. There a 10% larger factor base saves only
about {-10 * op["e0_attempts_elasticity_in_fb_size"]:.0f}% of attempts (elasticity {op["e0_attempts_elasticity_in_fb_size"]:.2f} at E0), and E0 is
{100 * (op["e0_attempts_over_optimum"] - 1):.1f}% above the optimum.</p>
</div>
<div class="figure">{img("census.png")}</div>
<p class="cap">Tier A over all 457 curves. D uses CPU time from a separate re-measurement
({cpu.get("curves", 0)} of 457 curves). The census wall-clock Gröbner timings drift with machine load in processing
order and are not used for between-curve comparison.</p>

<h2>Point decomposition and Gröbner bases</h2>
<div class="key">
<div><b>{hit["hits"]:,} / {hit["calls"]:,}</b><span>Gröbner decompositions that produced a relation; {hit["expected_hits"]:,.0f} expected from exact yield (z = {hit["z"]:.2f})</span></div>
<div><b>{hit["spurious_solutions"]}</b><span>spurious S₃ solutions rejected at lift time ({100 * hit["spurious_solutions"] / hit["calls"]:.2f}% of solves), all at x = 0</span></div>
<div><b>{dregVals.split(" ")[0]}</b><span>formal degree of regularity on all {sum(c["dreg"]["values"].values())} sampled systems: the minimum this variable split allows</span></div>
<div><b>{1000 * cpu.get("median_s", 0):.0f} ms</b><span>median Gröbner CPU time per decomposition</span></div>
</div>
<div class="prose">
<p>The Gröbner solver finds exactly the relations the exact yield predicts: the pooled hit rate differs from
expectation by {abs(hit["z"]):.1f} standard deviations. The spurious solutions all have one coordinate equal to 0, the
x-coordinate of the 2-torsion point, which the factor base leaves out. A non-degenerate solution with both coordinates in V
always lifts: if x₁ were a twist x-coordinate, the two roots x₂ would be Galois conjugates and so not in F<sub>2</sub><sup>19</sup>.
A target has x = 0 solutions with probability 2·1023 / (2<sup>19</sup> − 1) = 0.39%, about {2 * 1023 / (2 ** 19 - 1) * hit["calls"]:.0f} solutions in
{hit["calls"]:,} solves. The lift step counts them only until it finds a genuine relation, hence {hit["spurious_solutions"]}.</p>
<p>The degree of regularity cannot differ between curves in this
formulation: squaring is linear over F<sub>2</sub>, so the quadratic part of every equation comes from
(x₁x₂)² + x<sub>R</sub>x₁x₂ and depends on the target alone. b only shifts constants. It cannot tell targets apart either.
That quadratic part is bilinear in the bits of x₁ and x₂, so no combination of the equations ever produces a monomial in the
x₁ bits alone, or in the x₂ bits alone. Those monomials survive up to degree dim V = 10, which forces a formal degree of
regularity of at least 11 for every system of this shape. {dregControl}The number records dim V. The degree a solver actually
reaches would be the informative measurement.{s4Sentence}</p>
<p>Per-decomposition CPU cost rises weakly with factor-base size (Spearman ρ = {cpu.get("spearman_mean_vs_fb_size", float("nan")):.2f} over
{cpu.get("curves", 0)} curves, p = {cpu.get("spearman_mean_vs_fb_size_p", float("nan")):.2f}). That is what the solvable-share effect below predicts. E0 sits at the
{pct(cpu.get("e0_percentile_of_descendant_means", 50))} percentile of descendant means. The all-curve test also flags differences between curves
(Kruskal–Wallis p = {cpu.get("kruskal_by_curve", {}).get("p", float("nan")):.1g}), and the drift-controlled comparison below shows most of
that is machine drift. Within one curve the cost varies a lot (median CV {cpu.get("within_curve_cv", 0):.2f}),
because it depends on the target, and in particular on whether the system has solutions.
In the census, Gröbner cost showed no dependence on which ECDLP instance generated the target (Kruskal–Wallis p = {c["gb_seconds_per_call"]["kruskal_by_instance"]["p"]:.2f}).</p>
</div>

{interleaveBlock(s)}

<h2>End-to-end ECDLP runs {"" if final else "(in progress)"}</h2>
<div class="prose">
<p>Each run collects |F| + 10 relations from targets αP + βQ, solves the relation matrix mod p, and checks the
recovered scalar. The same 10 scalars are used on every curve, so curve and instance effects can be separated.
Attempt counts are exact; CPU seconds carry the same machine drift as above, and E0's ten runs happened early under different load,
so compare curves on attempts. {runtimeModel(cm, pc["expected_attempts_per_dlp"])}
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

{tauBlock(s)}
{crosscheckBlock(s)}

<h2>Caveats</h2>
<div class="prose">
<ul>
<li>This is an analogue of the reachable part of ECC2K-130's volcano, the 263-level. The mechanisms carry over to
F<sub>2</sub><sup>131</sup>. Yield is tag-driven there too, since E(F<sub>2</sub><sup>131</sup>) is again ℤ/4 × ℤ/N. The top-degree part of the
systems is curve-independent for S<sub>3</sub>, and for S<sub>4</sub> as well. The constants do not carry over.
With 2-point decompositions a useful factor base has about √q points, so at 131 bits this method is no better than Pollard rho.
The all-curve study shows that position in the volcano does not change this decomposition machinery, and the τ section shows
what E0's endomorphism adds to it. Neither shows whether any index-calculus attack threatens ECC2K-130.</li>
<li>The all-curve comparison uses one factor-base choice (a polynomial-basis subspace, 2-point decompositions) so every
curve is treated alike. The τ-invariant runs are E0-only by construction: descendants have no Frobenius endomorphism.</li>
<li>The machine was heavily loaded during all runs. Attempt counts and yields are exact and load-independent; comparisons
of cost use CPU time only.</li>
</ul>
</div>

<h2>Reproduce</h2>
<div class="prose">
<p><code>experiments/volcano-ic/</code> in aburan28/cryptanalysis: <code>sage run.sage census|gbcpu|ecdlp …</code>,
then <code>python3 crosscheck.py</code>, <code>sage crosscheck.sage</code>, <code>sage -python analyze.py</code> and
<code>sage -python build_report.py</code>.</p>
</div>
</div>
'''
    os.makedirs(os.path.join(HERE, 'report'), exist_ok=True)
    with open(os.path.join(HERE, 'report', 'index.html'), 'w') as fh:
        fh.write(page)
    print('wrote report/index.html', len(page) // 1024, 'KB')


if __name__ == '__main__':
    main()
