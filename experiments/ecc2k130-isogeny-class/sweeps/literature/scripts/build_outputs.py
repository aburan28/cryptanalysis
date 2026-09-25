# Assemble per_curve.json and levels.json from the raw computations (no new math here).
import json, sys
sys.path.insert(0, '/Volumes/SSD990/ecdlp-hardness-work/ground_truth')
import ecc2k
W = '/Volumes/SSD990/ecdlp-hardness-work/literature/'
F = json.load(open(W + 'raw/level_facts.json'))
S = json.load(open(W + 'raw/level263_structure.json'))
G = S['global']; PC = S['per_curve']
rho_nf = round(G['log2_rho_neg_frob'], 2); rho_n = round(G['log2_rho_neg_only'], 2)
rho_bbb = round(G['log2_rho_neg_frob_BBB_walk_factor_1.069993'], 2)
per = {}
for lab in ecc2k.LABELS:
    r = ecc2k.RECORDS[lab]; pc = PC[lab]
    d = {
        'orbit': r['orbit'], 'frob_index': r['frob_index'], 'level_conductor': r['level'],
        'end_ring': 'O_K = Z[(1+sqrt(-7))/2]' if lab == 'E0' else 'O_263 = Z + 263*O_K',
        'jmv_block': 'B1 = levels {1, 263} (263 curves, all explicitly known)',
        'small_isogeny_neighbours_computed': {f'l={l}': pc[f'phi{l}_rational_roots'] for l in (2, 11, 29)},
        'ghs_magic_number_m_computed': pc['ghs_m'],
        'ghs_cover_genus': pc['ghs_genus_bound'],
    }
    if lab == 'E0':
        d.update({
            'native_best_known_attack': 'parallel Pollard rho on orbits of <-1, Frobenius sigma> (size 2*131) [WZ98, GLV00, DGM99, BBB+09]',
            'native_log2_iterations': rho_nf,
            'native_log2_iterations_BBB09_walk': rho_bbb,
            'effective_log2_iterations_best_known': rho_nf,
            'reduction_to_E0': 'identity',
            'relative_to_E0': 'baseline',
        })
    else:
        d.update({
            'native_best_known_attack': 'parallel Pollard rho with negation only (Aut = {+-1}; End = O_263 has no element of norm 2, so no Frobenius endomorphism) [WZ98, BLS11]',
            'native_log2_iterations': rho_n,
            'effective_best_known_attack': 'map (P, Q) to E0 by the unique ascending 263-isogeny (degree coprime to N), then Frobenius+negation rho on E0',
            'effective_log2_iterations_best_known': rho_nf,
            'transfer_cost': 'one degree-263 isogeny evaluation per point: O(263) field operations with Velu on the quadratic twist over F_q (Frobenius acts as -1 = t/2 mod 263 on E[263]); negligible vs 2^60.8',
            'reduction_to_E0': 'polynomial time both ways: ascending 263-isogeny (JMV05 Thm 2.2 / Kohel96 Prop 23: exactly one up isogeny) and its dual',
            'relative_to_E0': 'equal (polynomial-time equivalent); native rho is 2^%.2f slower, but the transfer removes that gap' % (rho_n - rho_nf),
        })
    per[lab] = d
json.dump(per, open(W + 'per_curve.json', 'w'), indent=1)

h = F['class_numbers_formula']; p = F['p']; f = F['f']
levels = {
 '1': {'conductor': '1', 'end_ring': 'O_K', 'class_number': h['1'], 'block': 'B1',
       'explicitly_constructible': True,
       'literature_implication': 'Only curve at the top; the Koblitz structure (defined over F_2) gives the sqrt(131) Frobenius speedup [WZ98, GLV00, DGM99]. Best known attack: rho on <-1,sigma> orbits.',
       'log2_iterations_best_known': rho_nf, 'log2_iterations_BBB09_walk': rho_bbb},
 '263': {'conductor': '263', 'end_ring': 'Z + 263 O_K', 'class_number': h['263'], 'block': 'B1',
       'explicitly_constructible': True,
       'literature_implication': 'Polynomial-time equivalent to E0: one ascending 263-isogeny each (JMV05 Thm 2.2, Kohel96 Prop 23); 263 is far below JMV\'s (log q)^(2+delta) bound, and JMV05 sec. 6 treats levels bridged by Kohel\'s algorithm as one unit. Within the level, horizontal 2-isogenies (Frobenius) and 29-isogenies connect all 262 (computed). Hardness = E0 up to O(263)-operation transfer.',
       'log2_iterations_native': rho_n, 'log2_iterations_best_known': rho_nf},
 str(p): {'conductor': 'p', 'end_ring': 'Z + p O_K', 'class_number': h[p], 'block': 'B2',
       'kron_-7_p': F['kron_-7_p'],
       'explicitly_constructible': False,
       'literature_implication': 'Outside every known reduction to E0: any isogeny to levels 1/263 has degree divisible by p ~ 2^57 (Kohel96 Prop 21-22, JMV05 Thm 2.1(5), Gal99 Prop 1); p is not polylog(q) so JMV05 Cor 1.2 does not bridge it (JMV05 sec. 6 names exactly this situation for Koblitz CM classes). Within the level: random self-reducible under GRH (JMV05 Cor 1.2), and two given curves are linked in ~sqrt(h) ~ 2^28.5 isogeny steps (Gal99, GHS02, Galbraith-Stolbunov). Bridged to level 263p by 263-isogenies (polynomial time). Best known attack: rho with negation only.',
       'log2_iterations_best_known': rho_n},
 str(f): {'conductor': '263*p (= conductor of Z[pi])', 'end_ring': 'Z[pi]', 'class_number': h[f], 'block': 'B2',
       'explicitly_constructible': False,
       'literature_implication': 'Same as level p (one up 263-isogeny to level p, polynomial time; one up p-isogeny to level 263, infeasible). Holds ~99.6% of all curves in the isogeny class. Within-level path finding ~sqrt(h) ~ 2^32.5 steps.',
       'log2_iterations_best_known': rho_n},
 'global': {
   'total_curves_in_isogeny_class_one_twist_per_j': F['total_curves_in_isogeny_class'],
   'log2_total': F['log2_total'],
   'log2_fraction_in_block_B1': F['log2_fraction_levels_1_263'],
   'log2_prob_random_curve_over_Fq_lands_in_B2': G['log2_prob_random_curve_in_p_levels'],
   'p_isogeny_kernel': {'ord_frobenius_eigenvalue_mod_p': G['ord_lambda_mod_p'],
                        'x_coordinate_field_degree_over_Fq': G['x_coord_field_degree_over_Fq'],
                        'log2_bits_one_kernel_x_coordinate': G['log2_bits_one_kernel_x_coordinate'],
                        'kernel_polynomial_degree': G['kernel_poly_degree'],
                        'kernel_polynomial_irreducible_factors_over_Fq': G['kernel_poly_irreducible_factors'],
                        'log2_bits_kernel_polynomial': G['log2_bits_kernel_polynomial']},
   'embedding_degree_ord_N_q': F['embedding_degree_N'], 'log2_embedding_degree': F['log2_embedding_degree'],
   'p_plus_1_factor': G['p_plus_1_factor'],
   'rho_log2': {'neg_frob': rho_nf, 'neg_frob_BBB09_walk': rho_bbb, 'neg_only': rho_n},
 }}
json.dump(levels, open(W + 'levels.json', 'w'), indent=1)
print('wrote', len(per), 'curves')
