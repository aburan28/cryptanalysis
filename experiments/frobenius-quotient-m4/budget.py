# Per-decomposition budget for index calculus on ECC2K-130 with the
# Frobenius-stable weight factor base F_w = {P : 1 <= HW_NB(x(P)) <= w}.
#
# Pure arithmetic; nothing is run against the curve.  Conventions follow
# ../pdp-scaling (rho = 2^60.81 iterations on the <-1, tau> classes; sparse
# linear algebra m * C^2; one group addition = one rho iteration) with the
# Frobenius-orbit column count C = B / 131 credited in full.
#
#   python3 budget.py [--json budget.json] [--md budget.md]
#
# Heuristics, numbered so they can be attacked:
#   H1  half of the x-values in F_w lift to a rational point (Tr(x + 1/x^2) = 0),
#       so the base has B = X_w / 2 x-classes and X_w signed points.
#   H2  a random target is a signed sum of m base points with probability
#       min(1, X_w^m / (m! * 2^131)) (uniform sums; the 4-torsion tag and
#       subgroup restriction move this by at most 2 bits and are ignored).
#   H3  one relation per Frobenius orbit column suffices (C relations).
# The per-attempt budget is what a decomposition may cost if the total is to
# tie rho; "required exponent" is log2(budget) / log2(B), the exponent in the
# factor-base size a decomposition method must achieve.  Known methods:
# exhaustive/SAT/WDSat m, hybrid m - 1, meet-in-the-middle ceil(m/2)
# (../pdp-scaling "Reading the numbers" 2).  Any GENERIC decomposition (one
# that uses only the group law) costs at least 2^65.5 per attempt, above
# rho's whole 2^60.81, so only a method using the x-coordinate algebra can
# meet any budget below; the MITM column carries that floor.

import argparse
import json
import math

N = 131
RHO = 60.81
ORBIT = math.log2(N)


def lg(x):
    return math.log2(x)


def cell(m, w):
    xw = sum(math.comb(N, i) for i in range(1, w + 1))
    lx = lg(xw)
    lb = lx - 1                                  # H1
    lp = min(0.0, m * lx - lg(math.factorial(m)) - N)   # H2
    lc = lb - ORBIT                              # columns
    lrel = lc                                    # H3
    latt = lrel - lp
    lla = lg(m) + 2 * lc
    if lla >= RHO:
        lbud = None
    else:
        lbud = lg(2 ** RHO - 2 ** lla) - latt
    # meet-in-the-middle on signed points, but never below the generic
    # two-list floor: |L1| * |L2| >= #E ~ 2^131 whatever the lists are, since
    # the group law offers no bucketing of partial sums (no k-tree)
    mitm = max(math.ceil(m / 2) * lx, N / 2.0)
    row = {'m': m, 'w': w, 'log2_B': round(lb, 2), 'log2_columns': round(lc, 2),
           'log2_p_decomp': round(lp, 2), 'log2_attempts': round(latt, 2),
           'log2_linear_algebra': round(lla, 2),
           'log2_budget_per_attempt': None if lbud is None else round(lbud, 2),
           'required_exponent_in_B': None if lbud is None or lbud <= 0 else round(lbud / lb, 3),
           'mitm_exponent': math.ceil(m / 2),
           'log2_mitm_per_attempt': round(mitm, 2),
           'mitm_gap_bits': None if lbud is None else round(mitm - lbud, 2)}
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json')
    ap.add_argument('--md')
    a = ap.parse_args()
    rows = [cell(m, w) for m in range(2, 13) for w in range(1, 16)]
    best = {}
    for r in rows:
        if r['mitm_gap_bits'] is None or r['log2_budget_per_attempt'] <= 0:
            continue
        b = best.get(r['m'])
        if b is None or r['mitm_gap_bits'] < b['mitm_gap_bits']:
            best[r['m']] = r
    lines = ['| m | w | log2 B | log2 columns | log2 P(decomp) | log2 attempts | log2 LA | '
             'log2 budget/attempt | required exponent in B | MITM exponent | log2 MITM/attempt | MITM gap (bits) |',
             '|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|']
    for m in range(2, 13):
        if m not in best:
            lines.append('| %d | — | | | | | | none: LA alone exceeds rho at every w | | %d | | |'
                         % (m, math.ceil(m / 2)))
            continue
        r = best[m]
        lines.append('| %d | %d | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %.2f | %d | %.1f | +%.1f |' % (
            m, r['w'], r['log2_B'], r['log2_columns'], r['log2_p_decomp'], r['log2_attempts'],
            r['log2_linear_algebra'], r['log2_budget_per_attempt'], r['required_exponent_in_B'],
            r['mitm_exponent'], r['log2_mitm_per_attempt'], r['mitm_gap_bits']))
    md = '\n'.join(lines)
    print(md)
    if a.json:
        with open(a.json, 'w') as f:
            json.dump({'rho_log2': RHO, 'n': N, 'rows': rows,
                       'best_by_m': [best[m] for m in sorted(best)]}, f, indent=1)
    if a.md:
        with open(a.md, 'w') as f:
            f.write(md + '\n')


if __name__ == '__main__':
    main()
