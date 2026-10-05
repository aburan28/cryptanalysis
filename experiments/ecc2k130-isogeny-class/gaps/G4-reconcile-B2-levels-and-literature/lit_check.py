#!/usr/bin/env python3
"""G4 part (2): check literature claims L1-L5 against the source texts (grep only, never whole files),
and re-check the L3 horizontal-edge claims in literature/per_curve.json against the codex-crosscheck C1
horizontal-edge results (Frobenius-equivariant neighbour rules) for all 262 floor curves.
Output: lit_check.json (line pointers into the texts; at most one short quote per source).
Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; timeout 2400 python3 lit_check.py
"""
import json, re, os
W = '/Volumes/SSD990/ecdlp-hardness-work'
OUT = os.path.join(W, 'gaps/G4-reconcile-B2-levels-and-literature')
SRC = {
    'JMV05': f'{W}/literature/raw/jmv2005.txt',
    'Rob22': f'{W}/literature/raw/robert2022.txt',
    'Sut13': f'{W}/literature/raw/sutherland.txt',
    'Gal99': f'{W}/literature/raw/galbraith1999.txt',
    'Kohel96': f'{W}/literature/raw/kohel1996.txt',
    'Gal24': f'{W}/verify/p-levels/C4-audit/lit/galbraith2024_eprint924.txt',
    'GGR25': f'{W}/verify/p-levels/C4-audit/lit/ggr2025_eprint1243.txt',
    'RobNotes24': f'{W}/verify/p-levels/C4-audit/lit/robert_notes_2024_406.txt',
    'CEL21': f'{W}/verify/p-levels/C4-audit/lit/cel2021.txt',
}
LINES = {k: open(v, errors='replace').read().split('\n') for k, v in SRC.items()}
def find(src, pat, flags=re.I):
    rx = re.compile(pat, flags)
    return [i + 1 for i, ln in enumerate(LINES[src]) if rx.search(ln)]
def span_find(src, pat, width=3):
    """match a pattern across line breaks: join windows of `width` lines."""
    rx = re.compile(pat, re.I | re.S); L = LINES[src]; hits = []
    for i in range(len(L)):
        if rx.search(' '.join(L[i:i + width])): hits.append(i + 1)
    return hits

ev = {}
def put(key, src, pat, span=False):
    h = span_find(src, pat) if span else find(src, pat)
    ev[key] = dict(source=src, file=SRC[src], pattern=pat, lines=h[:6], found=bool(h))
    return bool(h)

# --- L1: block split (JMV05 sec 1.1 and sec 6) --------------------------------------------------
put('JMV05 sec1.1 no poly-time algorithm produces curves across non-smooth conductor gap', 'JMV05', r'even produces a pair of')
put('JMV05 sec6 cannot prove random reducibility for whole class', 'JMV05', r'cannot prove random reducibility')
put('JMV05 sec6 constructible subset = levels reachable by Kohel', 'JMV05', r'coincides exactly with the subcollection')
put('Gal24 Thm2 statement (crater -> E1, O~(h0 N^1/2))', 'Gal24', r'^Theorem 2\.')
put('Gal24 Thm2 complexity line', 'Gal24', r'complexity .?O.?\(h0 N 1/2 log')
put('Gal24 h0 = O(1) gives O~(q^1/4)', 'Gal24', r'When h0 = O\(1\)')
put('Gal24 sec9 Theorem 5 (random curve in class, O~(q^2/5) + polylog queries)', 'Gal24', r'^Theorem 5\.')
put('Gal24 sec10: floor-to-crater isogeny in at most O(q^1/4) when h0 small', 'Gal24', r'can be constructed in time at most')
put('Gal24 sec10: only two ways crater->floor (N^2 or guessing), each >= q^1/2', 'Gal24', r'we only know two ways to do this')
# --- L2: vertical isogenies ------------------------------------------------------------------------
put('Rob22 end of sec4: poly(log l) volcano navigation open', 'Rob22', r'move in the .-isogeny volcano in time polynomial')
put('Sut13 sec3.3: no vertical l-isogeny algorithm below linear in l', 'Sut13', r'not know any algorithm for computing a vertical')
put('Gal24 sec2.2: Phi_N in O~(N^2 log q) for any field (Leroux, Robert, Kunzweiler-Robert)', 'Gal24', r'for any field Fq in')
put('Gal24 sec8.1: even in 1999 O~(N^2) achievable', 'Gal24', r'even in 1999 one could have achieved')
put('Gal24 Thm1 (representation of unknown N-isogeny in O~(N^1/2))', 'Gal24', r'^Theorem 1\. Let E0 and E1')
put('Gal24 Thm1 needs N free of primes < 4 log N loglog N', 'Gal24', r'not divisible by any prime smaller than 4 log')
put('Gal24 sec2.1 Elkies-prime heuristic removable when |D0| bounded', 'Gal24', r'D0 is bounded, but we wish')
put('Gal24 sec4: 4-squares proved, 2-squares preferred in practice', 'Gal24', r'one would prefer to do the two squares version')
put('Gal24 Alg1: 2- and 3-power parts (E1[4] image convenient)', 'Gal24', r'it is convenient to know')
put('Gal24 Thm4 (Problem B in O~(q^1/2))', 'Gal24', r'^Theorem 4\. One can solve Problem B')
put('Gal24 sec11: better solution to Problem B is open', 'Gal24', r'better solution to Problem B')
put('GGR25 abstract: self-pairings remove a heuristic of Gal24', 'GGR25', r'eliminate a heuristic')
put('GGR25 Thm 4.3 ascending isogeny recovery', 'GGR25', r'^Theorem 4\.3\.')
put('RobNotes24: char-2 isogeny algorithm only for dimension 2 [BCR10b]', 'RobNotes24', r'characteristic two is described in \[BCR10b\]')
put('RobNotes24: theta theory needs characteristic prime to level n', 'RobNotes24', r'characteristic prime to the level n')
put('RobNotes24 CA 2.8: O(l^g) in k\' from a basis; O(l^{gr}) in k from equations', 'RobNotes24', r'^Complexity Analysis 2\.8')
put('RobNotes24 Cor 7.2: level-n theta point has n^g coordinates (e_i, e_i+e_j needed)', 'RobNotes24', r'uniquely determined by')
put('CEL21 abstract: char-2 isogenies quasi-linear in degree', 'CEL21', r'quasi-linear time in the degree')
put('CEL21 sec3: needs Weierstrass model of isogenous curve and the isogeny differential', 'CEL21', r'isogeny differential\. In this section')
put('CEL21 sec3.2: Elkies normalisation is quadratic in the degree', 'CEL21', r'of quadratic complexity in the')
# --- L4 / L5 -------------------------------------------------------------------------------------------
put('Gal99 sec2 main exception (large prime in index): relation of DLPs unclear', 'Gal99', r'main exception')
put('Gal99 sec8 no shortcut when only one conductor divisible by large prime', 'Gal99', r'no shortcut')
put('Kohel96 Prop 21 (prime-degree isogeny: index divides l)', 'Kohel96', r'Proposition 21')
put('Rob22 Thm 4.2 (End(E) in poly time given factorisation of Delta)', 'Rob22', r'^Theorem 4\.2\.')
put('Gal24 sec2: level of any curve easy (BS11 subexp, Rob22b poly once conductor factored)', 'Gal24', r'polynomial-time method once the conductor is factored')
put('JMV05 Cor 1.2 (within level, GRH)', 'JMV05', r'Corollary 1\.2')

# --- L3: re-check horizontal neighbours in literature/per_curve.json for all 262 floor curves -----------
pc = json.load(open(f'{W}/literature/per_curve.json'))
heq = json.load(open(f'{W}/verify/codex-crosscheck/C1-audit/horiz_equivariance.json'))
def lab(o, k): return f'{o}{k % 131:03d}'
def other(o): return 'B' if o == 'A' else 'A'
def shifts_from(l):
    a0 = heq[str(l)]['A000_nb']; b0 = heq[str(l)]['B000_nb']
    sa = sorted((x[0], int(x[1:])) for x in a0); sb = sorted((x[0], int(x[1:])) for x in b0)
    return sa, sb
l3 = {}
for l in (2, 11, 29):
    bad = []; n = 0
    for o in 'AB':
        for k in range(131):
            L = lab(o, k); ent = pc[L]['small_isogeny_neighbours_computed'].get(f'l={l}')
            if l == 2:
                expect = sorted([lab(o, k + 1), lab(o, k - 1)])
            else:
                sa, sb = shifts_from(l)
                sh = sa if o == 'A' else sb
                expect = sorted(lab(tgt_o, k + s) for (tgt_o, s) in sh)
            got = sorted(x[0] for x in ent)
            n += 1
            if got != expect: bad.append((L, got, expect))
    l3[f'l={l}'] = dict(curves_checked=n, mismatches=len(bad), first_mismatches=bad[:3],
                        cross_orbit=(heq[str(l)]['cross_orbit_edges'] if str(l) in heq else 0),
                        rule=('Frobenius: X_k -> X_{k+1} (inseparable) and X_{k-1} (separable dual)' if l == 2 else
                              f"C1-audit equivariance rule from A000->{heq[str(l)]['A000_nb']}, B000->{heq[str(l)]['B000_nb']}"))
e0 = pc['E0']['small_isogeny_neighbours_computed']
l3['E0'] = e0
# direct computations in codex-crosscheck C1 (not by equivariance)
direct = []
for fn in ('horiz_l11.jsonl', 'horiz_general_l29.jsonl', 'horiz_general_l23.jsonl'):
    for ln in open(f'{W}/verify/codex-crosscheck/C1-audit/{fn}'):
        if ln.strip(): direct.append(json.loads(ln))
l3['C1-audit direct Velu computations (l, curve, match with Codex)'] = [(d['l'], d['curve'], d['match']) for d in direct]
json.dump(dict(evidence=ev, L3_recheck=l3), open(os.path.join(OUT, 'lit_check.json'), 'w'), indent=1)
for k, v in ev.items(): print(('OK  ' if v['found'] else 'MISS'), v['source'], v['lines'], '|', k)
print(json.dumps(l3, indent=1)[:3000])
