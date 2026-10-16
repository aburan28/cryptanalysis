#!/usr/bin/env python3
"""Search a bounded two-link unit-root graph by native source-formula cost."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cost_aware_plan import witness_cost, witnesses
from one_aux_plan import add_vertex, close_requested
from root_first_plan import unit
from unit_root_plan import ROOT, candidate_vertices, trial_add
from verify_root_first import BASE, encode, run
from check_secp256k1_tau_generator import G, add, mul


# These are the eight lowest rotation-minus-four-mixed first-stage scores
# among links covering at least 18 of the 21 requested seeds.  The receipt
# records this bounded domain; graph edge counts enter the completed score.
FIRST_LINKS = ((-26, 9), (26, -9), (-25, 17), (-1, -8),
               (1, 8), (25, -17), (-32, 19), (32, -19))


def rewire(rows):
    """Select the cheapest valid witness for each vertex in its fixed order."""
    orbit = {}
    affine = {ROOT}
    chosen = []
    changed = 0
    for a, b, old in rows:
        target = (a, b)
        if old[0] == 'direct':
            assert target == ROOT
            op = old
        else:
            options = list(witnesses(target, orbit))
            assert options, target
            op = min(options, key=lambda candidate:
                     (*witness_cost(candidate, affine)[:3], candidate))
            assert witness_cost(op, affine)[:2] <= witness_cost(old, affine)[:2]
            changed += op != old
        chosen.append([a, b, op])
        for code in range(6):
            coefficient = unit(target, code)
            assert coefficient not in orbit
            orbit[coefficient] = target, code
    return chosen, changed


def source_cost(rows, requested_count):
    # The root is an affine unit rotation of Q, costing one multiplication.
    # Batch normalization charges 6M + 1S for each requested seed.
    edges = [witness_cost(op, {ROOT}) for _, _, op in rows
             if op[0] != 'direct']
    graph_muls = 1 + sum(row[0] for row in edges)
    graph_squares = sum(row[1] for row in edges)
    return {'field_muls': graph_muls + 6 * requested_count,
            'field_squares': graph_squares + requested_count,
            'graph_field_muls': graph_muls,
            'graph_field_squares': graph_squares,
            'normalization_field_muls': 6 * requested_count,
            'normalization_field_squares': requested_count,
            'unit_rotations': 1 + sum(row[2] for row in edges),
            'mixed_edges': sum(row[3] for row in edges),
            'graph_edges': len(edges)}


def optimize(source):
    assert source['count'] == 1
    requested = {tuple(row[:2]) for row in source['graph']['nodes']}
    assert ROOT in requested and len(requested) == 21
    base = [], set(), {}
    add_vertex(*base, ROOT, ['direct'])
    close_requested(requested, *base)
    first_rank = []
    for candidate in candidate_vertices(requested, base[1], base[2]):
        state = trial_add(requested, base, candidate)
        if state is not None and len(state[1] & requested) >= 18:
            rows = state[0]
            edges = [witness_cost(op, {ROOT}) for _, _, op in rows
                     if op[0] != 'direct']
            score = 1 + sum(row[2] - 4 * row[3] for row in edges)
            first_rank.append((score, -len(state[1] & requested), candidate))
    assert tuple(row[2] for row in sorted(first_rank)[:8]) == FIRST_LINKS
    best = None
    examined = 0
    feasible = 0
    for first in FIRST_LINKS:
        first_state = trial_add(requested, base, first)
        assert first_state is not None
        for second in candidate_vertices(requested, first_state[1], first_state[2]):
            examined += 1
            state = trial_add(requested, first_state, second)
            if state is None or not requested <= state[1]:
                continue
            feasible += 1
            rows, changed = rewire(state[0])
            assert len(rows) == len(requested) + 2
            cost = source_cost(rows, len(requested))
            key = (cost['field_muls'], cost['field_squares'],
                   cost['unit_rotations'], first, second)
            if best is None or key < best[0]:
                best = key, first, second, rows, changed, cost
    assert best is not None
    _, first, second, rows, changed, cost = best
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=rows)
    receipt = {'schema': 1, 'count': 1, 'root': list(ROOT),
               'requested_seeds': len(requested),
               'constructed_vertices': len(rows),
               'first_links_examined': [list(x) for x in FIRST_LINKS],
               'first_link_candidates_ranked': len(first_rank),
               'second_candidates_examined': examined,
               'complete_two_link_graphs': feasible,
               'first_auxiliary': list(first),
               'second_auxiliary': list(second),
               'rewired_edges': changed,
               'source_formula_cost': cost,
               'cost_boundary': 'graph construction and batch normalization; shared binary-power preparation and inversion, recoding, plan loading, Q parsing, and restart evaluation excluded',
               'search_domain': 'eight listed first links; every bounded second link returned by candidate_vertices for each; all valid one-power and two-parent witnesses for every vertex in each complete fixed-order graph'}
    return result, receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--binary', type=Path)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    result, receipt = optimize(json.loads(source_bytes))
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt['source_plan_sha256'] = sha256(source_bytes).hexdigest()
    receipt['output_plan_sha256'] = sha256(output.encode()).hexdigest()
    if args.binary is not None:
        frozen_path = BASE / 'rho-restart-first128-fixture.json'
        frozen = json.loads(frozen_path.read_bytes())
        row = frozen['cases'][0]
        a, b = int(row['a_hex'], 16), int(row['b_hex'], 16)
        replay = []
        with TemporaryDirectory(prefix='cost-aware-one-replay-') as temp:
            scratch = Path(temp) / 'fixture.json'
            for q_scalar in (None, 1, 2, 3, 7):
                if q_scalar is None:
                    fixture = frozen
                else:
                    q = mul(q_scalar, G)
                    fixture = {'q_hex': encode(q), 'cases': [{
                        'a_hex': row['a_hex'], 'b_hex': row['b_hex'],
                        'point_hex': encode(add(mul(a, G), mul(b, q))) }]}
                for mode in ('graph-planned', 'fused-graph-planned'):
                    checked = run(args.binary, fixture, 1, args.output, mode,
                                  scratch)
                    checked['q_scalar'] = q_scalar
                    replay.append(checked)
        receipt['native_replay'] = {
            'binary_sha256': sha256(args.binary.read_bytes()).hexdigest(),
            'frozen_fixture_sha256': sha256(frozen_path.read_bytes()).hexdigest(),
            'exact_outputs': len(replay), 'results': replay}
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'plan_sha256': receipt['output_plan_sha256'],
                      'source_formula_cost': receipt['source_formula_cost'],
                      'complete_two_link_graphs': receipt['complete_two_link_graphs'],
                      'exact_outputs': receipt.get('native_replay', {}).get('exact_outputs')},
                     sort_keys=True))


if __name__ == '__main__':
    main()
