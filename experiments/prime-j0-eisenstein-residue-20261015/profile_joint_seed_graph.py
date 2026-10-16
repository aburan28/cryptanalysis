#!/usr/bin/env python3
"""Independently count group-add calls for the frozen shared Q-seed graph."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
SOURCE = ('joint_norm4033.rs', 'rho_restart_joint.rs',
          'native_rho_restart_joint_overlay.py')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def weight(pair):
    return sum(bin(abs(value)).count('1') for value in pair)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    fixture = HERE / 'rho-restart-first128-fixture.json'
    result = {'schema': 1, 'purpose': 'source_level_q_seed_addition_calls',
              'binary_sha256': digest(args.binary),
              'fixture_sha256': digest(fixture),
              'source_sha256': {name: digest(HERE / name) for name in SOURCE},
              'runs': []}
    for count in (1, 128):
        command = [str(args.binary), '--pilot-rho-restart-joint-profile',
                   str(fixture), str(count)]
        proc = subprocess.run(command, text=True, capture_output=True)
        assert proc.returncode == 0 and proc.stderr == '', proc.stderr
        profile = json.loads(proc.stdout)
        seeds = [tuple(x) for x in profile['q_digit_seeds'] +
                 profile['q_terminal_seeds']]
        assert len(seeds) == len(set(seeds))
        known, roots, edges = set(), [], 0
        for a, b in sorted(seeds):
            if any((a+da,b+db) in known for da,db in
                   ((-1,0),(0,-1),(1,0),(0,1))):
                edges += 1
            else:
                roots.append((a,b))
            known.add((a,b))
        direct_calls = sum(map(weight,seeds))
        root_calls = sum(map(weight,roots))
        assert len(seeds) == len(roots) + edges
        graph_command = [str(args.binary), '--pilot-rho-restart-joint-graph',
                         str(fixture), str(count)]
        graph_proc = subprocess.run(graph_command, text=True, capture_output=True)
        assert graph_proc.returncode == 0 and graph_proc.stderr == '', graph_proc.stderr
        fields = dict(word.split('=',1) for word in graph_proc.stdout.split())
        assert fields['verified'] == '1' and fields['mode'] == 'joint_graph'
        assert int(fields['count']) == count
        assert int(fields['constructed_q_points']) == len(seeds)
        assert int(fields['graph_edges']) == edges
        assert int(fields['direct_seeds']) == len(roots)
        result['runs'].append({
            'count': count, 'requested_unique_seeds': len(seeds),
            'seed_pairs_sha256': sha256(json.dumps(sorted(seeds),
                separators=(',',':')).encode()).hexdigest(),
            'direct_add_projective_calls': direct_calls,
            'graph_root_add_projective_calls': root_calls,
            'graph_edge_add_projective_calls': edges,
            'graph_total_add_projective_calls': root_calls + edges,
            'direct_roots': len(roots),
            'verified_point': fields['point'],
        })
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'counts': [row['count'] for row in result['runs']]},
                     sort_keys=True))


if __name__ == '__main__':
    main()
