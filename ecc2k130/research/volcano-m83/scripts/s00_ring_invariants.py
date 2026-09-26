"""Public ring invariants of the F_(2^83) Koblitz curve, standard library only.

E0: y^2 + xy = x^3 + 1 over F_(2^83), the m=83 instance of the repository's
ECC2K-130 client.  This is fixed integer arithmetic: no isogenies, relation
systems, point data or discrete logarithms.  Every primality claim below is
backed by a Lucas certificate whose leaves are checked by trial division.

    python3 s00_ring_invariants.py > ../outputs/s00-ring-invariants.json
"""

import json
from math import gcd, isqrt, log2, pi, prod


def require(condition, message):
    if not condition:
        raise ValueError(message)


def trial_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    return all(n % d for d in range(3, isqrt(n) + 1, 2))


def lucas_prime(n, factors, witness):
    """Lucas: n prime if w^(n-1)=1 and w^((n-1)/p)!=1 for every prime p | n-1."""
    require(prod(p ** e for p, e in factors.items()) == n - 1, 'incomplete n-1 for %d' % n)
    require(pow(witness, n - 1, n) == 1, 'Fermat step failed for %d' % n)
    for p in factors:
        require(gcd(pow(witness, (n - 1) // p, n) - 1, n) == 1, 'Lucas step failed %d/%d' % (n, p))
    return True


def certify(n, certs):
    """Recursive certificate: leaves by trial division, others by Lucas."""
    if n < 10 ** 12:
        require(trial_prime(n), '%d is not prime' % n)
        return {'n': n, 'method': 'trial division'}
    factors, witness = certs[n]
    children = [certify(p, certs) for p in factors]
    lucas_prime(n, factors, witness)
    return {'n': n, 'method': 'Lucas', 'witness': witness,
            'n_minus_1': {str(p): e for p, e in factors.items()}, 'factors': children}


def reduced_primitive_form_count(d):
    require(d < 0 and d % 4 in (0, 1), 'invalid D')
    count = 0
    for a in range(1, isqrt(abs(d) // 3) + 1):
        for b in range(-a + 1, a + 1):
            if (b * b - d) % (4 * a):
                continue
            c = (b * b - d) // (4 * a)
            if a > c or (a == c and b < 0):
                continue
            if gcd(gcd(a, abs(b)), c) == 1:
                count += 1
    return count


def multiplicative_order(a, n, factors):
    """Order of a modulo prime n, given the factorization of n - 1."""
    order = n - 1
    for p, e in factors.items():
        for _ in range(e):
            if pow(a, order // p, n) == 1:
                order //= p
    return order


def factorize_small(n):
    out = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            out[d] = out.get(d, 0) + 1
            n //= d
        d += 1
    if n > 1:
        out[n] = out.get(n, 0) + 1
    return out


def main():
    m = 83
    q = 2 ** m
    affine = [(x, y) for x in range(2) for y in range(2) if (y * y + x * y - x ** 3 - 1) % 2 == 0]
    base_trace = 3 - (len(affine) + 1)
    require(base_trace == -1, 'E0(F_2) count mismatch')

    # tau^2 + tau + 2 = 0; tau^i = a + b tau.
    a, b = 1, 0
    for _ in range(m):
        a, b = -2 * b, a - b
    trace = 2 * a - b
    conductor = abs(b)
    require(a * a - a * b + 2 * b * b == q, 'norm identity')
    require(trace * trace - 4 * q == -7 * conductor ** 2, 'discriminant identity')
    t0, t1 = 2, base_trace
    for _ in range(2, m + 1):
        t0, t1 = t1, -t1 - 2 * t0
    require(t1 == trace, 'independent trace recurrence')

    ell = 2417851639230796216685689
    require(q + 1 - trace == 4 * ell, 'point count 4*ell')
    big = 1012327725929069161
    certs = {
        ell: ({2: 3, 3: 1, 11: 1, 83: 1, 109: 1, big: 1}, 19),
        big: ({2: 3, 3: 2, 5: 1, 13: 1, 17: 1, 59: 1, 11119: 1, 19395841: 1}, 7),
    }
    ell_cert = certify(ell, certs)

    f1, f2 = 6473, 53676929
    require(trial_prime(f1) and trial_prime(f2), 'conductor primes')
    require(f1 * f2 == conductor, 'conductor factorization')
    symbols = {p: (1 if pow(-7 % p, (p - 1) // 2, p) == 1 else -1) for p in (f1, f2)}
    require(symbols == {f1: -1, f2: -1}, 'both conductor primes are inert')
    require(reduced_primitive_form_count(-7) == 1, 'h(-7)')
    h_floor = reduced_primitive_form_count(-7 * f1 ** 2)
    require(h_floor == f1 + 1, 'conductor-6473 class number by form count')

    orders = []
    for f in (1, f1, f2, conductor):
        h = prod(p - symbols[p] for p in (f1, f2) if f % p == 0)
        orders.append({'conductor': f, 'discriminant': -7 * f * f, 'class_number': h,
                       'frobenius_orbits_if_enumerated': h // m if f > 1 else 1,
                       'minimum_noninteger_endomorphism_degree': (7 * f * f + 1) // 4 if f > 1 else 2,
                       'gcd_class_number_subgroup_order': gcd(h, ell)})

    # q-Frobenius on E0[f] is multiplication by a mod f because f | b.
    local = {}
    for p in (f1, f2):
        pf = factorize_small(p - 1)
        local[str(p)] = {
            'legendre_minus7': symbols[p],
            'pi_scalar_mod_p': a % p,
            'order_of_pi_scalar': multiplicative_order(a % p, p, pf),
            'q_mod_p': q % p,
            'mu_p_embedding_degree': multiplicative_order(q % p, p, pf),
            'x_coordinate_field_degree_of_E0_p_torsion': multiplicative_order(a % p, p, pf) // 2,
        }
    require(local[str(f1)]['pi_scalar_mod_p'] == 2514, 'pi mod 6473')
    require(local[str(f1)]['order_of_pi_scalar'] == f1 - 1, 'pi is a primitive root mod 6473')

    ell_minus_1 = {2: 3, 3: 1, 11: 1, 83: 1, 109: 1, big: 1}
    k_emb = multiplicative_order(q % ell, ell, ell_minus_1)
    require((ell - 1) // k_emb == 2 * m, 'embedding degree cofactor 166')

    # Idealized collision-search operation counts (no canonicalization overhead).
    rho = {
        'no_quotient_log2': 0.5 * log2(pi * ell / 2),
        'negation_log2': 0.5 * log2(pi * ell / 4),
        'signed_frobenius_log2': 0.5 * log2(pi * ell / (4 * m)),
        'signed_frobenius_orbit_size': 2 * m,
    }

    result = {
        'scope': 'public arithmetic invariants; no solver-hardness measurement',
        'curve': 'y^2 + xy = x^3 + 1 over F_(2^83)',
        'affine_points_over_F2': affine,
        'base_trace': base_trace,
        'extension_degree': m,
        'tau_power_coefficients': [a, b],
        'extension_trace': trace,
        'group_order': 4 * ell,
        'prime_subgroup_order': ell,
        'prime_subgroup_certificate': ell_cert,
        'frobenius_order_conductor': conductor,
        'frobenius_order_conductor_factorization': {str(f1): 1, str(f2): 1},
        'possible_orders': orders,
        'conductor_6473_reduced_form_count': h_floor,
        'conductor_prime_local_data': local,
        'embedding_degree': k_emb,
        'embedding_degree_bits': k_emb.bit_length(),
        'embedding_degree_cofactor': (ell - 1) // k_emb,
        'rho_baselines': rho,
        'all_arithmetic_checks_passed': True,
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
