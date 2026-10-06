# Full index-calculus cost at n = 131 with the linearized-half (LHD) oracle.
#
# Arithmetic only.  Same conventions as ../pdp-scaling and ../frobenius-quotient-m4
# (rho 2^60.81; sparse LA m * C^2; one oracle call charged ORACLE_LOG2 group
# operations -- a (3l - 1)-column F_2 solve plus ~3l field multiplications).
#
# LHD with a k-point linearized oracle (k = 2 implemented in lhd.py):
#   columns C = 2^l (V = span{1..z^(l-1)} is not Frobenius stable at prime n,
#               so no orbit quotient; the orbit union does not help either,
#               because the oracle only linearizes same-shift tuples)
#   cost per relation = 2^(n - k l) oracle calls (sample the other m - k points;
#               m is the smallest arity with m l >= n - 5)
#   linearization needs sum_{i<=k} dim V^i <= n, with dim V^i >= i(l - 1) + 1
#   (for V a polynomial-degree subspace this is equality; for prime n the
#   linear Cauchy-Davenport bound of Hou-Leung-Xiang / Bachoc-Serra-Zemor says
#   no V does better -- recalled, not re-derived here).
#
#   python3 lhd_budget.py

import math

N = 131
RHO = 60.81
ORACLE_LOG2 = 4.0   # charged group-op equivalents per oracle call (generous)


def maxL(k):
    # sum_{i=1..k} (i (l - 1) + 1) <= N
    s = k * (k + 1) // 2
    return (N - k + s) // s


def main():
    print('| k | max l (linearization) | m | l | log2 columns | log2 relation phase | log2 LA | log2 total | vs rho |')
    print('|--:|--:|--:|--:|--:|--:|--:|--:|--:|')
    best = None
    for k in (2, 3, 4):
        lmax = maxL(k)
        rows = []
        for l in range(1, lmax + 1):
            m = max(k + 1, math.ceil((N - 5) / l))   # smallest arity with relations
            rel = l + max(0, N - k * l) + ORACLE_LOG2
            la = math.log2(m) + 2 * l
            tot = math.log2(2 ** rel + 2 ** la)
            rows.append((tot, l, rel, la, m))
        if not rows:
            print('| %d | %d | — | | | | none: 4l < n at every admissible l | |' % (k, lmax))
            continue
        tot, l, rel, la, m = min(rows)
        print('| %d | %d | %d | %d | %d | %.1f | %.1f | %.1f | +%.1f |' % (k, lmax, m, l, l, rel, la, tot, tot - RHO))
        if best is None or tot < best[0]:
            best = (tot, k, l)
    print()
    print('Best: k = %d, l = %d, total 2^%.1f against rho 2^%.2f.' % (best[1], best[2], best[0], RHO))
    print('Asymptotically: relation phase 2^(n - (k-1) l) with l <= 2n/(k(k+1)) gives '
          '2^(n(1 - 2(k-1)/(k(k+1)))) >= 2^(2n/3) for every k; the LA 2^(2l) is below it.')


if __name__ == '__main__':
    main()
