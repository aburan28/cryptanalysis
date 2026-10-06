"""The conductor-53676929 level: exact structure and the cost of reaching it.

Runs 01-10 need explicit curves.  At conductor 6473 the floor (6474 curves)
was built from a class polynomial and checked against explicit degree-6473
isogenies computed in F_(2^268588).  This script establishes the same
structure for the next level of Z[pi] in O_K, l' = 53676929, and measures
what each construction route would cost there:

  structure  class group (PARI quadclassunit), class orders of the prime
             above 2 and of small split primes, Frobenius action on E0[l'],
             torsion and kernel-polynomial fields, the level lattice, the
             exact twist order and l'-cofactor over F_(q^r') (Lucas doubling);
  costs      (a) CM: size lower bound of the class polynomial and the
             polclass timing law fitted on this study's runs;
             (b) torsion: native carryless-multiply scaling (native/clbench)
             extrapolated to F_(2^(83 r')) and a twist ladder;
             (c) search: measured cost of a [4 ELL]R = O test on random curves
             against the probability that a random b lies in the isogeny class.

    sage -python s10_level_53676929.py  ->  outputs/level-53676929/structure.json
"""
import ctypes
import json
import math
import random
import subprocess
import time

from sage.all import Integer, factor, kronecker, pari

import f83lib
import m83

OUT = m83.OUT / 'level-53676929'
L1, L2 = m83.F1, m83.F2          # 6473, 53676929


def class_order(D, p, h):
    f = pari.qfbprimeform(D, p)
    one = pari.qfbpow(f, 0)
    n = h
    for r, e in factor(h):
        for _ in range(e):
            if pari.qfbpow(f, n // r) == one:
                n //= r
    return int(n)


def lucas_v(n):
    """V_n = tau^n + taubar^n for tau^2 + tau + 2 = 0 (V_1 = -1), by doubling."""
    vk, vk1, k = Integer(2), Integer(-1), 0
    for bit in bin(n)[2:]:
        v2k = vk * vk - (Integer(2) << k)
        v2k1 = vk * vk1 + (Integer(1) << k)
        if bit == '1':
            vk, vk1, k = v2k1, vk1 * vk1 - (Integer(2) << (k + 1)), 2 * k + 1
        else:
            vk, vk1, k = v2k, v2k1, 2 * k
    return vk


def structure():
    q = m83.Q
    a = m83.TAU_A
    D = -7 * L2 ** 2
    h = L2 + 1
    t0 = time.perf_counter()
    cl = pari.quadclassunit(D)
    cl_seconds = time.perf_counter() - t0
    assert int(cl[0]) == h and len(cl[1]) == 1
    orders = {str(p): class_order(D, p, h) for p in [2, 11, 23, 29, 37, 43, 53]
              if p == 2 or kronecker(D, p) == 1}
    assert orders['2'] == m83.M
    c = a % L2
    o = int(pari.znorder(pari.Mod(c, L2)))
    minus_one_in = pow(c, o // 2, L2) == L2 - 1 if o % 2 == 0 else False
    r = o // 2 if minus_one_in else o                 # x-coordinate field degree over F_q
    per_line = ((L2 - 1) // 2) // r
    assert per_line == 4 and pow(c, r, L2) == L2 - 1
    # exact twist order over F_(q^r): E0[l'] x-coordinates live on the twist
    N = m83.M * r
    t0 = time.perf_counter()
    V = lucas_v(N)
    Q = Integer(1) << N
    tw = Q + 1 + V
    e = 0
    while tw % L2 == 0:
        tw //= L2
        e += 1
    lucas_seconds = time.perf_counter() - t0
    classes = {'crater (conductor 1)': 1, 'conductor 6473': L1 + 1, 'conductor 53676929': h,
               'conductor 6473*53676929': (L1 + 1) * h}
    size = sum(classes.values())
    return {
        'l_prime': L2, 'inert': kronecker(-7, L2) == -1, 'discriminant': D, 'class_number': h,
        'class_number_factorization': str(factor(h)), 'class_group': [int(x) for x in cl[1]],
        'quadclassunit_seconds': cl_seconds, 'frobenius_orbits': h // m83.M,
        'ideal_class_orders': orders,
        'horizontal_cycles': {p: {'length': n_, 'cycles': h // n_, 'orbits_per_cycle': n_ // m83.M}
                              for p, n_ in orders.items() if p != '2'},
        'minimum_noninteger_endomorphism_degree': (7 * L2 * L2 + 1) // 4,
        'pi_scalar_on_E0_l': c, 'pi_scalar_order': o, 'index_in_F_l_star': (L2 - 1) // o,
        'minus_one_in_frobenius_group': minus_one_in,
        'x_coordinate_field_degree': r, 'x_coordinate_field_bits': N,
        'kernel_polynomial_degree': (L2 - 1) // 2,
        'kernel_polynomial_irreducible_factors': per_line, 'factor_degree': r,
        'full_E0_torsion_field_degree': o, 'floor_full_torsion_field_degree': o * L2,
        'q_mod_l': q % L2, 'mu_l_embedding_degree': int(pari.znorder(pari.Mod(q, L2))),
        'twist_l_valuation_over_F_q_r': e, 'twist_cofactor_bits': int(tw.nbits()), 'lucas_seconds': lucas_seconds,
        'level_lattice': {'sizes': classes, 'isogeny_class_size': size,
                          'edges': 'each conductor-53676929 curve: 1 ascending 53676929-isogeny to E0 and '
                                   '6474 descending 6473-isogenies; each bottom curve: one ascending isogeny of '
                                   'each prime degree'},
        'embedding_degree_of_ELL_bits': 74,
    }


def costs(st):
    # (a) CM class polynomial: the X^(h-1) coefficient is -sum of the roots and is
    # dominated by j of the principal form, |j| ~ exp(pi sqrt|D|).
    D = st['discriminant']
    j_bits = math.pi * math.sqrt(-D) / math.log(2)
    runs = [(312, 0.957), (1302, 22.6), (2694, 107.1), (6474, 702.7)]   # polclass(D, 5) on this machine
    xs = [math.log(h) for h, _ in runs]
    ys = [math.log(s) for _, s in runs]
    k = (len(xs) * sum(x * y for x, y in zip(xs, ys)) - sum(xs) * sum(ys)) / (len(xs) * sum(x * x for x in xs) - sum(xs) ** 2)
    c0 = math.exp((sum(ys) - k * sum(xs)) / len(xs))
    cm_seconds = c0 * st['class_number'] ** k
    # (b) torsion route: measured clmul scaling, Kronecker size of F_(2^(83 r))
    rows = [json.loads(l) for l in subprocess.run([str(m83.ROOT / 'native' / 'clbench'), '1068032'],
                                                  capture_output=True, text=True, check=True).stdout.split()]
    w1, t1 = rows[-2]['words'], rows[-2]['cpu_seconds']
    w2, t2 = rows[-1]['words'], rows[-1]['cpu_seconds']
    exponent = math.log(t2 / t1) / math.log(w2 / w1)
    words = math.ceil((2 * m83.M - 1) * st['x_coordinate_field_degree'] / 64)
    mult_seconds = t2 * (words / w2) ** exponent
    ladder_mults = 5 * st['twist_cofactor_bits']
    ladder_seconds = ladder_mults * mult_seconds
    # 6473 reference point: the measured ladder over F_(2^268588)
    e0 = json.loads((m83.OUT / 'run04-explicit-descent' / 'E0-torsion.json').read_text())
    # (c) search: probability that a random b gives a curve in the isogeny class
    _LIB = f83lib._LIB
    _LIB.f83_scalar.argtypes = [f83lib.FE, f83lib.FE, f83lib.FE, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int,
                                ctypes.POINTER(f83lib.FE), ctypes.POINTER(f83lib.FE)]
    bits = [int(ch) for ch in bin(m83.N)[2:]]
    B = (ctypes.c_uint8 * len(bits))(*bits)
    rng = random.Random(10)
    tests = hits = 0
    cpu = 0.0
    while tests < 20000:
        b, x = rng.getrandbits(83) or 1, rng.getrandbits(83) or 1
        if not f83lib.ratx(b, [x])[1]:
            continue
        y = f83lib.points(b, [x])[0][0]
        ox, oy = f83lib.FE(), f83lib.FE()
        t0 = time.process_time()
        inf = _LIB.f83_scalar(f83lib.fe(b), f83lib.fe(x), f83lib.fe(y), B, len(bits), ctypes.byref(ox), ctypes.byref(oy))
        cpu += time.process_time() - t0
        hits += inf == 1
        tests += 1
    per_test = cpu / tests
    size = st['level_lattice']['isogeny_class_size']
    expected_tests = 2 ** m83.M / size
    year = 365.25 * 86400
    return {
        'cm_class_polynomial': {'degree': st['class_number'], 'j_coefficient_bits_lower_bound': j_bits,
                                'gamma2_coefficient_bits_lower_bound': j_bits / 3,
                                'polclass_timing_law': {'seconds': 'c * h^k', 'c': c0, 'k': k, 'fitted_on': runs},
                                'extrapolated_cpu_years': cm_seconds / year},
        'torsion_route': {'field_bits': st['x_coordinate_field_bits'], 'element_megabytes': st['x_coordinate_field_bits'] / 8e6,
                          'kronecker_words': words, 'clbench': rows, 'fitted_exponent': exponent,
                          'multiplication_cpu_seconds': mult_seconds, 'ladder_bits': st['twist_cofactor_bits'],
                          'ladder_multiplications': ladder_mults, 'ladder_cpu_years': ladder_seconds / year,
                          'reference_6473_ladder_seconds': e0['ladder_seconds'],
                          'reference_6473_field_bits': 83 * 3236},
        'random_search': {'isogeny_class_size': size, 'success_probability_per_curve': size / 2 ** m83.M,
                          'expected_tests': expected_tests, 'measured_tests': tests, 'measured_hits': hits,
                          'cpu_seconds_per_test': per_test, 'expected_cpu_years': expected_tests * per_test / year,
                          'probability_hit_is_on_this_level': st['class_number'] / size,
                          'then': 'a hit on the bottom level needs one ascending 6473-isogeny (the F_(2^268588) '
                                  'computation of Run-04) to reach the conductor-53676929 level'},
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    st = structure()
    print(json.dumps({k: v for k, v in st.items() if k != 'level_lattice'}, indent=1), flush=True)
    co = costs(st)
    routes = {'CM class polynomial': co['cm_class_polynomial']['extrapolated_cpu_years'],
              'torsion ladder': co['torsion_route']['ladder_cpu_years'],
              'random search': co['random_search']['expected_cpu_years']}
    cheapest = min(routes, key=routes.get)
    out = {'structure': st, 'costs': co, 'route_cpu_years': routes, 'cheapest_route': cheapest,
           'conclusion': 'runs 01-10 require explicit conductor-53676929 curves; the cheapest known route '
                         '(%s) is estimated at %.0f CPU-years on this machine' % (cheapest, routes[cheapest])}
    (OUT / 'structure.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(co, indent=1))


if __name__ == '__main__':
    main()
