"""Run-05: embedding degree and conductor-prime torsion, crater versus floor.

Collects the arithmetic receipts (s00) and the explicit torsion computations
(native ladders over F_Q, Q = q^3236 = 2^268588) into one result:

  * large subgroup: ord_ELL(q) is a 74-bit divisor of ELL - 1, invariant on the
    whole F_q-isogeny class, so descent gives no MOV shortcut;
  * at l = 6473: q = 2548, t = 2 * 2514 and X^2 - tX + q = (X - 2514)^2 mod l;
    2514 is a primitive root, so mu_l first appears over F_(q^3236);
  * crater: pi = 2514 I on E0[l] (frobcheck), the twist of E0 over F_Q has
    l-part (Z/l)^2 (a point of order l and 6474 distinct kernel lines), and E0[l]
    is rational over F_(q^6472);
  * floor: pi = 2514 I + N with N != 0 nilpotent; the twist of the reference
    floor curve over F_Q has a point of order l^2, so its l-part is cyclic
    Z/l^2, exactly one kernel line is Frobenius-stable, and full E[l] needs
    F_(q^(6472 * 6473)).

    python3 s05_embedding.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'outputs'


def main():
    inv = json.loads((OUT / 's00-ring-invariants.json').read_text())
    d = OUT / 'run04-explicit-descent'
    e0 = json.loads((d / 'E0-torsion.json').read_text())
    floor = json.loads((d / 'O00-00-torsion.json').read_text())
    frob = json.loads((d / 'E0-frobcheck.json').read_text())
    lines = json.loads((d / 'line-codomains.json').read_text())
    l = 6473
    local = inv['conductor_prime_local_data'][str(l)]
    a = local['pi_scalar_mod_p']
    t = inv['extension_trace']
    q_mod = local['q_mod_p']
    assert (t - 2 * a) % l == 0 and (q_mod - a * a) % l == 0
    assert e0['order_is_ell'] and not e0['order_is_ell_squared']
    assert floor['order_is_ell_squared']
    assert frob['frobenius_matches'] and frob['tau_sum_has_order_ell']
    result = {
        'large_subgroup': {'ell': inv['prime_subgroup_order'], 'embedding_degree': inv['embedding_degree'],
                           'embedding_degree_bits': inv['embedding_degree_bits'],
                           'ell_minus_1_over_k': inv['embedding_degree_cofactor'],
                           'invariant_on_isogeny_class': True},
        'conductor_prime': {'l': l, 'q_mod_l': q_mod, 't_mod_l': t % l,
                            'frobenius_polynomial_mod_l': '(X - %d)^2' % a,
                            'pi_scalar_order': local['order_of_pi_scalar'],
                            'mu_l_embedding_degree': local['mu_p_embedding_degree']},
        'crater_E0': {'pi_on_E0_l': '%d * I' % a, 'verified_by': 'x(P)^q = x([2514]P) on a point of order 6473',
                      'twist_over_F_Q_l_part': '(Z/6473)^2', 'stable_kernel_lines': lines['kernel_lines'],
                      'x_coordinate_field': 'F_(q^3236)', 'full_torsion_field': 'F_(q^6472)',
                      'torsion_point_ladder_seconds': e0['ladder_seconds']},
        'floor_reference': {'curve_id': 'O00-00', 'pi_on_E_l': '%d * I + N, N nilpotent nonzero' % a,
                            'twist_over_F_Q_l_part': 'Z/6473^2 (a point of order 6473^2 was found)',
                            'stable_kernel_lines': 1, 'full_torsion_field': 'F_(q^%d)' % ((l - 1) * l),
                            'torsion_point_ladder_seconds': floor['ladder_seconds']},
        'ecc2k130_contrast': {'l': 263, 'q_mod_l': 1, 'pi_on_E0_l': '-I',
                              'crater_torsion_field': 'F_(q^2)', 'floor_torsion_field': 'F_(q^526)'},
    }
    (OUT / 'run05-embedding.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
