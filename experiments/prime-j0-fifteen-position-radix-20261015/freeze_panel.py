#!/usr/bin/env python3
"""Derive a frozen 16-versus-15 panel from the previous same-point Tier 1 plan."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014'
OLD = '/workspace/bench-sources/prime-j0-nearest-orbit-19183-native-batch'
NEW = '/workspace/bench-sources/prime-j0-nearest-orbit-71023-native-batch'


def run():
    plan = json.loads((PARENT / 'tier1-16v17-manifest.json').read_text())
    for case in plan['cases']:
        assert case['reference'][1:] == ['--benchmark-mixed640-batch','96']
        if case['id'] == 'compare':
            assert case['candidate'][0] == f'{OLD}/target/release/eisenstein_fixed'
            case['candidate'][0] = f'{NEW}/target/release/eisenstein_fixed'
        else:
            assert case['candidate'] == case['reference']
    plan['artifacts'] = sorted(set(
        path for path in plan['artifacts']
        if f'{OLD}/' not in path
        and not path.startswith('/workspace/isolated-bench/panels/radix19183-')
    ))
    plan['artifacts'] += [
        f'{NEW}/Cargo.lock',f'{NEW}/Cargo.toml',
        f'{NEW}/src/bin/eisenstein_fixed.rs',
        f'{NEW}/src/bin/eisenstein_fixed/unit_orbit_windows.rs',
        f'{NEW}/src/bin/mixed640_bench_fixture.json',
        f'{NEW}/native268_overlay.py',f'{NEW}/linux-test.log',
        f'{NEW}/linux-build.log',f'{NEW}/linux-preflight.stdout',
        f'{NEW}/linux-preflight.stderr',f'{NEW}/target/release/eisenstein_fixed',
        '/workspace/isolated-bench/panels/radix71023-frontier.json',
        '/workspace/isolated-bench/panels/radix71023-screen.json',
        '/workspace/isolated-bench/panels/radix71023-group-replay.json',
        '/workspace/isolated-bench/panels/radix71023-rules.json',
    ]
    plan['artifacts'] = sorted(set(plan['artifacts']))
    plan['measurement_boundary'] = json.loads(
        (HERE / 'tier1-rules.json').read_text())['timing_boundary']
    return plan


if __name__ == '__main__':
    print(json.dumps(run(),sort_keys=True,indent=2))
