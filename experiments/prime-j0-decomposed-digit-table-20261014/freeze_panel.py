#!/usr/bin/env python3
"""Derive the frozen orbit-versus-unit-basis panel from the previous same-point panel."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'prime-j0-variable-orbit-radix-20261014'
OLD = '/workspace/bench-sources/prime-j0-nearest-orbit-19183-native-batch'
NEW = '/workspace/bench-sources/prime-j0-unit-basis-19183-native-batch'


def run():
    plan = json.loads((PARENT / 'tier1-18v17-96-manifest.json').read_text())
    for case in plan['cases']:
        assert case['reference'][1:] == ['--benchmark-mixed640-batch', '96']
        case['reference'][0] = f'{OLD}/target/release/eisenstein_fixed'
        case['candidate'][0] = (
            f'{NEW}/target/release/eisenstein_fixed' if case['id'] == 'compare'
            else f'{OLD}/target/release/eisenstein_fixed')
    plan['artifacts'] = sorted(set(
        path for path in plan['artifacts']
        if '/prime-j0-nearest-orbit-12211-native-batch/' not in path
        and not path.startswith('/workspace/isolated-bench/panels/radix19183-')
    ))
    plan['artifacts'] += [
        f'{NEW}/Cargo.lock', f'{NEW}/Cargo.toml',
        f'{NEW}/src/bin/eisenstein_fixed.rs',
        f'{NEW}/src/bin/eisenstein_fixed/unit_orbit_windows.rs',
        f'{NEW}/src/bin/mixed640_bench_fixture.json',
        f'{NEW}/native_overlay.py', f'{NEW}/linux-test.log',
        f'{NEW}/linux-build.log', f'{NEW}/linux-preflight.stdout',
        f'{NEW}/linux-preflight.stderr', f'{NEW}/target/release/eisenstein_fixed',
        '/workspace/isolated-bench/panels/unit-basis-screen.json',
        '/workspace/isolated-bench/panels/unit-basis-group-replay.json',
        '/workspace/isolated-bench/panels/unit-basis-rules.json',
    ]
    plan['artifacts'] = sorted(set(plan['artifacts']))
    plan['measurement_boundary'] = json.loads(
        (HERE / 'tier1-rules.json').read_text())['timing_boundary']
    return plan


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True, indent=2))
