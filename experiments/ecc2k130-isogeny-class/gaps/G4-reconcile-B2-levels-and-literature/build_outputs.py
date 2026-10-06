#!/usr/bin/env python3
"""G4 parts (3) and (4): assemble levels_reconciled.json and errata.json from the computed files
reconcile_numbers.json, kani_search.json, lit_check.json (this directory) and the on-disk inputs.
Every number below is read from those files or computed here from the stated constants.
Run: export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp; timeout 2400 python3 build_outputs.py
"""
import json, math, os
W = '/Volumes/SSD990/ecdlp-hardness-work'
D = os.path.join(W, 'gaps/G4-reconcile-B2-levels-and-literature')
R = json.load(open(os.path.join(D, 'reconcile_numbers.json')))
S = json.load(open(os.path.join(D, 'kani_search.json')))
L = json.load(open(os.path.join(D, 'lit_check.json')))
T263 = json.load(open(f'{W}/transport-263/summary.json'))
TAB = R['E3']['transport table']
log2 = math.log2
p = 146505763881528721
N = 680564733841876926932320129493409985129
RHO_E0 = 0.5 * log2(math.pi * N / (4 * 131)); RHO_NEG = 0.5 * log2(math.pi * N / 4)
def r(x, k=2): return round(float(x), k)
def eff(T_M, ci=5.0): return log2(2 ** RHO_E0 + T_M / ci)

B = R['B']
cons = B['construction cost of one B2 curve (a2=0,Tr b=1 search, 2^64.937 candidates)']
trials = B['expected trials per hit']
LOG2_TRIALS = trials['a2=0 and Tr(b)=1 prefilter (q/2 candidates)']['log2_trials_level_p_or_263p']
E0M = B['E0 rho cost in F_q-mults (5M / 6M per iteration), log2']
NATM = B['native neg-only rho in F_q-mults (5M / 6M), log2']

def trow(key):
    t = TAB[key]
    out = dict(reference_setting=t['reference_setting'], log2_U_per_unit_C_reference=t['log2_U_reference'],
               log2_U_range_over_settings=t['log2_U_range_over_settings'])
    if t.get('log2_gamma_onetime_reference'): out['log2_gamma_onetime_Fq_mults'] = t['log2_gamma_onetime_reference']
    for C in (9, 100, 1000):
        v = t[f'fixed C={C}: [log2 T ref, eff ref, [eff min, eff max]]']
        out[f'C={C}'] = dict(log2_transport_Fq_mults=v[0], log2_transport_E0rho_equiv=r(v[0] - E0M[0], 2),
                             effective_log2_iters=v[1], effective_range_over_settings=v[2])
    for kappa in (1, 10, 100):
        k = [kk for kk in t if kk.startswith(f'scaled C=kappa*3^D kappa={kappa} ')][0]
        v = t[k]
        out[f'kappa={kappa} ({k.split("(")[1].split(")")[0]})'] = dict(log2_transport_Fq_mults=v[0], effective_log2_iters=v[1],
                                                                      effective_range_over_settings=v[2])
    out['breakeven_C_reference'] = t['breakeven (ref)']
    out['breakeven_C_cheapest_setting'] = t['breakeven (cheapest setting)']
    out['breakeven_C_dearest_setting'] = t['breakeven (dearest setting)']
    return out

transport = {}
for g in ('dim2 (scalar gamma, M=p+a^2)', 'dim2 (horizontal gamma, rt2c)', 'dim4 (two squares)', 'dim8 (four squares, Thm 1 as proved)'):
    for m in ('descended', 'compositum', 'compositum+theta', 'equations'):
        transport[f'{g} | {m}'] = trow(f'{g} | {m}')

# best dim-2 parameter sets (for the record)
best_scalar = S['dim2 scalar gamma (M = p + a^2)|descended|kara|npush=2D']
best_scalar_c = S['dim2 scalar gamma (M = p + a^2)|compositum|kara|npush=2D']
best_h = S['dim2 horizontal-gamma (rt2c type)|pool=split|compositum|kara|npush=2D']

# dim-2 effective interval under "algorithm exists" with kappa in [1, 100] (C = 9 .. 900), all models and settings
def eff_span(prefixes, kappas=(1, 10, 100)):
    lo, hi = 99.0, 0.0
    for key in TAB:
        if not any(key.startswith(pf) for pf in prefixes): continue
        for kappa in kappas:
            kk = [x for x in TAB[key] if x.startswith(f'scaled C=kappa*3^D kappa={kappa} ')][0]
            v = TAB[key][kk]
            lo = min(lo, v[2][0]); hi = max(hi, v[2][1])
    return [r(lo, 3), r(hi, 3)]
span_dim2 = eff_span(['dim2 (scalar', 'dim2 (horizontal'])
span_dim4 = eff_span(['dim4'])
span_dim8 = eff_span(['dim8'])

ln = math.log
thm1_bound = lambda n: 4 * ln(n) * ln(ln(n))
T263_M = T263['transport_cost_log2_M_equiv_upper']['median']

levels = {
 '_meta': dict(
    task='G4 reconcile B2 levels and literature',
    produced_by=['reconcile.py (sage -python, ~80 s)', 'lit_check.py (python3)', 'build_outputs.py (python3)'],
    inputs_read=['p-levels/{conclusions,levels}.json', 'literature/{levels,citations,per_curve}.json',
                 'verify/p-levels/C4-audit/*', 'verify/p-levels/C5-audit/*', 'verify/redteam/RT15-*', 'verify/redteam/RT2-01-*',
                 'redteam-2/raw/*.json', 'transport-263/summary.json', 'verify/codex-crosscheck/C1-audit/horiz_*'],
    units=dict(Fq_mult='one multiplication in F_{2^131}', E0_rho_equiv='cost / (E0 rho cost in F_q-mults), E0 rho = 2^%.3f iterations x 5 M (BBB09: (I-3M)/N + 5M + 21S, squarings free in normal basis); 6 M/iteration shown as sensitivity' % RHO_E0,
               effective_log2='log2 of (E0 rho iterations + transport F_q-mults / 5), i.e. rho-iteration equivalents',
               C='per-step constant: F_{q^K}-multiplications per l^D unit of one (l,...,l)-isogeny step in dimension D (no char-2 implementation exists here; C is scanned); kappa-scaled C = kappa * 3^D reflects the 3^D level-3 theta coordinates needed in char 2 (level must be odd)'),
    E0_rho_log2_iterations=r(RHO_E0, 3), E0_rho_log2_Fq_mults_5M_6M=E0M,
    native_neg_only_rho_log2_iterations=r(RHO_NEG, 3), native_log2_Fq_mults_5M_6M=NATM,
    note_on_class_fraction='levels p and 263p together hold 263(p+1) of 263(p+2) curves = all but 2^-57.02 of the class; level 263p alone holds 262/263 = 99.62%'),
 'constants': dict(q='2^131', t=R['A']['t'], N=R['A']['N'], f='263*p', p=str(p),
                   kronecker_minus7=dict(p=-1, l263=1), class_numbers=R['A']['class numbers h(1),h(263),h(p),h(263p)'],
                   log2_class_numbers=R['A']['log2 class numbers'], r_ord_p_c=R['A']['r = ord_p(c), log2'],
                   r_x=R['A']['r_x (x-coordinate field degree of ker(pi - c)), log2']),
 'levels': {
  '1': dict(conductor='1', end_ring='O_K', class_count='1', log2_class_count=0.0, block='B1',
            construction=dict(method='given: E0 is the Certicom ECC2K-130 curve (j = 1)', log2_Fq_mults=0.0),
            native_rho_log2_iterations=r(RHO_E0, 3), native_rho_note='negation + F_2-Frobenius tau, classes of size 2*131',
            transport_to_E0='identity',
            effective_log2_interval=[r(RHO_E0, 3), r(RHO_E0, 3)],
            endpoint_conditions='both endpoints: parallel rho on <-1,tau>-classes (the BBB09 walk costs 2^60.91 iterations with its 1.069993 non-randomness factor)'),
  '263': dict(conductor='263', end_ring='Z + 263 O_K', class_count='262', log2_class_count=R['A']['log2 class numbers'][1], block='B1',
              construction=dict(method='explicit: roots of H_D mod 2 (D = -7*263^2), equivalently Velu from the 264 subgroups of E0[263] over F_{q^2}; all 262 curves are in ground_truth.json',
                                cost_note='seconds of Sage time (ground-truth build and derive_floor); no bit estimate needed'),
              native_rho_log2_iterations=r(RHO_NEG, 3), native_rho_note='negation only (O_263 has no element of norm 2, so no Frobenius endomorphism)',
              transport_to_E0=dict(method='one ascending 263-isogeny (kernel over F_{q^2}), all 262 transports checked in transport-263/',
                                   log2_Fq_mult_equiv=r(T263_M, 2), log2_E0rho_equiv=r(T263_M - E0M[0], 2), heuristic=False, char2_algorithm='Velu (implemented, run)'),
              effective_log2_interval=[r(RHO_E0, 3), r(eff(2 ** T263_M), 3)],
              endpoint_conditions='both endpoints: E0 rho after a 2^%.2f-mult transport (transport-263/summary.json effective_log2 median %.6f)' % (T263_M, T263['effective_log2']['median'])),
  'p': None, '263p': None},
}

cons_block = dict(
  cheapest_method='random search over y^2+xy=x^3+b with the free prefilter a2 = 0, Tr(b) = 1 (every curve of order 4N has this shape: 4N = 4 mod 8), test [4N]P = O by an x-only ladder; a level-263p hit (262/263 of hits) is moved to level p by one 263-isogeny with kernel over F_{q^2}, so level p costs the same',
  log2_candidates=LOG2_TRIALS,
  candidate_space_comparison=trials,
  per_candidate_test_Fq_mults=dict(lower_bound_131_doublings_x_2M=262, ladder_xP_eq_1_counted=R['B']['executed LD ladder for [4N]P (bits of 4N = 132)']['0']['xP1_M'],
                                   ladder_generic_counted=R['B']['executed LD ladder for [4N]P (bits of 4N = 132)']['0']['generic_M']),
  log2_Fq_mults=dict(lower_bound=cons['lower bound: 131 x-only doublings x 2M']['log2_Fq_mults'],
                     counted_ladder_xP1=cons['ladder with x_P = 1 (valid since Tr b = 1), counted']['log2_Fq_mults'],
                     counted_ladder_generic=cons['ladder generic base point, counted']['log2_Fq_mults'],
                     absurd_floor_1M_per_candidate=cons['floor: 1 M per candidate (no real test)']['log2_Fq_mults']),
  log2_E0rho_equivalents=dict(lower_bound_6M_iter=cons['lower bound: 131 x-only doublings x 2M']['log2 E0-rho equivalents (redteam 6M/iteration)'],
                              counted_ladder_xP1_5M_iter=cons['ladder with x_P = 1 (valid since Tr b = 1), counted']['log2 E0-rho equivalents (BBB09 5M/iteration)'],
                              absurd_floor_1M_per_candidate_6M_iter=cons['floor: 1 M per candidate (no real test)']['log2 E0-rho equivalents (redteam 6M/iteration)']),
  galbraith2024_thm4_figure=dict(log2=65.5, meaning='O~(q^{1/2}) F_q-operations: an asymptotic statement that hides the per-candidate test (a log q factor) and constants; it is not a trial count'),
  other_routes_log2_Fq_ops=dict(descend_from_E0_cofactor_kernel_point_xonly_LB=R['C']['x-only over F_{q^{r/2}} (twist, c^(r/2) = -1): log2(131 * (r/2)^2)'],
                                descend_from_E0_cofactor_full_points=R['C']['full points over F_{q^r}: log2(131 * r^2) [scalar ~131 r bits x F_{q^r}-op >= r F_q-ops]'],
                                Phi_p_Otilde_p2=R['D']['Phi_p via Leroux / Robert / Kunzweiler-Robert O~(p^2 log q): log2 p^2, log2 p^2*131'],
                                Phi_p_cubic_obsolete=R['D']['Phi_p cubic (Gal99-era O(p^3)): log2 p^3'],
                                CM_log2_absD=R['D']['CM: log2 |D| level p = 7p^2, level 263p = 7(263p)^2']),
  construction_costs_more_than_E0_instance=True,
  construction_vs_E0_statement=('YES. One B2 curve costs >= 2^%.2f F_q-mults (2^%.2f candidates x >= 262 M), i.e. >= 2^%.2f E0-rho solves; with the counted ladder 2^%.2f F_q-mults = 2^%.2f E0-rho solves (5 M/iteration). Even a 1-M test would cost 2^%.2f E0-rho solves.'
       % (cons['lower bound: 131 x-only doublings x 2M']['log2_Fq_mults'], LOG2_TRIALS,
          cons['lower bound: 131 x-only doublings x 2M']['log2 E0-rho equivalents (redteam 6M/iteration)'],
          cons['ladder with x_P = 1 (valid since Tr b = 1), counted']['log2_Fq_mults'],
          cons['ladder with x_P = 1 (valid since Tr b = 1), counted']['log2 E0-rho equivalents (BBB09 5M/iteration)'],
          cons['floor: 1 M per candidate (no real test)']['log2 E0-rho equivalents (redteam 6M/iteration)'])))

transport_block_common = dict(
  method='Galbraith ePrint 2024/924 (RNT 11:7, 2025) Thm 1 + Thm 2 with h0 = 1 (the crater is {E0}, so the curve directly above a level-p curve is E0): Kani/Robert representation of the ascending p-isogeny found by a meet-in-the-middle over guesses of its action on E[M1], M = p + m smooth. Asymptotic cost O~(p^{1/2}) = O~(2^%.2f).' % (log2(p) / 2),
  thm1_hypotheses=dict(N_equals_p=dict(smallest_prime_factor=str(p), bound_4lnN_lnlnN=r(thm1_bound(p), 1), ok=True),
                       N_equals_263p=dict(smallest_prime_factor=263, bound_4lnN_lnlnN=r(thm1_bound(263 * p), 1), ok=False,
                                          fix='ascend the 263-step first (kernel over F_{q^2}), then N = p')),
  heuristics=['MITM meets exactly once (Gal24 footnote 8: unique solution expected)',
              'Elkies-prime distribution: removable for bounded |D0| (Gal24 sec 2.1); here D0 = -7 and the needed parameters were found explicitly (kani_search.json)',
              'm a sum of 2 squares (dim 4) / 1 square or horizontal-gamma norm (dim 2): not needed in dim 8; found explicitly here'],
  char2_algorithm_availability=dict(dim2='described in the literature ([BCR10b], cited by Robert ePrint 2024/406 as the characteristic-2 theta-isogeny algorithm, dimension 2 only); not implemented in this work tree; per-step constant unknown',
                                    dim4_dim8='no characteristic-2 algorithm for (l,...,l)-isogenies in dimension 4 or 8 is cited in the texts on disk; algebraic theta theory needs a level prime to the characteristic (odd level, 3^D coordinates)'),
  models=dict(descended='each step has an F_q-rational representation of cost C*l^D in F_{q^K_l}; later-prime basis points are pushed in their own field F_{q^K_j}',
              compositum='step from a kernel basis in F_{q^K_l}; pushing a later prime\'s points needs F_{q^lcm(K_l,K_j)} (RT2-01-1 model)',
              **{'compositum+theta': 'compositum, with every field also containing the level-3 (level-5 for l = 3) theta-structure field (pi-order 8 on E[3], 24 on E[5])',
                 'equations': 'Robert notes CA 2.8 first bullet: step from rational kernel equations in O(l^{D r}) F_q-ops, r = 1 if l = 1 mod 4 else 2; pushes in F_{q^K_j}'}),
  push_count='2D basis points per later prime (reference, as RT2-01-1) or D (sensitivity)',
  field_mult='Karatsuba K^1.585 (reference) or linear K (lower bound)',
  reproduction_of_disk_figures=dict(
      proposer_rt4_dim2=[R['E1']['reproduction of disk figures (per-C costs in F_q-mults; eff with 5M/iteration)']['dim2_c81_A=29.71.137.179 (rt2c horizontal gamma)']['proposer_rt4_log2_C9_100_1000'],
                         R['E1']['reproduction of disk figures (per-C costs in F_q-mults; eff with 5M/iteration)']['dim2_c3_A=11.23.79.107.109 (rt2c horizontal gamma)']['proposer_rt4_log2_C9_100_1000']],
      RT2_01_1_compositum_c81=R['E1']['reproduction of disk figures (per-C costs in F_q-mults; eff with 5M/iteration)']['dim2_c81_A=29.71.137.179 (rt2c horizontal gamma)']['compositum|npush=2D|kara']['log2_T_C9_100_1000'],
      descended_c81=R['E1']['reproduction of disk figures (per-C costs in F_q-mults; eff with 5M/iteration)']['dim2_c81_A=29.71.137.179 (rt2c horizontal gamma)']['descended|npush=2D|kara']['log2_T_C9_100_1000'],
      RT15_1_per_guess_dim2=R['E1']['RT15-1 per-guess dim-2 model on a=34154152 (M=5^2 * 7 * 11^2 * 17 * 127 * 149 * 179 * 281 * 431): log2 T (C=1)'],
      verdict=('The two disputed dim-2 ranges are both arithmetically right for their own models and are reproduced exactly: 2^50.0-2^58.4 is the redteam-2 proposer model (C = 9..1000 over two parameter sets), which charges pushes of later-prime points in the field of the prime being stepped over (not a consistent field model); 2^55.8-2^62.6 is the RT2-01-1 compositum model on the c = 81 set. The descended model on the same set gives 2^51.2-2^58.0. Neither is measured; which applies depends on whether an F_q-rational (descended) step representation is available in characteristic 2.')),
  best_parameters=dict(dim2_scalar_descended=dict(a=best_scalar['a'], M_factorisation=best_scalar['factorisation'], log2_U=best_scalar['log2_U']),
                       dim2_scalar_compositum=dict(a=best_scalar_c['a'], M_factorisation=best_scalar_c['factorisation'], log2_U=best_scalar_c['log2_U']),
                       dim2_horizontal_compositum=dict(c=best_h['c'], A=best_h['A_primes'], m=best_h['m'], max_split_prime_in_gamma=best_h['max_split_prime_in_gamma'], log2_U=best_h['log2_U'], log2_gamma_onetime=best_h['gamma_onetime_log2_Fq_mults'])),
  per_dimension_and_model=transport,
  effective_spans_kappa_1_to_100=dict(dim2=span_dim2, dim4=span_dim4, dim8=span_dim8))

def level_block(which):
    lab = 'p' if which == 'p' else '263p'
    idx = 2 if which == 'p' else 3
    blk = dict(conductor='p' if which == 'p' else '263*p (= conductor of Z[pi])',
               end_ring='Z + p O_K' if which == 'p' else 'Z[pi] = Z + 263p O_K',
               class_count=R['A']['class numbers h(1),h(263),h(p),h(263p)'][idx], log2_class_count=R['A']['log2 class numbers'][idx], block='B2',
               construction=cons_block,
               native_rho_log2_iterations=r(RHO_NEG, 3), native_rho_note='negation only; smallest non-scalar endomorphism has degree 2^114.85 (level p) / 2^130.93 (level 263p) per C4-audit',
               transport_to_E0=transport_block_common if which == 'p' else dict(
                   step1='ascending 263-isogeny to level p: kernel over F_{q^2} (t/2 = -1 mod 263), Velu, cost of the same order as the level-263 transport (2^%.2f F_q-mult equivalents measured there)' % T263_M,
                   step2='as level p (see levels.p.transport_to_E0); Thm 1 cannot be applied with N = 263p directly'),
               effective_log2_interval=[r(RHO_E0, 3), r(RHO_NEG, 3)],
               endpoint_conditions=dict(
                   lower=('%.3f: reached when a characteristic-2 odd-degree (l,l)-isogeny algorithm for abelian surfaces (dimension 2; [BCR10b] per Robert ePrint 2024/406, not implemented here) runs with a small per-step constant: at kappa = 1 (C = 9) every dim-2 model/setting gives at most %.3f; in the descended and horizontal-gamma models even kappa = 100 stays below %.3f. Heuristic parts: MITM uniqueness (the parameters themselves were found explicitly).'
                          % (RHO_E0, max(TAB[k]['scaled C=kappa*3^D kappa=1 (C=9): [log2 T ref, eff ref, [eff min, eff max]]'][2][1] for k in TAB if k.startswith('dim2')),
                             max(TAB[k]['scaled C=kappa*3^D kappa=100 (C=900): [log2 T ref, eff ref, [eff min, eff max]]'][2][1] for k in TAB if k.startswith('dim2') and ('descended' in k or 'horizontal' in k)))),
                   conditional_estimate_if_dim2_algorithm_exists=dict(kappa_1_to_100=span_dim2,
                        note='over all four dim-2 models, both mult models, both push counts; reference compositum (scalar gamma) %.3f at kappa = 1 and %.3f at kappa = 100'
                             % (TAB['dim2 (scalar gamma, M=p+a^2) | compositum']['scaled C=kappa*3^D kappa=1 (C=9): [log2 T ref, eff ref, [eff min, eff max]]'][1],
                                TAB['dim2 (scalar gamma, M=p+a^2) | compositum']['scaled C=kappa*3^D kappa=100 (C=900): [log2 T ref, eff ref, [eff min, eff max]]'][1])),
                   upper=('%.3f: no usable characteristic-2 higher-dimensional isogeny algorithm, or one whose constant exceeds the no-gain threshold (dim 2, scalar-gamma reference: C > %.0f compositum, C > %.0f descended); then the best known attack is native negation-only rho.'
                          % (RHO_NEG, TAB['dim2 (scalar gamma, M=p+a^2) | compositum']['breakeven (ref)']['C_no_gain_vs_native'],
                             TAB['dim2 (scalar gamma, M=p+a^2) | descended']['breakeven (ref)']['C_no_gain_vs_native'])),
                   other_dimensions=('dim 4 (two squares) gives a gain only for C < %.0f (compositum reference, kappa < %.1f) or C < %.0f (descended reference, kappa < %.0f); '
                                     'dim 8 (four squares, the version Gal24 Thm 1 proves) gives effective >= %.1f for kappa >= 1 (C >= 3^8); only an unscaled C = 1 with the most optimistic settings would bring it to %.2f.')
                                    % (TAB['dim4 (two squares) | compositum']['breakeven (ref)']['C_no_gain_vs_native'], TAB['dim4 (two squares) | compositum']['breakeven (ref)']['C_no_gain_vs_native'] / 81,
                                       TAB['dim4 (two squares) | descended']['breakeven (ref)']['C_no_gain_vs_native'], TAB['dim4 (two squares) | descended']['breakeven (ref)']['C_no_gain_vs_native'] / 81,
                                       span_dim8[0], min(TAB[k]['fixed C=1: [log2 T ref, eff ref, [eff min, eff max]]'][2][0] for k in TAB if k.startswith('dim8')))),
               presented_vs_random=('The interval is for a PRESENTED curve. Nobody can currently present one: constructing any B2 curve costs 2^%.2f-2^%.2f E0-rho solves (construction block).'
                                    % (cons_block['log2_E0rho_equivalents']['lower_bound_6M_iter'], cons_block['log2_E0rho_equivalents']['counted_ladder_xP1_5M_iter'])))
    return blk
levels['levels']['p'] = level_block('p')
levels['levels']['263p'] = level_block('263p')
levels['block_bridge_question'] = dict(
  question="Does Galbraith 2024's O~(sqrt p) contradict 'no known method bridges the blocks'?",
  answer=('Yes, for the direction B2 -> B1 on a presented curve: Gal24 Thm 2 (h0 = 1) computes an evaluable representation of the ascending p-isogeny to E0 in O~(p^{1/2}) = O~(2^%.2f) F_q-operations, and Gal24 sec 10 states the resulting reduction of any floor-curve ECDLP to the crater when h0 is small. '
          'No, for polynomial time (JMV05 sec 1.1 and Rob22 sec 4 speak about polynomial time; O~(p^{1/2}) is exponential in log p, so those statements stand as written). '
          'No, for the direction B1 -> B2: Problem B (produce a descended curve with an evaluable map) is O~(q^{1/2}) (Gal24 Thm 4) and Gal24 sec 10 says only two ways are known (N^2 work or guessing), both >= q^{1/2}; concretely >= 2^%.2f F_q-mults here. '
          'Concrete (not asymptotic) cost of the B2 -> B1 bridge depends on a characteristic-2 higher-dimensional isogeny algorithm: see levels.p.transport_to_E0.') % (log2(p) / 2, cons_block['log2_Fq_mults']['lower_bound']))
ctr = transport['dim2 (scalar gamma, M=p+a^2) | compositum']; dtr = transport['dim2 (scalar gamma, M=p+a^2) | descended']
d4c_no_gain = TAB['dim4 (two squares) | compositum']['breakeven (ref)']['C_no_gain_vs_native']; d4d_no_gain = TAB['dim4 (two squares) | descended']['breakeven (ref)']['C_no_gain_vs_native']
rep = R['E1']['reproduction of disk figures (per-C costs in F_q-mults; eff with 5M/iteration)']
levels['disputed_numbers'] = {
 'construction_cost': dict(on_disk=['2^64.94 candidates (C5-audit, rt3_misc)', '2^65.5 (Galbraith Thm 4)', '2^66.94 trials (p-levels/conclusions.json)'],
     recomputed=dict(uniform_b_a2=trials['uniform (b,a2) over 2(q-1) classes (p-levels/conclusions.json)']['log2_trials_level_p_or_263p'],
                     prefiltered=LOG2_TRIALS, galbraith_Otilde_q_half=65.5,
                     Fq_mults=cons_block['log2_Fq_mults'], E0rho_equivalents=cons_block['log2_E0rho_equivalents']),
     verdict=('2^%.2f is the right candidate count: every curve of order 4N has a2 = 0 and Tr(b) = 1 (4N = 4 mod 8; lemma re-verified by brute force for m = 7, 9, 11, 13 and on 12 random curves over F_2^131), so the uniform-(b, a2) count 2^66.94 wastes a factor 4. '
              'Galbraith\'s 2^65.5 is O~(q^{1/2}), an asymptotic figure with the per-candidate test and constants hidden, not a count. The right COST is 2^%.2f-2^%.2f F_q-mults (>= 131 x-only doublings at 2 M, or the executed ladder at 660 M), i.e. 2^%.2f-2^%.2f E0-rho solves.')
             % (LOG2_TRIALS, cons_block['log2_Fq_mults']['lower_bound'], cons_block['log2_Fq_mults']['counted_ladder_xP1'],
                cons_block['log2_E0rho_equivalents']['lower_bound_6M_iter'], cons_block['log2_E0rho_equivalents']['counted_ladder_xP1_5M_iter'])),
 'cofactor_kernel_point_bound': dict(on_disk=[111.9, 113.9],
     recomputed=[R['C']['x-only over F_{q^{r/2}} (twist, c^(r/2) = -1): log2(131 * (r/2)^2)'], R['C']['full points over F_{q^r}: log2(131 * r^2) [scalar ~131 r bits x F_{q^r}-op >= r F_q-ops]']],
     verdict='2^111.9 is the valid lower bound for that route: the kernel x-coordinates lie on the quadratic twist over F_{q^{r/2}} (c^{r/2} = -1), so an x-only ladder over F_{q^{r/2}} suffices; 2^113.9 counts full points over F_{q^r} (and equals Gal24 sec 2.2 O~(k^2 log q) with k = r). Both are 2^50 above E0 rho and bound only kernel-point routes, not the Kani route.'),
 'Phi_p_route': dict(on_disk=['O~(p^2) = 2^114', '2^171'], recomputed=dict(p2=R['D']['Phi_p via Leroux / Robert / Kunzweiler-Robert O~(p^2 log q): log2 p^2, log2 p^2*131'], p3=R['D']['Phi_p cubic (Gal99-era O(p^3)): log2 p^3']),
     verdict='2^114 (2^121 with the log q factor) is current: Gal24 sec 2.2 cites O~(N^2 log q) for Phi_N over any F_q (Leroux; Robert; Kunzweiler-Robert), and sec 8.1 says O~(N^2) was already achievable in 1999. 2^171 = p^3 is the obsolete Gal99 bound. Neither matters for the verdict.'),
 'galbraith_dim2_transport_cost': dict(on_disk=['2^50.0-2^58.4 (redteam-2 rt4)', '2^55.8-2^62.6 (RT2-01-1 compositum)'],
     recomputed=dict(proposer_model_c81=rep['dim2_c81_A=29.71.137.179 (rt2c horizontal gamma)']['proposer_rt4_log2_C9_100_1000'],
                     proposer_model_c3=rep['dim2_c3_A=11.23.79.107.109 (rt2c horizontal gamma)']['proposer_rt4_log2_C9_100_1000'],
                     compositum_c81=rep['dim2_c81_A=29.71.137.179 (rt2c horizontal gamma)']['compositum|npush=2D|kara']['log2_T_C9_100_1000'],
                     descended_c81=rep['dim2_c81_A=29.71.137.179 (rt2c horizontal gamma)']['descended|npush=2D|kara']['log2_T_C9_100_1000'],
                     searched_best=dict(scalar_descended_log2_U=dtr['log2_U_per_unit_C_reference'], scalar_compositum_log2_U=ctr['log2_U_per_unit_C_reference'],
                                        horizontal_compositum_log2_U=best_h['log2_U'], horizontal_gamma_onetime=best_h['gamma_onetime_log2_Fq_mults'])),
     verdict=('Both on-disk ranges are reproduced exactly (C = 9, 100, 1000). The first uses a field model that cannot hold the pushed points, so it is not a valid model. The second (compositum) is the consistent model when each step is computed from a kernel basis; the descended model (F_q-rational step representations) gives 2^51.2-2^58.0 on the same set. '
              'Parameter search: the horizontal-gamma route reaches 2^%.2f per unit C plus a one-time 2^%.2f (compositum reference; the on-disk c = 81 set is 2^%.2f); the scalar-gamma route, which needs no gamma, is 2^%.2f (compositum) / 2^%.2f (descended) per unit C. Every consistent dim-2 model keeps the effective hardness within %.2f bits of E0 for kappa <= 100 (C <= 900). '
              'No figure is measured: none exists until a characteristic-2 dimension-2 (l,l)-isogeny implementation is timed.')
             % (best_h['log2_U'], best_h['gamma_onetime_log2_Fq_mults'], rep['dim2_c81_A=29.71.137.179 (rt2c horizontal gamma)']['compositum|npush=2D|kara']['log2_U'], ctr['log2_U_per_unit_C_reference'], dtr['log2_U_per_unit_C_reference'], span_dim2[1] - RHO_E0)),
 'dims_4_and_8': dict(verdict=('dim 4 (two squares, Galbraith\'s preferred form): gain for C below %.0f (compositum reference) / %.0f (descended); dim 8 (four squares, Thm 1 as proved): effective >= %.1f for kappa >= 1, so no gain. The RT2-01-1 claim "no gain in dim 4 at C = 1000" holds only for the proposer parameter set.')
                          % (d4c_no_gain, d4d_no_gain, span_dim8[0])),
}
json.dump(levels, open(os.path.join(D, 'levels_reconciled.json'), 'w'), indent=1)
print('wrote levels_reconciled.json')

# (2) literature claims L1-L5
# =====================================================================================================
ev = L['evidence']; l3 = L['L3_recheck']
def evl(key): e = ev[key]; return f"{e['source']} lines {e['lines'][:3]}"
hp, h263p = int(R['A']['class numbers h(1),h(263),h(p),h(263p)'][2]), int(R['A']['class numbers h(1),h(263),h(p),h(263p)'][3])
claims = {
 '_note': ('The L1-L5 texts are not on disk (verify/literature/ is empty and literature/*.json has no claim ids). '
           'L1-L4 are checked as summarised in the G4 task text and as written in literature/levels.json; L5 was not specified, '
           'so the two remaining literature assertions in literature/levels.json and literature/per_curve.json are checked as L5a and L5b.'),
 'L1': dict(claim='Block split (JMV05 sec 6): B1 = levels {1, 263} (263 explicit curves) and B2 = levels {p, 263p}; random reducibility across the whole class cannot be proven because P(c_pi) = p is large.',
            verdict='CORRECTED',
            confirmed_part=('JMV05 statements are quoted correctly (%s; %s; %s): no polynomial-time reduction across the p-gap is known, and only B1 is constructible '
                            '(constructing any B2 curve costs >= 2^%.2f F_q-mults = 2^%.2f E0-rho solves, recomputed here).')
                           % (evl('JMV05 sec1.1 no poly-time algorithm produces curves across non-smooth conductor gap'), evl('JMV05 sec6 cannot prove random reducibility for whole class'),
                              evl('JMV05 sec6 constructible subset = levels reachable by Kohel'), cons_block['log2_Fq_mults']['lower_bound'], cons_block['log2_E0rho_equivalents']['lower_bound_6M_iter']),
            correction=('The split is a polynomial-time notion only. Gal24 Thm 2 (%s) gives, for h0 = 1, an O~(h0 N^{1/2}) = O~(2^%.2f) isogeny from E0 to any presented level-p curve, '
                        'and Gal24 sec 10 (%s) spells out the resulting reduction of floor-curve ECDLP to the crater; Gal24 Thm 5 (%s) replaces JMV-style random self-reducibility by one over all but a negligible part of the class in O~(q^{2/5}) plus polylog oracle queries. '
                        'So B2 is not cut off from E0 at below-rho cost; the concrete cost is conditional (levels.p.transport_to_E0).')
                       % (evl('Gal24 Thm2 statement (crater -> E1, O~(h0 N^1/2))'), log2(p) / 2, evl('Gal24 sec10: floor-to-crater isogeny in at most O(q^1/4) when h0 small'),
                          evl('Gal24 sec9 Theorem 5 (random curve in class, O~(q^2/5) + polylog queries)'))),
 'L2': dict(claim='Every known vertical-isogeny method is infeasible for degree p; Rob22 sec 4 lists poly(log l) volcano navigation as open; Sut13 sec 3.3: no vertical l-isogeny algorithm below linear in l.',
            verdict='REFUTED (as stated); the quoted sources are accurate for their date',
            evidence=('Rob22 (%s) and Sut13 (%s) are quoted correctly and Rob22\'s poly(log l) problem is still open. But Gal24 Thm 1 (%s) computes an evaluable representation of an unknown N-isogeny between two GIVEN curves in O~(N^{1/2}); '
                      'with N = p this is the ascending vertical p-isogeny of a presented level-p curve in O~(2^%.2f), with no kernel points and no kernel polynomial. '
                      'Recomputed concrete costs: dim 2 reference %s F_q-mults per unit C (descended / compositum); dim 8 (Thm 1 exactly as proved) >= 2^%.1f even at kappa = 1. '
                      'Infeasibility does hold for (i) any method that outputs kernel data (>= 2^%.2f coefficients), (ii) the cofactor route (>= 2^%.2f), (iii) Phi_p (O~(p^2 log q) = 2^%.2f-2^%.2f; the 2^%.2f cubic figure is obsolete per Gal24 sec 8.1, %s), and (iv) the descending direction from E0 (Problem B, Gal24 Thm 4, %s).')
                     % (evl('Rob22 end of sec4: poly(log l) volcano navigation open'), evl('Sut13 sec3.3: no vertical l-isogeny algorithm below linear in l'),
                        evl('Gal24 Thm1 (representation of unknown N-isogeny in O~(N^1/2))'), log2(p) / 2,
                        [TAB['dim2 (scalar gamma, M=p+a^2) | descended']['log2_U_reference'], TAB['dim2 (scalar gamma, M=p+a^2) | compositum']['log2_U_reference']], span_dim8[0],
                        R['C']['kernel polynomial degree (p-1)/2 (log2), bytes at 131 bits/coeff'][0],
                        R['C']['x-only over F_{q^{r/2}} (twist, c^(r/2) = -1): log2(131 * (r/2)^2)'],
                        R['D']['Phi_p via Leroux / Robert / Kunzweiler-Robert O~(p^2 log q): log2 p^2, log2 p^2*131'][0], R['D']['Phi_p via Leroux / Robert / Kunzweiler-Robert O~(p^2 log q): log2 p^2, log2 p^2*131'][1],
                        R['D']['Phi_p cubic (Gal99-era O(p^3)): log2 p^3'], evl('Gal24 sec8.1: even in 1999 O~(N^2) achievable'), evl('Gal24 Thm4 (Problem B in O~(q^1/2))')),
            also_checked=('CEL21 (%s) computes char-2 isogenies in time quasi-linear in the degree, but needs the codomain model and the isogeny differential (%s), which it obtains by an Elkies-type step of quadratic complexity in the degree (%s): not a shortcut for degree p.'
                          % (evl('CEL21 abstract: char-2 isogenies quasi-linear in degree'), evl('CEL21 sec3: needs Weierstrass model of isogenous curve and the isogeny differential'), evl('CEL21 sec3.2: Elkies normalisation is quadratic in the degree')))),
 'L3': dict(claim='Horizontal graph on level 263 for l = 2, 11, 29 (literature/per_curve.json): l = 2 is the Frobenius / Verschiebung pair X_k <-> X_{k+-1}; l = 11 stays inside each orbit (A000 -> A016, A115); l = 29 crosses orbits (A000 -> B006, B065).',
            verdict='CONFIRMED',
            evidence=('All 262 floor curves checked against the codex-crosscheck C1 results: mismatches l=2: %d, l=11: %d, l=29: %d. The C1 audit checked that Codex run-10 edge sets are Frobenius-shift invariant with all degrees 2 '
                      '(so the A000 and B000 neighbourhoods determine every edge), and recomputed A000/B000/A090/B021/B067/A092 (l = 11) and A000/B021 (l = 29) directly by division polynomials / Velu, all matching. '
                      'l = 2 follows from the label construction j(X_k) = j(X000)^(2^k) in ground_truth.json. E0 has only self-loops for l = 2, 11, 29.')
                     % (l3['l=2']['mismatches'], l3['l=11']['mismatches'], l3['l=29']['mismatches'])),
 'L4': dict(claim='B2 is at least as hard as E0 and not provably equivalent to it.',
            verdict='CORRECTED',
            confirmed_part=('"At least as hard" holds as a best-known-attack statement: every known attack on a presented B2 curve costs >= E0 rho (%.3f): transport-then-rho is E0 rho plus a nonnegative transport, and native rho is %.3f. '
                            'No reduction from E0 to B2 is known below q^{1/2} (Gal24 sec 10, %s), so this is not a reduction-theoretic statement.') % (RHO_E0, RHO_NEG, evl('Gal24 sec10: only two ways crater->floor (N^2 or guessing), each >= q^1/2')),
            correction=('"Not provably equivalent" needs qualifying: the direction B2 -> E0 has a known reduction, Gal24 Thm 2 with h0 = 1, costing O~(p^{1/2}) asymptotically; it is heuristic in the 2-square (dim 4) form '
                        'and in the MITM-uniqueness step, and the Elkies-prime heuristic is removable for |D0| = 7 (%s). What is missing is (a) a cheap reduction E0 -> B2 (Problem B, >= 2^%.2f F_q-mults here) and (b) a characteristic-2 implementation of the higher-dimensional step, which decides whether B2 sits at %.2f or %.2f.')
                       % (evl('Gal24 sec2.1 Elkies-prime heuristic removable when |D0| bounded'), cons_block['log2_Fq_mults']['lower_bound'], RHO_E0, RHO_NEG)),
 'L5a': dict(claim='(reconstructed) Level identification is polynomial time given the factorisation of t^2 - 4q (Rob22 Thm 4.2; BS11 subexponential); within a level, ECDLP is random self-reducible under GRH (JMV05 Cor 1.2), and two given curves are linked in ~sqrt(h) isogeny steps: 2^28.5 (level p), 2^32.5 (level 263p).',
             verdict='CONFIRMED',
             evidence=('%s; Gal24 repeats it (%s); JMV05 Cor 1.2 (%s). sqrt(h) recomputed: log2 sqrt(p+1) = %.2f, log2 sqrt(262(p+1)) = %.2f.'
                       % (evl('Rob22 Thm 4.2 (End(E) in poly time given factorisation of Delta)'), evl('Gal24 sec2: level of any curve easy (BS11 subexp, Rob22b poly once conductor factored)'),
                          evl('JMV05 Cor 1.2 (within level, GRH)'), log2(hp) / 2, log2(h263p) / 2)),
             caveat='The companion sentence in literature/levels.json (moving between B1 and B2 needs a degree-p vertical isogeny with kernel x-coordinates in a degree-2^52.44 extension) is stale for the same reason as L2.'),
 'L5b': dict(claim='(reconstructed) GHS / Weil descent does not apply: ord_131(2) = 130, so the magic number is m in {1, 131} (Menezes-Qu, as restated in GHS02 Thm 2); E0 has m = 1, the 262 floor curves m = 131, and any B2 curve has b outside F_2, hence m = 131.',
             verdict='CONFIRMED',
             evidence='GHS02 Thm 2 (Menezes-Qu) found in literature/raw/ghs2002.txt; GHS02 states the extended isogeny-walk attack only works for composite extension degree. literature/per_curve.json: m = 131 for all 262 floor curves and m = 1 for E0 (counted here).'),
}
json.dump(claims, open(os.path.join(D, 'literature_claims_checked.json'), 'w'), indent=1)
print('wrote literature_claims_checked.json')

# =====================================================================================================
# (4) errata: stale files and fields (NOT edited; listed here)
# =====================================================================================================
PC = json.load(open(f'{W}/p-levels/conclusions.json'))
PL = json.load(open(f'{W}/p-levels/levels.json'))
LL = json.load(open(f'{W}/literature/levels.json'))
LC = json.load(open(f'{W}/literature/citations.json'))
R3 = json.load(open(f'{W}/redteam-2/raw/rt3_misc.json'))
R4 = json.load(open(f'{W}/redteam-2/raw/rt4_transport_cost.json'))
C5 = json.load(open(f'{W}/verify/p-levels/C5-audit/search_cost_out.json'))
C4 = json.load(open(f'{W}/verify/p-levels/C4-audit/c4_numbers.json'))
RT15 = json.load(open(f'{W}/verify/redteam/RT15-presented-level-p-and-263p-curves-1/rt15_summary.json'))
RT201 = json.load(open(f'{W}/verify/redteam/RT2-01-1/raw/s6_summary.json'))
INT = [r(RHO_E0, 3), r(RHO_NEG, 3)]
lp = PC['per_level']['conductor_p']; l263p = PC['per_level']['conductor_263p']
cc = PC['constructing_any_level_p_or_263p_curve']
ctr = transport['dim2 (scalar gamma, M=p+a^2) | compositum']
dtr = transport['dim2 (scalar gamma, M=p+a^2) | descended']
d4c = transport['dim4 (two squares) | compositum']; d8d = transport['dim8 (four squares, Thm 1 as proved) | descended']
E = []
def add(file, field, on_disk, status, replacement, why):
    E.append(dict(file=file, field=field, value_on_disk=on_disk, status=status, replacement=replacement, reason=why))
add('p-levels/conclusions.json', 'per_level."conductor_p".effective_log2', lp['effective_log2'], 'STALE',
    dict(effective_log2_interval=INT, see='levels_reconciled.json levels.p.endpoint_conditions'),
    'Gal24 Thm 2 (h0 = 1) transports a presented level-p curve to E0 at O~(p^1/2); recomputed dim-2 cost puts the effective hardness at 60.81-62.3 if a char-2 dim-2 algorithm exists with C <= 1000, 64.33 only if none does.')
add('p-levels/conclusions.json', 'per_level."conductor_p".transport_to_E0', lp['transport_to_E0'], 'PARTLY STALE',
    'one p-isogeny is still unavoidable (Kohel96 Prop 21), but it need not be computed from kernel points: Gal24 Thm 1 yields an evaluable Kani/Robert representation from E1, E0 and N = p alone',
    'the F_{q^r} kernel-point framing only bounds Velu-type methods.')
add('p-levels/conclusions.json', 'per_level."conductor_p".transport_cost_bounds_log2_Fq_ops', lp['transport_cost_bounds_log2_Fq_ops'], 'STALE (as bounds on transport)',
    {'sqrt-Velu (needs kernel points)': lp['transport_cost_bounds_log2_Fq_ops'].get('sqrt-Velu over F_{q^(r/2)} (LB, linear-cost ext. arithmetic)'),
     'cofactor kernel point, x-only over F_{q^(r/2)} (tighter valid LB of that route)': R['C']['x-only over F_{q^{r/2}} (twist, c^(r/2) = -1): log2(131 * (r/2)^2)'],
     'Phi_p, O~(p^2 log q) (Gal24 sec 2.2)': R['D']['Phi_p via Leroux / Robert / Kunzweiler-Robert O~(p^2 log q): log2 p^2, log2 p^2*131'],
     'Kani route, dim 2, per unit C (descended / compositum reference)': [dtr['log2_U_per_unit_C_reference'], ctr['log2_U_per_unit_C_reference']]},
    'each figure bounds one route only; the Kani route is not covered by any of them. The 171 (= 3 log2 p) Phi_p figure is the obsolete cubic bound (Gal24 sec 8.1); 113.91 counts full points over F_{q^r}, 111.91 is the x-only count.')
add('p-levels/conclusions.json', 'per_level."conductor_p".caveat', lp['caveat'], 'STALE',
    'A known algorithm (Gal24 Thm 2, O~(p^1/2), small memory: guess tree or a 2^%.1f-entry MITM table in the scalar dim-2 route) makes E0 rho + transport ~ %.2f-%.2f under a dim-2 char-2 algorithm with kappa <= 100.' % (S['dim2 scalar gamma (M = p + a^2)|compositum|kara|npush=2D']['log2_table_entries'], span_dim2[0], span_dim2[1]),
    '"No such algorithm is known" was true for quasi-linear kernel-polynomial methods only.')
add('p-levels/conclusions.json', 'per_level."conductor_263p".effective_log2', l263p['effective_log2'], 'STALE',
    dict(effective_log2_interval=INT), 'same as level p after one cheap 263-ascent (kernel over F_{q^2}).')
add('p-levels/conclusions.json', 'per_level."conductor_263p".transport_to_E0', l263p['transport_to_E0'], 'STALE',
    'ascend 263 (cheap) to level p, then Kani with N = p (Thm 1 cannot take N = 263p: 263 < 4 ln N ln ln N = %.0f)' % thm1_bound(263 * p),
    'the p-step has no F_{q^r} obstruction in the Kani route.')
add('p-levels/conclusions.json', 'per_level."conductor_263 (A000..B130)".effective_log2', PC['per_level']['conductor_263 (A000..B130)']['effective_log2'], 'CONFIRMED (update note only)',
    r(T263['effective_log2']['median'], 6), 'transport-263/summary.json re-derived it: median effective 60.809037 with a 2^15.55-mult transport.')
add('p-levels/conclusions.json', 'constructing_any_level_p_or_263p_curve.random_search_log2_trials_level_p_or_263p', cc['random_search_log2_trials_level_p_or_263p'], 'CORRECTED',
    LOG2_TRIALS, '66.94 counts uniform (b, a2) over 2(q-1) classes; the free prefilter a2 = 0, Tr(b) = 1 (verified by brute force for m = 7..13 and on F_2^131) removes a factor 4.')
add('p-levels/conclusions.json', 'constructing_any_level_p_or_263p_curve.random_search_log2_trials_level_p', cc['random_search_log2_trials_level_p'], 'CORRECTED',
    LOG2_TRIALS, 'any level-263p hit is moved to level p by one 263-isogeny (kernel over F_{q^2}), so a level-p curve costs the same as a B2 curve, not 2^74.98 (or 2^72.98 prefiltered) trials.')
add('p-levels/conclusions.json', 'constructing_any_level_p_or_263p_curve.status', cc['status'], 'CORRECTED',
    'no level-p or level-263p curve can be constructed with fewer than 2^%.2f candidate tests, i.e. >= 2^%.2f F_q-mults (>= 2^%.2f E0-rho solves)' % (LOG2_TRIALS, cons_block['log2_Fq_mults']['lower_bound'], cons_block['log2_E0rho_equivalents']['lower_bound_6M_iter']),
    'trial count and per-test cost recomputed (test cost counted by executing the ladder: 660 M with x_P = 1, 792 M generic).')
add('p-levels/levels.json', 'levels.LEVEL_263p.ascending_263_kernel', PL['levels']['LEVEL_263p']['ascending_263_kernel'], 'STALE (annotation)',
    'cheap step to level p; it is the required first step of the Kani transport for level 263p', '"(does not help)" no longer holds.')
for key, name in (('146505763881528721', 'level p'), ('38531015900842053623', 'level 263p')):
    add('literature/levels.json', f'"{key}".literature_implication', LL[key]['literature_implication'], 'REFUTED IN PART',
        'keep: degree-p isogeny unavoidable (Kohel96, JMV05 Thm 2.1(5), Gal99 Prop 1) and no poly-time bridge (JMV05); replace "outside every known reduction to E0" / "infeasible" by: Gal24 Thm 2 reduces a presented %s curve to E0 in O~(p^1/2); concrete cost conditional on a char-2 higher-dimensional isogeny algorithm' % name,
        'literature/citations.json has no entry for Gal24, GGR25 or Robert 2024/406, so the 2024-2025 results were not considered.')
    add('literature/levels.json', f'"{key}".log2_iterations_best_known', LL[key]['log2_iterations_best_known'], 'STALE',
        dict(effective_log2_interval=INT), 'see levels_reconciled.json.')
    add('literature/levels.json', f'"{key}".identification_vs_navigation', LL[key]['identification_vs_navigation'], 'PARTLY STALE',
        'identification part confirmed (Rob22 Thm 4.2); navigation part: Sut13 sec 3.3 (2012) is superseded for the ascending direction by Gal24 Thm 1/2, which needs no kernel x-coordinates; Rob22 sec 4 poly(log l) problem still open',
        'kernel-field degree 2^52.44 is irrelevant to the Kani route.')
add('literature/levels.json', 'global.log2_prob_random_curve_over_Fq_lands_in_B2', LL['global']['log2_prob_random_curve_over_Fq_lands_in_B2'], 'CONTEXT (not an error)',
    {'per_uniform_(b,a2)': LL['global']['log2_prob_random_curve_over_Fq_lands_in_B2'], 'per_prefiltered_candidate': -LOG2_TRIALS},
    'correct for a uniform (b, a2); the construction cost should use the prefiltered 2^-64.94.')
add('literature/citations.json', '(missing entries)', sorted(LC.keys()), 'INCOMPLETE',
    ['Gal24: S. D. Galbraith, Climbing and descending tall isogeny volcanos, ePrint 2024/924 (RNT 11:7, 2025): Thm 1, 2, 4, 5 and secs 2.2, 8.1, 10',
     'GGR25: Galbraith, Gilchrist, Robert, Improved algorithms for ascending isogeny volcanoes, ePrint 2025/1243',
     'RobNotes24: D. Robert, ePrint 2024/406 notes (char-2 theta isogenies only in dimension 2 via [BCR10b]; Complexity Analysis 2.8)',
     'CEL21: Caruso, Eid, Lercier, Fast computation of elliptic curve isogenies in characteristic two, arXiv 2003.06367'],
    'these are the sources that change the B2 verdict (read in verify/p-levels/C4-audit/lit/).')
add('literature/citations.json', 'Sut13.results."sec 3.3" and Rob22.results."end of sec 4"', [LC['Sut13']['results']['sec 3.3'], LC['Rob22']['results']['end of sec 4']], 'ACCURATE BUT SUPERSEDED',
    'add: an O~(l^1/2) evaluable representation of the ascending vertical isogeny exists for presented curves (Gal24 Thm 1/2)', 'quotes checked against the texts (lit_check.json).')
add('redteam-2/raw/rt3_misc.json', 'random_search_cost_log2_M', R3['random_search_cost_log2_M'], 'SLIGHTLY HIGH',
    [cons_block['log2_Fq_mults']['counted_ladder_xP1'], cons_block['log2_Fq_mults']['counted_ladder_generic']],
    'implies ~2^%.1f M per test; the executed ladder counts 660 M (x_P = 1) or 792 M.' % (R3['random_search_cost_log2_M'] - LOG2_TRIALS))
add('verify/p-levels/C5-audit/search_cost_out.json', 'log2 F_q mults rho E0 (8/iter assumed) ; log2 ratio search/rho', [C5['log2 F_q mults rho E0 (8/iter assumed)'], C5['log2 ratio search/rho']], 'INCONSISTENT ASSUMPTION',
    dict(E0_rho_log2_Fq_mults_5M=E0M[0], ratio_log2=r(C5['log2 F_q mults random search'] - E0M[0], 3)),
    'BBB09 gives (I-3M)/N + 5M + 21S per iteration (squarings free in normal basis), not 8 M.')
add('redteam-2/raw/rt4_transport_cost.json', 'all rows (dim2 c81, dim2 c3, dim4)', {k: v for k, v in R4.items() if k.startswith('dim')}, 'MODEL-INCONSISTENT (numbers reproduced exactly)',
    dict(compositum_c81=levels['levels']['p']['transport_to_E0']['reproduction_of_disk_figures']['RT2_01_1_compositum_c81'],
         descended_c81=levels['levels']['p']['transport_to_E0']['reproduction_of_disk_figures']['descended_c81']),
    'pushes of later-prime points are charged in the field of the prime being stepped over, which cannot hold them; consistent models are compositum or descended.')
add('verify/redteam/RT15-presented-level-p-and-263p-curves-1/rt15_summary.json', '"dim4 optimistic (C4 example M)" and "dim8 optimistic (C4 example M; Thm 1 as proved)"',
    {k: RT15[k]['log2 transport F_q-mults'] for k in ('dim4 optimistic (C4 example M)', 'dim8 optimistic (C4 example M; Thm 1 as proved)')}, 'SUPERSEDED (single example parameter set, per-guess model)',
    dict(dim4_descended_ref_log2_U=transport['dim4 (two squares) | descended']['log2_U_per_unit_C_reference'], dim4_compositum_ref_log2_U=d4c['log2_U_per_unit_C_reference'],
         dim8_descended_ref_log2_U=d8d['log2_U_per_unit_C_reference']),
    'searched parameters; the dim-8 no-gain conclusion stands, the dim-4 one depends on C.')
add('verify/redteam/RT2-01-1/raw/s6_summary.json', 'proposer_dim4.compositum_kara.eff_iters_C100_C1000_C10000', RT201['proposer_dim4']['compositum_kara']['eff_iters_C100_C1000_C10000'], 'PARAMETER-SPECIFIC',
    dict(searched_dim4_compositum_ref_eff_C100=d4c['C=100']['effective_log2_iters'], C1000=d4c['C=1000']['effective_log2_iters'], no_gain_C=d4c['breakeven_C_reference']['C_no_gain_vs_native']),
    '"no gain in dim 4 at C = 1000" holds for the proposer set [23,37,53,67,137]; the searched set still gains ~1.3 bits at C = 1000 and loses only above C ~ 2.8e3.')
add('verify/p-levels/C4-audit/c4_numbers.json', 'log2(p^3) [Phi_p route]', C4['log2(p^3)            [Phi_p route]'], 'OBSOLETE FIGURE (context)',
    C4['log2(p^2)            [Couveignes/De Feo O~(l^2) route, not listed in C4]'], 'Gal24 sec 2.2 / 8.1: O~(N^2 log q) for Phi_N over any F_q.')
errata = dict(_note=('Files are NOT edited (read-only for this task). Each entry names a stale or disputed field, its current value, and the replacement from levels_reconciled.json / reconcile_numbers.json. '
                     'Also: the G4 task header calls levels p and 263p "99.6% of the class"; together they are all but 2^-57.02 of it (263(p+1) of 263(p+2)); 99.62% is level 263p alone.'),
              entries=E, n_entries=len(E))
json.dump(errata, open(os.path.join(D, 'errata.json'), 'w'), indent=1)
print('wrote errata.json with', len(E), 'entries')
