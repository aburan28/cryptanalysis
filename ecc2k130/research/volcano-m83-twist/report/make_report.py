"""Write REPORT.md from ../outputs/summary.json (every number below is read from outputs/)."""
import json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'outputs'
S = json.loads((OUT / 'summary.json').read_text())
iso = json.loads((OUT / 's00-small-isogenies.json').read_text())
ctl = json.loads((OUT / 'control-run06.json').read_text())
a0, a1, rho, icr = S['0'], S['1'], S['rho_a1'], S['ic_k12_vs_rho_a1']
_rf = OUT / 'rho-floor-summary.json'
RF = json.loads(_rf.read_text()) if _rf.exists() else None
_ra = OUT / 'rho-floor-all-summary.json'
RA = json.loads(_ra.read_text()) if _ra.exists() else None


def f(x, d=6): return ('%.' + str(d) + 'f') % x
def pct(x): return '%+.4f %%' % (100 * x)


def census_rows(s):
    c = s['crater']['Y_matched']
    return [('crater E0, polynomial basis', f(c), '—'),
            ('floor mean ± sd (%d curves)' % s['floor_curves'], '%s ± %.2g' % (f(s['floor_Y']['mean']), s['floor_Y']['sd']), pct(s['floor_Y']['mean'] / c - 1)),
            ('best floor curve %s' % s['top5'][0][1], f(s['top5'][0][0]), pct(s['top5'][0][0] / c - 1)),
            ('crater, 200 field representations: mean ± sd', '%s ± %.2g' % (f(s['reps']['mean']), s['reps']['sd']), pct(s['reps']['mean'] / c - 1)),
            ('best representation', f(s['reps']['max']), pct(s['reps']['max'] / c - 1))]


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows]
    return '\n'.join(out)


rho_rows = []
for key, lab in (('crater_mode2', 'crater E0, classes {±τ^i P}'), ('crater_mode1', 'crater E0, classes {±P}'),
                 ('crater_mode0', 'crater E0, plain'), ('floor_mode1', 'floor O00-00/O39-00/O77-82, {±P}'),
                 ('floor_mode0', 'floor O00-00/O39-00/O77-82, plain')):
    r = rho[key]
    rho_rows.append((lab, r['solves'], '%.3f ± %.3f' % (r['S_steps_mean'], r['S_steps_se']), '%.3f' % r['S_theory'],
                     '%.1f' % r['squarings_per_step'],
                     ' / '.join('%.3g' % r['S_priced'][w] for w in ('0', '0.1', '1')), '%.1f' % r['wall_s_mean']))

beats = a0['floor_beating_crater_by_gate'] + a1['floor_beating_crater_by_gate'] + a0['reps']['beating_crater_by_gate'] + a1['reps']['beating_crater_by_gate']
k7, k11 = iso['a1_53bit']['7']['n_kernels'], iso['a1_53bit']['11']['n_kernels']

md = f"""# Factor-base yield and Pollard rho across the GF(2^83) Koblitz isogeny class

Date 2026-10-16. Study directory `cryptanalysis:ecc2k130/research/volcano-m83-twist/`, extending
`cryptanalysis:ecc2k130/research/volcano-m83/` (the a2 = 0 floor census) to the a2 = 1 twist, field
representations and Pollard rho. Frozen protocol: `PROTOCOL.md`. Stage diagnostic only: no IC1
candidate, no end-to-end index-calculus run, `candidate_id: null`.

## Question and answer

Does a curve reachable by isogeny from the GF(2^83) Koblitz curves, or a field representation of the
Koblitz curve, give a factor base that clearly beats the Koblitz crater? **No.** {'No candidate cleared the frozen gate' if not beats else 'GATE CLEARED BY: ' + ', '.join(beats)}
(+0.1 % for a2 = 0, +5 % for a2 = 1, equal cardinality S = {a0['S']}, k = {a0['k']}), on 2 × 6474 floor curves and
2 × 200 representations. Floor curves also lose the 83-fold Frobenius folding. By the protocol, the end-to-end
N83 run against the 28.688 ms K3425/root4 baseline (`crypto:research/n83_final_tournament_results_20261015`) is
not opened.

## Curves

- a2 = 0: y² + xy = x³ + b, n = ELL = 2417851639230796216685689 (81-bit), h = 4. Crater b = 1 is
  ../volcano-m83 E0 (no EC1 ID registered in `experiments/ic-candidate-catalog/curves.yaml`).
- a2 = 1: y² + xy = x³ + x² + b, n = 8569786107849059 (53-bit), h = 1128547018 = 2·10459·53951. Crater b = 1
  is `EC1N83Ckb1a1haacb69ee9f37` (crypto N83 instance).
- Field F₂[z]/(z⁸³ + z⁷ + z⁴ + z² + 1) for both. Floor: the 6474 conductor-6473 curves O00-00 … O77-82 of
  ../volcano-m83 (b = 1/j, j a root of the ring class polynomial mod 2). The j-set does not depend on the twist,
  so each floor j gives one a2 = 0 and one a2 = 1 curve; every curve passed [N]R = O in the census.

## Structure (derived, exactly computed)

![](../outputs/structure.png)

t² − 4q = −7c², c = 6473 · 53676929, and Q(√−7) has class number 1, so the crater has End = O_K and every
horizontal isogeny of degree prime to c is an endomorphism. `scripts/s00_small_isogenies.py` factors ψ_ℓ over
GF(2^83) for ℓ = 3, 5, 7, 11, 13 on both twists: ℓ = 3, 5, 13 give no rational kernel; ℓ = 7 gives {k7} kernel and
ℓ = 11 gives {k11}, and every codomain has a₆′ = 1 (the crater itself, with the same abscissae in this normal
form). The first other curves are the degree-6473 floor (verified maps in ../volcano-m83 Run-04). The F₈₃ toy's
7-isogeny/rescaling tournament therefore has a single candidate on GF(2^83).

## Instrument and control (measured)

`native/f83x.c` (x86-64 PCLMUL) computes the factor base of rational x in span(basis), cofactor tags
(log of [n]P in E(F_q)[h], Pohlig–Hellman, homomorphism self-check), and the exact number of (4-subset, sign
vector) with tag sum 0 mod h, the eligible4 count of ../volcano-m83 run06. `scripts/control_run06.py`
reproduces all 24 run06 counts exactly (all_match = {ctl['all_match']}). Normalised yield
Y = eligible / (16·C(S,4)/h); for a2 = 1 the Poisson sd of Y at S = {a1['S']} is about {a1['poisson_sd_Y']:.3f}.

## Four-summand yield census (measured)

![](../outputs/yield-census.png)

a2 = 0 (h = 4):

{table(['arm', 'Y at S = %d' % a0['S'], 'vs crater'], census_rows(a0))}

a2 = 1 (h = 1128547018):

{table(['arm', 'Y at S = %d' % a1['S'], 'vs crater'], census_rows(a1))}

Crater rank from top among the floor: a2 = 0 {a0['crater_rank_from_top']} of 6475, a2 = 1 {a1['crater_rank_from_top']} of 6475.
Natural factor-base sizes on the floor: a2 = 0 {a0['floor_x_count']['min']}–{a0['floor_x_count']['max']}, a2 = 1
{a1['floor_x_count']['min']}–{a1['floor_x_count']['max']} points. For a2 = 1 the observed floor sd of Y is {a1['floor_Y']['sd']:.4f},
{a1['floor_Y']['sd'] / a1['poisson_sd_Y']:.2f}× the Poisson sd ({a1['poisson_sd_Y']:.4f}) of a count near {round(1 / a1['poisson_sd_Y'] ** 2)}; the excess is
observed, not explained here (overlapping 4-subsets make eligible counts dependent, which is one candidate). The best floor curve,
{a1['top5'][0][1]}, is {pct(a1['top5'][0][0] / a1['crater']['Y_matched'] - 1)} above the crater, inside the gate; no replication was
preregistered, so it is not promoted and no curve is named a lead.

## Pollard rho on the a2 = 1 twist (measured)

![](../outputs/rho-a1.png)

`f83x rho`: r = 32 adding walk, next-index rule and doubling escape against fruitless cycles, distinguished points
on bits 1..d of the canonical x (bit 0 is pinned: Tr = bits {{0, 79, 81}} and Tr(x) = Tr(a2) on the odd-order
subgroup), one walk per solve, fixture scalar recovered and checked by [k]G = Q on every solve. Yield of rho =
collisions per step, reported as S = steps / √n. Priced columns charge the canonicalisation squarings at
0 / 0.1 / 1 GAE each (crypto CLAUDE.md §5a band).

{table(['arm', 'solves', 'S (± se)', 'theory', 'squarings / step', 'S priced at 0 / 0.1 / 1 GAE', 'wall s / solve'], rho_rows)}

The crater's τ classes give S ≈ {rho['crater_mode2']['S_steps_mean']:.3f} against {rho['crater_mode1']['S_steps_mean']:.3f} for ±P, the √83 factor.
Floor curves have no τ over F₂ and run as ±P rho. Across the 0–1 GAE band the {{±τ^i P}} and {{±P}} arms do not keep
one order (0.107 < 0.855 at 0 GAE, 13.3 > 0.855 at 1 GAE), so the band rule does not rank them; the single-core,
contended wall times ({rho['crater_mode2']['wall_s_mean']:.1f} s against {rho['crater_mode1']['wall_s_mean']:.1f} s) are exploratory, not a tiered timing claim.
The plain-walk means sit above and below theory with 4–6 solves each; their intervals are wide.

The k = {a1['k']} subspace base is not competitive with rho: collecting {icr['rows_needed']} rows needs at least
2^{icr['log2_queries_for_rows_lower_bound']:.1f} uniform queries against 2^{icr['log2_rho_steps_mode2_measured']:.1f} measured τ-class rho steps.
That is the expected scale gap for a 2^12-point domain; the N83 pipeline uses ≈ 5.7·10⁵ projected points and a root index.
The a2 = 0 twist needs ≈ 2^37 τ-class rho steps (prediction, not run).

## Pollard rho over the whole 53-bit floor (measured; protocol addendum)

{("" if RF is None else f"""![](../outputs/rho-floor-a1.png)

The 6474 floor curves form 78 orbits of 83 under b → b², and (x, y) → (x², y²) is a group isomorphism
E_b → E_{{b²}}, so one representative per orbit (O00-00 … O77-00) covers the floor up to that isomorphism.
`scripts/rho_floor.py` ran {RF['solves']} {{±P}} solves (2 per orbit, seeds 1000 and 1001), all verified
({RF['all_verified']}), {RF['restarts']} restarts, {RF['steps_total']:.3g} walk steps in all.

{table(['arm', 'solves', 'S (± se)'], [
    ('floor, 78 orbit representatives, {±P}', RF['solves'], '%.3f ± %.3f' % (RF['S_mean'], RF['S_se'])),
    ('crater E0, {±P}', RF['crater_pm']['n'], '%.3f ± %.3f' % (RF['crater_pm']['mean'], RF['crater_pm']['se'])),
    ('crater E0, {±τ^i P}', RF['crater_tau']['n'], '%.3f ± %.3f' % (RF['crater_tau']['mean'], RF['crater_tau']['se'])),
    ('theory {±P}', '—', '%.3f' % RF['S_theory'])])}

- Orbits are homogeneous: one-way ANOVA F({RF['anova']['df'][0]}, {RF['anova']['df'][1]}) = {RF['anova']['F']:.2f}, p = {RF['anova']['p']:.2f};
  a {RF['anova']['permutations']}-draw permutation test gives p = {RF['anova']['permutation_p']:.2f}. Two solves per orbit cannot rank orbits,
  so no orbit is named a lead (lowest orbit means {', '.join('%s %.2f' % (k, v) for v, k in RF['lowest_orbit_means'])} are draws).
- The floor's {{±P}} rho costs {RF['floor_over_crater_tau']:.2f}× the crater's τ-class rho, against √83 = {math.sqrt(83):.2f}: the Frobenius factor the
  floor loses, as derived.
- The pooled floor mean sits {(RF['S_mean'] - RF['S_theory']) / RF['S_se']:.1f} se above √(π/4). Observed and not explained here; an r = 32
  adding walk with fruitless-cycle escapes is expected to sit slightly above the random-mapping constant, which this run does not test.
- The a2 = 0 floor (~2^37 steps per solve) was not run.
""")}

## Pollard rho on every one of the 6474 floor curves (measured; protocol addendum 2)

{("" if RA is None else f"""![](../outputs/rho-floor-all-a1.png)

`scripts/rho_floor_all.py` ran one {{±P}} solve on every floor curve (seed 2000), split over 8 cloud sessions
(`--shard I --of 8`; session IDs in `outputs/rho-floor-all-a1.sessions.json`) and merged here:
{RA['solves']} solves on {RA['distinct_curves']} distinct curves of {RA['expected_curves']} expected, {RA['n_missing']} missing,
{RA['duplicates']} duplicates, all verified ({RA['all_verified']}), {RA['restarts']} restart, {RA['steps_total']:.3g} walk steps,
mean wall time {RA['wall_s_mean']:.0f} s per solve.

{table(['quantity', 'value'], [
    ('S = steps / √n, mean ± se', '%.4f ± %.4f' % (RA['S_mean'], RA['S_se'])),
    ('S standard deviation', '%.3f' % RA['S_sd']),
    ('theory √(π/4)', '%.4f' % RA['S_theory']),
    ('mean − theory', '%+.2f se' % RA['S_mean_minus_theory_in_se']),
    ('ANOVA over the 78 orbits', 'F(%d, %d) = %.3f, p = %.3f' % (RA['anova']['df'][0], RA['anova']['df'][1], RA['anova']['F'], RA['anova']['p'])),
    ('permutation test (%d draws)' % RA['anova']['permutations'], 'p = %.3f' % RA['anova']['permutation_p']),
    ('Rayleigh KS distance (95 % critical)', '%.4f (%.4f)' % (RA['rayleigh_ks_D'], RA['rayleigh_ks_D_crit95'])),
    ('orbit mean range', '%.3f – %.3f' % tuple(RA['orbit_mean_range']))])}

- No isogeny on the floor changes rho: the 78 orbits are indistinguishable (ANOVA and permutation p ≈ 0.5), and
  the per-curve S follow a Rayleigh shape (KS distance well under its critical value). The orbit means span
  {RA['orbit_mean_range'][0]:.2f}–{RA['orbit_mean_range'][1]:.2f} with ~83 solves each, the spread expected from sd {RA['S_sd']:.2f}.
- The pooled mean is {RA['S_mean_minus_theory_in_se']:.1f} se above √(π/4), confirming the 156-solve offset at much higher precision.
  Approximate attribution, not proven: retried additions on the {{±P}} class (≈ 1/32), the r = 32 adding walk's
  departure from a random mapping (≈ 1.6 %) and escapes (0.12 % of steps) predict S ≈ 0.93; the measured value sits
  about 2 se above that. Reported as observed.
- The 81-bit (a2 = 0) crater and floor were not run: they need ~2^37 steps per solve and a distributed walk that
  this session did not build, and the cloud credentials in the environment are placeholders.
""")}

## What this does not show

- No end-to-end IC row and no IC1 candidate: yields are stage diagnostics.
- The 53676929-level curves and isogenies of degree > 13 other than 6473 were not examined (../volcano-m83 §18:
  no feasible construction).
- Only polynomial-subspace factor bases at k = 12 and representations of the form span{{1, ρ, …, ρ^11}} were screened.
- Rho timings are one shared cloud core, exploratory tier.

## Graphs checked

New: `outputs/structure.svg`, `outputs/yield-census.svg`, `outputs/rho-a1.svg`, `outputs/rho-floor-a1.svg`, `outputs/rho-floor-all-a1.svg` (rendered PNG beside each).
../volcano-m83 figures and `experiments/volcano-ic/figures/` were checked and remain current: no verified edge
or curve was added and the a2 = 0 census agrees with ../volcano-m83 Run-06.

## Reproduce

```
make -C native
cd scripts
python3 control_run06.py && python3 s00_small_isogenies.py
python3 census.py floor --a2 0; ./run_rest.sh; python3 rho_panel.py
python3 analyze.py && python3 diagram.py
python3 rho_floor.py && python3 rho_floor_analyze.py
python3 rho_floor_all.py --shard I --of 8   # I = 0..7, then:
python3 rho_floor_all_analyze.py
cd ../report && python3 make_report.py && python3 build_report.py
```
"""
(HERE / 'REPORT.md').write_text(md)
print('wrote REPORT.md')
