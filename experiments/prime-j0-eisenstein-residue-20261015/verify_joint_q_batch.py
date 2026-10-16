#!/usr/bin/env python3
"""Independently construct Q variants and replay the joint rho command."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

from check_secp256k1_tau_generator import G, P, add, mul

HERE = Path(__file__).resolve().parent


def point_hex(point):
    if point is None:
        return 'identity'
    return ':'.join(f'{coordinate:064x}' for coordinate in point)


def scalar(row, name):
    return int(row[name + '_hex'], 16)


def run(binary, fixture, count, path, mode):
    path.write_text(json.dumps(fixture, sort_keys=True, separators=(',', ':')) + '\n')
    command = {
        'openssl_nowarm': '--pilot-rho-restart',
        'joint': '--pilot-rho-restart-joint',
        'joint_demand': '--pilot-rho-restart-joint-demand',
        'joint_fused': '--pilot-rho-restart-joint-fused',
        'joint_graph': '--pilot-rho-restart-joint-graph',
        'joint_fused_graph': '--pilot-rho-restart-joint-fused-graph',
        'joint_graph_planned': '--pilot-rho-restart-joint-graph-planned',
        'joint_fused_graph_planned': '--pilot-rho-restart-joint-fused-graph-planned',
    }[mode]
    argv = ([str(binary), command, 'openssl_nowarm', str(path), str(count)]
            if mode == 'openssl_nowarm' else
            [str(binary), command, str(path), str(count)])
    if mode in ('joint_graph_planned', 'joint_fused_graph_planned'):
        plan = path.with_name(path.stem + f'-plan-{count}.json')
        planned = subprocess.run([str(binary), '--pilot-rho-restart-joint-write-plan',
                                  str(path), str(count), str(plan)],
                                 text=True, capture_output=True)
        assert planned.returncode == 0, planned.stderr
        assert 'q_hex' not in plan.read_text()
        argv.append(str(plan))
    result = subprocess.run(argv,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    fields = dict(word.split('=', 1) for word in result.stdout.split())
    assert fields['verified'] == '1'
    assert fields['mode'] == mode
    assert int(fields['count']) == count
    assert fields['point'] == fixture['cases'][count-1]['point_hex']
    assert result.stderr == ''
    assert float(fields['online_ms']) > 0
    if mode == 'openssl_nowarm':
        assert float(fields['openssl_warmup_ms']) == 0.0
    if mode in ('joint_demand', 'joint_fused', 'joint_graph', 'joint_fused_graph',
                'joint_graph_planned', 'joint_fused_graph_planned'):
        assert int(fields['constructed_q_points']) >= 0
        assert abs(float(fields['online_ms'])
                   - float(fields['target_preparation_ms'])
                   - float(fields['restart_eval_ms'])) < 0.00001
    if mode in ('joint_fused', 'joint_fused_graph', 'joint_fused_graph_planned'):
        assert int(fields['fused_pair_sums']) >= 0
    if mode in ('joint_graph', 'joint_fused_graph', 'joint_graph_planned',
                'joint_fused_graph_planned'):
        assert (int(fields['graph_edges']) + int(fields['direct_seeds']) ==
                int(fields['constructed_q_points']))
    if mode in ('joint_graph_planned', 'joint_fused_graph_planned'):
        assert float(fields['graph_plan_ms']) == 0
        assert float(fields['plan_load_ms']) >= 0
        assert int(fields['plan_bytes']) > 0
    return {'mode': mode, 'fixture_sha256': sha256(path.read_bytes()).hexdigest(),
            'count': count, 'point': fields['point'], 'stdout': result.stdout.strip()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = HERE / 'rho-restart-first128-fixture.json'
    frozen = json.loads(source.read_text())
    q = tuple(int(value, 16) for value in frozen['q_hex'].split(':'))
    for row in frozen['cases'][:128]:
        assert row['point_hex'] == point_hex(add(mul(scalar(row, 'a'), G),
                                               mul(scalar(row, 'b'), q)))
    receipt = {
        'schema': 1, 'purpose': 'correctness_replay_only',
        'platform': platform.platform(),
        'binary_sha256': sha256(args.binary.read_bytes()).hexdigest(),
        'component_sha256': {
            name: sha256((HERE / name).read_bytes()).hexdigest()
            for name in ('joint_norm4033.rs', 'rho_restart_joint.rs',
                         'native_rho_restart_joint_overlay.py')},
        'source_fixture_sha256': sha256(source.read_bytes()).hexdigest(),
        'results': [],
    }
    with TemporaryDirectory(prefix='joint-q-batch-replay-') as temporary:
        root = Path(temporary)
        frozen_path = root / 'frozen-eight.json'
        frozen_path.write_text(json.dumps(frozen, sort_keys=True, separators=(',', ':')) + '\n')
        reference_plan = root / 'frozen-eight-plan.json'
        create = subprocess.run([str(args.binary), '--pilot-rho-restart-joint-write-plan',
                                 str(frozen_path), '8', str(reference_plan)],
                                text=True, capture_output=True)
        assert create.returncode == 0, create.stderr
        receipt['q_independent_plan_sha256'] = sha256(reference_plan.read_bytes()).hexdigest()
        for count in (1, 128):
            for mode in ('openssl_nowarm', 'joint', 'joint_demand', 'joint_fused',
                         'joint_graph', 'joint_fused_graph',
                         'joint_graph_planned', 'joint_fused_graph_planned'):
                receipt['results'].append({'q_scalar': None,
                    **run(args.binary, frozen, count, root / 'frozen.json', mode)})
        for q_scalar in (1, 2, 3, 7):
            q = mul(q_scalar, G)
            rows = []
            for row in frozen['cases'][:8]:
                a, b = scalar(row, 'a'), scalar(row, 'b')
                rows.append({'a_hex': row['a_hex'], 'b_hex': row['b_hex'],
                             'point_hex': point_hex(add(mul(a, G), mul(b, q)))})
            fixture = {'q_hex': point_hex(q), 'cases': rows}
            variant_path = root / f'q{q_scalar}.json'
            variant_path.write_text(json.dumps(fixture, sort_keys=True,
                                               separators=(',', ':')) + '\n')
            variant_plan = root / f'q{q_scalar}-plan.json'
            create = subprocess.run([str(args.binary), '--pilot-rho-restart-joint-write-plan',
                                     str(variant_path), '8', str(variant_plan)],
                                    text=True, capture_output=True)
            assert create.returncode == 0, create.stderr
            assert variant_plan.read_bytes() == reference_plan.read_bytes()
            for mode in ('joint', 'joint_demand', 'joint_fused', 'joint_graph',
                         'joint_fused_graph', 'joint_graph_planned',
                         'joint_fused_graph_planned'):
                receipt['results'].append({'q_scalar': q_scalar,
                    **run(args.binary, fixture, 8, root / f'q{q_scalar}.json', mode)})
        neg_g = (G[0], (-G[1]) % P)
        edges = (
            ('same_point_double', G, 1, 1),
            ('opposite_identity', neg_g, 1, 1),
            ('zero_zero', G, 0, 0),
            ('one_sided', G, 1, 0),
        )
        for name, q, a, b in edges:
            fixture = {'q_hex': point_hex(q), 'cases': [{
                'a_hex': f'{a:x}', 'b_hex': f'{b:x}',
                'point_hex': point_hex(add(mul(a, G), mul(b, q))),
            }]}
            for mode in ('joint_fused', 'joint_fused_graph',
                         'joint_fused_graph_planned'):
                receipt['results'].append({'edge': name, **run(args.binary, fixture, 1,
                    root / f'{name}.json', mode)})
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'runs': len(receipt['results']),
                      'outputs': sum(item['count'] for item in receipt['results'])},
                     sort_keys=True))


if __name__ == '__main__':
    main()
