# Final step only: compare my per-order minima with the prior sweep's result files (data only, no code reuse).
import json, math
P = json.load(open('sweep_py.json'))['per_d']
out = {}
for key, fn, w_note in (('O263', 'cvp_O263.json', 'prior basis (1, omega_263=132+263tau): x_mine = x_prior + 132*y'),
                        ('OK', 'cvp_OK.json', 'prior basis (1, omega=1+tau): x_mine = x_prior + y')):
    J = json.load(open('/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms/' + fn))
    tab = J['per_order_table']
    rows = tab if isinstance(tab, list) else list(tab.values())
    shift = 132 if key == 'O263' else 1
    n = 0; maxdev = 0.0; elem_same = 0; elem_diff = []
    for r in rows:
        d = str(r['d']); mine = P[d][key]
        if r['min_norm_log2'] is None:
            continue
        n += 1
        maxdev = max(maxdev, abs(r['min_norm_log2'] - mine['log2_min']))
        xp, yp = int(r['argmin_xy'][0]), int(r['argmin_xy'][1])
        xm, ym = int(mine['argmin_xy'][0]), int(mine['argmin_xy'][1])
        if (xp + shift * yp, yp) == (xm, ym):
            elem_same += 1
        else:
            elem_diff.append(int(d))
    out[key] = {'basis_note': w_note, 'prior_w': J.get('w'), 'orders_compared': n, 'max_abs_log2_diff_per_order_min': maxdev,
                'argmin_identical_element': elem_same, 'argmin_differs_at_d': elem_diff,
                'prior_overall': J['smallest_norm_over_all_orders_3..2^20_y_nonzero']}
    print(key, {k: v for k, v in out[key].items() if k != 'prior_overall'})
json.dump(out, open('compare_prior.json', 'w'), indent=1)
# exact norms at the orders where the argmin element differs (ties?)
N = 680564733841876926932320129493409985129
for key, fn, m, shift in (('O263', 'cvp_O263.json', 263, 132), ('OK', 'cvp_OK.json', 1, 1)):
    J = json.load(open('/Volumes/SSD990/ecdlp-hardness-work/rho-endomorphisms/' + fn))
    rows = J['per_order_table'] if isinstance(J['per_order_table'], list) else list(J['per_order_table'].values())
    ties = []
    for r in rows:
        if r['d'] in out[key]['argmin_differs_at_d']:
            xp, yp = int(r['argmin_xy'][0]), int(r['argmin_xy'][1])
            x, y = xp + shift * yp, yp
            nprior = x * x - m * x * y + 2 * m * m * y * y
            ties.append((r['d'], nprior == int(P[str(r['d'])][key]['min'])))
    out[key]['exact_norm_equal_at_differing_argmins'] = ties
    print(key, ties)
json.dump(out, open('compare_prior.json', 'w'), indent=1)
