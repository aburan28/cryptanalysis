"""Run-07: exact half-trace pair membership on F_(2^83).

An unordered pair {x, y} of distinct factor-base x-coordinates is encoded by
s = x + y (k bits of the polynomial subspace) and t = xy (2k - 1 bits: the
product of two polynomials of degree < k has degree <= 2k - 2 < 83).  With
c = t / s^2 and m = 83 odd, HT(c) = sum_{i<=41} c^(4^i) satisfies
HT(c)^2 + HT(c) = c + Tr(c), so when Tr(c) = 0 the roots are x = s HT(c) and
x + s.  (s, t) is valid exactly when s != 0, Tr(c) = 0, both roots lie in the
subspace and both lift to the curve.

For each curve and k = 4..7 this evaluates the predicate on every affine
(s, t) (2^(3k-1) assignments), checks that the accepted set is exactly the
C(b, 2) pair images, and interpolates the invalid-pair indicator to its ANF
(degree, term count), against the direct x-membership ANF.  The useful-scale
variable model is evaluated at the Run-06 crossover dimension.

    sage -python run07_halftrace.py
"""
import json
import math
import time

import numpy as np

import f83lib
import m83
from run01_comparison import coordinate_basis

OUT = m83.OUT / 'run07-halftrace'


def mobius(table, nbits):
    a = table.astype(np.uint8).copy()
    for i in range(nbits):
        step = 1 << i
        a = a.reshape(-1, 2 * step)
        a[:, step:] ^= a[:, :step]
        a = a.reshape(-1)
    return a


def anf_stats(table, nbits):
    coeffs = mobius(table, nbits)
    idx = np.nonzero(coeffs)[0]
    if len(idx) == 0:
        return 0, 0
    pop = np.array([bin(int(i)).count('1') for i in idx])
    return int(pop.max()), int(len(idx))


def poly_to_bits(v, nbits):
    return v & ((1 << nbits) - 1)


def run_curve(cid, b, k):
    started = time.perf_counter()
    basis = [m83.enc(u) for u in coordinate_basis(k, 'polynomial')]   # w^i: element i <-> bit i
    rational = f83lib.ratx(b, basis)
    xs = [m for m in range(1 << k) if rational[m]]
    nb = len(xs)
    nt = 2 * k - 1
    nvars = k + nt
    # half-trace predicate on every affine (s, t)
    invalid = np.ones(1 << nvars, dtype=np.uint8)
    accepted = 0
    for s in range(1, 1 << k):
        inv_s2 = f83lib.inv(f83lib.mul(s, s))
        for t in range(1 << nt):
            c = f83lib.mul(t, inv_s2)
            if f83lib.trace(c):
                continue
            x = f83lib.mul(s, f83lib.halftrace(c))
            y = x ^ s
            if x >> k or y >> k:                 # outside the polynomial subspace
                continue
            if not (rational[x] and rational[y]):
                continue
            invalid[s | (t << k)] = 0
            accepted += 1
    # the accepted set is exactly the pair images
    images = set()
    for i in range(nb):
        for j in range(i + 1, nb):
            x, y = xs[i], xs[j]
            images.add((x ^ y) | (f83lib.mul(x, y) << k))
    acc_set = set(np.nonzero(invalid == 0)[0].tolist())
    assert accepted == len(images) == math.comb(nb, 2) and acc_set == images
    pdeg, pterms = anf_stats(invalid, nvars)
    direct = np.array([0 if (m and rational[m]) else 1 for m in range(1 << k)], dtype=np.uint8)
    ddeg, dterms = anf_stats(direct, k)
    return {'curve_id': cid, 'k': k, 'rational_x': nb, 'pair_variables': nvars,
            'exhaustive_assignments': 1 << nvars, 'accepted_pairs': accepted,
            'accepted_equals_choose_b_2': True, 'pair_anf_degree': pdeg, 'pair_anf_terms': pterms,
            'pair_anf_density': pterms / (1 << nvars), 'direct_anf_degree': ddeg, 'direct_anf_terms': dterms,
            'seconds': time.perf_counter() - started}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    halftrace_checks = 0
    import random
    rng = random.Random(83)
    for _ in range(64):
        c = rng.getrandbits(83)
        h = f83lib.halftrace(c)
        assert f83lib.mul(h, h) ^ h == c ^ f83lib.trace(c)
        halftrace_checks += 1
    inventory = {c['curve_id']: c for c in m83.load_inventory()}
    sel = json.loads((m83.OUT / 'run04-explicit-descent' / 'selection.json').read_text())
    ids = ['E0'] + [p['curve_id'] for p in sel['selected']]
    rows = []
    for k in (4, 5, 6, 7):
        for cid in ids:
            row = run_curve(cid, int(inventory[cid]['b']), k)
            rows.append(row)
            print(json.dumps(row), flush=True)
    rho = json.loads((m83.OUT / 'run06-four-summand' / 'rho-comparison.json').read_text())
    kc = rho['crossover_k']
    b = 2 ** (kc - 1)
    model = {'k': kc, 'direct_S5_variables': 4 * kc, 'two_affine_pair_images': 2 * (3 * kc - 1),
             'root_witness': 4 * kc, 'full_field_auxiliary_circuit': 2 * (3 * kc - 1 + 3 * m83.M),
             'factor_base_x': b, 'unordered_pairs_log2': math.log2(math.comb(b, 2)),
             'two_index_truth_table_log2': 2 * math.log2(math.comb(b, 2)),
             'semantic_bits_saved': 2}
    out = {'halftrace_identity_checks': halftrace_checks, 'rows': rows, 'useful_scale_model': model}
    (OUT / 'halftrace-results.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(model, indent=1))


if __name__ == '__main__':
    main()
