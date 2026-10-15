#!/usr/bin/env python3
"""Freeze the ten-pass paired Tier 1 panel before remote submission."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
BASE_MANIFEST = HERE / 'tier1-alt-radix-cpu40-manifest.json'
BASE_RULES = HERE / 'tier1-alt-radix-cpu40-rules.json'
MANIFEST = HERE / 'tier1-alt-radix-long10-cpu40-manifest.json'
RULES = HERE / 'tier1-alt-radix-long10-cpu40-rules.json'
PANEL = '/workspace/isolated-bench/panels'
ROOT = '/workspace/bench-sources'
COUNT = 128*96*10
BATCH_ID = 'uniform128x96x10'
HASHES = {
    'overlay': 'bb56c393ab35c25cca4015e863c1c7edf4574ae84e740c68031b557c77f7247b',
    'cache10_front': '0947e957a72f8007ca25a742309d0aa3aea6f98f998f604bbf01a2ac8af0aecb',
    'cache10_windows': 'ebe3a989b4a0eabf71691f9ba74324c3276c91f7220f585ea73319cceecab733',
    'cache10_binary': '933c31da42adbd51758f1853f727b75ad899086f80d0ec61d6919ec61e591be2',
    'alt_front': 'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef',
    'alt_windows': 'ee2297e049142e7447a1eac01da947095dba145f463657506b6a90adb9f3864d',
    'alt_binary': '44e524beefa2c33a1855ec14ac6a1fa3946b7e783614d68de9f39c2e38f801f1',
}


def write(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data, sort_keys=True, indent=2)+'\n')
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert sha256((HERE/'native_long_alt_panel_overlay.py').read_bytes()).hexdigest() == HASHES['overlay']
    rules = deepcopy(json.loads(BASE_RULES.read_text()))
    rules['purpose'] = ('Longer matched Tier 1 batch-throughput panel for norm-110557 '
                        'fifteen-row full two-x versus norm-136531 ten-row cache')
    rules['outer_repeats'] = 10
    rules['repetitions'] = 16
    rules['prior_panel_status'] = 'unknown_after_tier_gate'
    rules['hashes'] = HASHES
    rules['overlay_sha256'] = {'native_long_alt_panel_overlay.py': HASHES['overlay']}
    rules['timing_boundary'] = ('Rust Instant times ten consecutive passes over the same '
        'frozen 96 batches of 128 distinct SHAKE256-derived scalars (122,880 outputs); '
        'table preparation and fixture loading are outside the interval; every output '
        'is checked against an independently computed point after the interval.')
    rules['arm_order'] = 'A/A, alternate-radix comparison, A/A; runner alternates reference and candidate per repeat'
    rules['comparison_acceptance'] = ('all 16 pairs per case valid, each adjacent A/A '
        'ratio in [0.90,1.11], and the predeclared paired bootstrap 95% '
        'log-ratio interval excludes one')
    rules_sha = write(RULES, rules)

    manifest = deepcopy(json.loads(BASE_MANIFEST.read_text()))
    manifest['cases'] = deepcopy(manifest['cases'])
    for case in manifest['cases']:
        for side in ('reference', 'candidate'):
            case[side][0] = case[side][0].replace('prime-j0-cache10-native',
                'prime-j0-cache10-long10').replace('prime-j0-alt-radix-native',
                'prime-j0-alt-radix-long10')
        case['expected_fields']['batch_id'] = BATCH_ID
        case['expected_fields']['count'] = str(COUNT)
    manifest['artifacts'] = [
        '/workspace/cryptanalysis/scripts/isolated_bench.py',
        f'{PANEL}/allocation.json', f'{PANEL}/host-probe.json',
        f'{PANEL}/{RULES.name}', f'{PANEL}/native_long_alt_panel_overlay.py',
    ]
    for name in ('prime-j0-cache10-long10', 'prime-j0-alt-radix-long10'):
        manifest['artifacts'].extend(f'{ROOT}/{name}/{item}' for item in (
            'Cargo.toml', 'Cargo.lock', 'src/bin/eisenstein_fixed.rs',
            'src/bin/eisenstein_fixed/unit_orbit_windows.rs',
            'src/bin/mixed640_uniform_fixture.json',
            'target/release/eisenstein_fixed'))
    manifest['measurement_boundary'] = rules['timing_boundary']
    manifest['repetitions'] = 16
    manifest['timeout_s'] = 30
    manifest['outer_repeats'] = 10
    manifest['prior_panel_job_id'] = '51a80dfd759e4d5e8d5196a0a031aa78'
    manifest_sha = write(MANIFEST, manifest)
    print(json.dumps({'rules_sha256': rules_sha, 'manifest_sha256': manifest_sha,
                      'case_count': len(manifest['cases']),
                      'repetitions': manifest['repetitions'],
                      'outputs_per_arm': COUNT}, sort_keys=True))


if __name__ == '__main__':
    main()
