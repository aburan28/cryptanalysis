#!/usr/bin/env python3
"""Verify frozen scattered-pair matching on a fresh scalar panel."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent


def sha256(data): return hashlib.sha256(data).hexdigest()


def matching(adjacency):
    @lru_cache(None)
    def solve(mask):
        if not mask: return ()
        bit = mask & -mask
        i = bit.bit_length() - 1
        rest = mask ^ bit
        best = solve(rest)
        candidates = adjacency[i] & rest
        while candidates:
            partner = candidates & -candidates
            j = partner.bit_length() - 1
            trial = ((i, j),) + solve(rest ^ partner)
            if len(trial) > len(best): best = trial
            candidates ^= partner
        return best
    return solve((1 << len(adjacency)) - 1)


def add(a, b): return a[0] + b[0], a[1] + b[1]


def pattern_coeff(pat, digits, tau):
    if not pat: return (0, 0)
    pos, digit = divmod(pat - 1, 18)
    value = digits[digit]
    for _ in range(pos): value = tau(*value)
    return value


def tau_power(value, n, tau):
    for _ in range(n): value = tau(*value)
    return value


def apply_unit_point(point, code, beta, modulus):
    if point is None: return None
    x, y = point
    x = x * pow(beta, code % 3, modulus) % modulus
    if code >= 3: y = -y % modulus
    return x, y


def panel(repo, design_path, inputs_path, output):
    sys.path[:0] = [str(repo), str(HERE)]
    from make_tau3_fused import build, recode, block_pattern, tau, unit
    from run import representatives, point_add, point_mul
    from make_tau3_scatter_design import unit_maps

    design_blob, inputs_blob = design_path.read_bytes(), inputs_path.read_bytes()
    design, inputs = json.loads(design_blob), json.loads(inputs_blob)
    assert inputs['design_sha256'] == sha256(design_blob)
    designs = {x['curve']: x for x in design['records']}
    digits, residue, *_ = build()
    maps = unit_maps(digits, unit)
    rows = []
    for case in inputs['cases']:
        name = case['curve']['name']; config = designs[name]
        selected = {(i,j,u,v) for i,j,u,v in config['entries']}
        order, modulus, b = (case['curve'][key] for key in ('order','p','b'))
        point = int(case['base_x']), int(case['base_y'])
        # The same curve/point in the earlier fixture provides the native
        # endomorphism eigenvalue. Its complement is omega's eigenvalue.
        old = json.loads((repo / 'compact-pos-panel.json').read_text())
        field = next(row['fields'] for row in old['rows']
                     if row['case_id'] == case['id'] and row['mode'] == 'pos-compact')
        endo_lambda = int(field['endo_lambda'])
        omega_eigen = (order - endo_lambda) % order
        beta0 = next(pow(g, (modulus - 1)//3, modulus) for g in range(2, 100)
                     if pow(g, (modulus - 1)//3, modulus) != 1)
        omega_point = point_mul(point, omega_eigen, modulus, b)
        beta = next(v for v in (beta0, beta0 * beta0 % modulus)
                    if (v * point[0] % modulus, point[1]) == omega_point)
        scalar_path = inputs_path.parent / case['scalar_file']
        blob = scalar_path.read_bytes()
        assert sha256(blob) == case['scalar_file_sha256']
        base_adds = new_adds = matched = coeff_checks = point_checks = 0
        counts = [0] * 4
        for index, (scalar,) in enumerate(struct.iter_unpack('<Q', blob)):
            _, a, c = min(representatives(order, omega_eigen, scalar), key=lambda x: x[0])
            seq = recode(a, c, digits, residue)
            patterns = [block_pattern((seq[i:i+3] + [0]*3)[:3]) for i in range(0,len(seq),3)]
            blocks = [(i,v) for i,v in enumerate(patterns) if v]
            baseline = sum(bool(patterns[i] or (patterns[i+1] if i+1 < len(patterns) else 0))
                           for i in range(0,len(patterns),2))
            adj = [0]*len(blocks)
            for x,(i,u) in enumerate(blocks):
                for y in range(x+1,len(blocks)):
                    j,v = blocks[y]
                    rep = min((mapping[u],mapping[v]) for mapping in maps)
                    if i//2 == j//2 or (i,j,*rep) in selected:
                        adj[x] |= 1 << y; adj[y] |= 1 << x
            pairs = matching(adj)
            paired = {z for pair in pairs for z in pair}
            cost = len(blocks)-len(pairs)
            assert cost <= baseline
            base_adds += baseline; new_adds += cost; matched += len(pairs)
            counts[min(3,len(pairs))] += 1
            coeff_sum = (0,0)
            group_sum = None
            group_check = index < 16 or index % 512 == 0
            for x,y in pairs:
                (i,u),(j,v) = blocks[x],blocks[y]
                rep = min((mapping[u],mapping[v]) for mapping in maps)
                code = next(code for code,mapping in enumerate(maps)
                            if (mapping[rep[0]],mapping[rep[1]]) == (u,v))
                rep_coeff = add(tau_power(pattern_coeff(rep[0],digits,tau),3*i,tau),
                                tau_power(pattern_coeff(rep[1],digits,tau),3*j,tau))
                actual_coeff = unit(*rep_coeff,code)
                direct_coeff = add(tau_power(pattern_coeff(u,digits,tau),3*i,tau),
                                   tau_power(pattern_coeff(v,digits,tau),3*j,tau))
                assert actual_coeff == direct_coeff
                coeff_sum = add(coeff_sum,actual_coeff)
                if group_check:
                    krep = (rep_coeff[0]+rep_coeff[1]*(1+endo_lambda))%order
                    prepared = point_mul(point,krep,modulus,b)
                    group_sum = point_add(group_sum,apply_unit_point(prepared,code,beta,modulus),modulus,b)
            for x,(i,u) in enumerate(blocks):
                if x in paired: continue
                rep = min(mapping[u] for mapping in maps)
                code = next(code for code,mapping in enumerate(maps) if mapping[rep] == u)
                rep_coeff = tau_power(pattern_coeff(rep,digits,tau),3*i,tau)
                actual_coeff = unit(*rep_coeff,code)
                direct_coeff = tau_power(pattern_coeff(u,digits,tau),3*i,tau)
                assert actual_coeff == direct_coeff
                coeff_sum = add(coeff_sum,actual_coeff)
                if group_check:
                    krep = (rep_coeff[0]+rep_coeff[1]*(1+endo_lambda))%order
                    prepared = point_mul(point,krep,modulus,b)
                    group_sum = point_add(group_sum,apply_unit_point(prepared,code,beta,modulus),modulus,b)
            assert coeff_sum == (a,c)
            assert (coeff_sum[0]+coeff_sum[1]*(1+endo_lambda))%order == scalar%order
            coeff_checks += 1
            if group_check:
                assert group_sum == point_mul(point,scalar,modulus,b)
                point_checks += 1
        rows.append({'case_id':case['id'],'curve':name,'scalars':coeff_checks,
                     'base_adds':base_adds,'scatter_adds':new_adds,'add_savings':base_adds-new_adds,
                     'matched_pairs':matched,'point_checks':point_checks,
                     'point_entries':config['total_point_entries'],
                     'full6_point_entries':config['full6_point_entries'],
                     'matched_count_histogram_0_1_2_3plus':counts,
                     'verified':True})
        print(json.dumps(rows[-1],sort_keys=True),flush=True)
    report={'schema':1,'status':'verified_prospective_operation_panel',
            'cpu_timing_claim':None,'design_sha256':sha256(design_blob),
            'inputs_sha256':sha256(inputs_blob),'source_sha256':sha256(Path(__file__).read_bytes()),
            'rows':rows}
    content=json.dumps(report,indent=2,sort_keys=True).encode()+b'\n'
    output.write_bytes(content)
    return {'output_sha256':sha256(content),'rows':len(rows),
            'coefficient_checks':sum(r['scalars'] for r in rows),
            'point_checks':sum(r['point_checks'] for r in rows)}


if __name__=='__main__':
    if len(sys.argv)!=5: raise SystemExit('usage: check_tau3_scatter_panel.py REPO DESIGN INPUTS OUTPUT')
    print(json.dumps(panel(*map(Path,sys.argv[1:])),sort_keys=True))
