# Cross-implementation check: exact Python sweep (cvp2d) vs float C sweep (cvpsweep.c, PARI basis) for d < 2^20.
import json, math
P = json.load(open('sweep_py.json'))['per_d']
out = {}
for m, key in ((263, 'O263'), (1, 'OK')):
    Cj = json.load(open('sweep_c_lt20_m%d.json' % m))
    Cd = Cj['per_d']
    mism_count = 0; mism_min = []; comp = 0; maxdev = 0.0; skipped = []
    hist_mism = 0
    for d, e in P.items():
        pe = e[key]; ce = Cd[d]
        if pe['count'] != ce['count']:
            mism_count += 1
        pmin = int(pe['min'])
        if pmin < 2 ** 60:
            skipped.append(int(d)); continue
        comp += 1
        if int(ce['exact_norm_at_argk']) != pmin:
            mism_min.append((int(d), pe['log2_min'], ce['exact_log2']))
        maxdev = max(maxdev, abs(ce['min_log2_float'] - pe['log2_min']))
        # histograms (floor log2) : python uses exact bit_length, C uses ilogb of float -> may differ at bin edges
        ph = pe['hist_floorlog2']; ch = ce['hist']
        diff = sum(abs(ph.get(b, 0) - ch.get(b, 0)) for b in set(ph) | set(ch))
        hist_mism += diff
    # flagged (C) vs python lists below threshold
    flog = Cj['flag_log2']
    pyset = set()
    for d, e in P.items():
        if key == 'OK':
            for k, x, y, v in e['OK']['below2_100']:
                pyset.add((int(d), k, x, y, v))
    cset = set((f['d'], f['k'], f['xy'][0], f['xy'][1], f['exact_norm']) for f in Cj['flagged'])
    out[key] = {'d_compared': comp, 'd_skipped_tiny_min': sorted(skipped), 'count_mismatches': mism_count,
                'min_mismatches': mism_min, 'max_abs_log2_dev_float_vs_exact': maxdev,
                'hist_bin_total_abs_diff': hist_mism, 'n_flagged_C': len(cset),
                'flagged_equal_python_below2_100': (cset == pyset) if key == 'OK' else None,
                'C_flagged_exact_log2': sorted(f['log2_exact'] for f in Cj['flagged'])[:12]}
    print(key, json.dumps(out[key])[:1500])
json.dump(out, open('compare_py_c_lt20.json', 'w'), indent=1)
