#!/usr/bin/env python3
"""Freeze the same-radix prefetch comparison before queue submission."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
BASE = HERE/'tier1-alt-radix-long10-cpu40-manifest.json'
RULES = HERE/'tier1-alt-prefetch-cpu40-rules.json'
MANIFEST = HERE/'tier1-alt-prefetch-cpu40-manifest.json'
PANEL = '/workspace/isolated-bench/panels'
ROOT = '/workspace/bench-sources'
HASHES = {
    'overlay':'f3816df36ba07cf590af71246dbe2d5d3cb96bb47029312090d30534a0408bdc',
    'reference_front':'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef',
    'reference_windows':'ee2297e049142e7447a1eac01da947095dba145f463657506b6a90adb9f3864d',
    'reference_binary':'44e524beefa2c33a1855ec14ac6a1fa3946b7e783614d68de9f39c2e38f801f1',
    'prefetch_front':'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef',
    'prefetch_windows':'f5dcba53fd1db7eb5b2c47cc9ccc3cc85c1c60ca45e1efb53e5f4aab5ff23154',
    'prefetch_binary':'d5ecff11f55f80aed1a2aa56766dc1691a760404a5aecbb1feb5c049fce2e270',
}


def write(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
    return sha256(path.read_bytes()).hexdigest()


def main():
    assert sha256((HERE/'native_alt_prefetch_overlay.py').read_bytes()).hexdigest() == HASHES['overlay']
    base = json.loads(BASE.read_text())
    rules = {
        'schema':1, 'tier':'tier1_instance', 'execution_cpu':40, 'service_cpu':2,
        'purpose':'Within norm-110557 fifteen-row two-x path, prefetch selected table entries before affine gather',
        'case_order':['cal_before','compare_prefetch','cal_after'],
        'arm_order':'A/A, prefetch comparison, A/A; runner alternates reference and candidate per repeat',
        'aa_acceptance':[0.90,1.11], 'repetitions':16, 'outer_repeats':10,
        'comparison_acceptance':('all 16 comparison pairs valid; adjacent A/A ratios in '
            '[0.90,1.11]; paired bootstrap 95% log-ratio interval excludes one'),
        'fixture_sha256':base['cases'][0]['expected_fields']['fixture_sha256'],
        'table_bytes':{'reference':27429548,'prefetch':27429548,'cap':33554432},
        'hashes':HASHES,
        'timing_boundary':base['measurement_boundary'],
    }
    rules_sha = write(RULES,rules)
    manifest = deepcopy(base)
    reference = f'{ROOT}/prime-j0-alt-radix-long10/target/release/eisenstein_fixed'
    candidate = f'{ROOT}/prime-j0-alt-radix-prefetch-long10/target/release/eisenstein_fixed'
    for case, name in zip(manifest['cases'], rules['case_order']):
        case['id'] = name
        case['reference'] = [reference,'--benchmark-alt-radix-uniform','128','96']
        case['candidate'] = [candidate if name == 'compare_prefetch' else reference,
                             '--benchmark-alt-radix-uniform','128','96']
    manifest['artifacts'] = [
        '/workspace/cryptanalysis/scripts/isolated_bench.py',
        f'{PANEL}/allocation.json', f'{PANEL}/host-probe.json',
        f'{PANEL}/{RULES.name}', f'{PANEL}/native_alt_prefetch_overlay.py',
        f'{PANEL}/native_long_alt_panel_overlay.py',
    ]
    for name in ('prime-j0-alt-radix-long10','prime-j0-alt-radix-prefetch-long10'):
        manifest['artifacts'].extend(f'{ROOT}/{name}/{item}' for item in (
            'Cargo.toml','Cargo.lock','src/bin/eisenstein_fixed.rs',
            'src/bin/eisenstein_fixed/unit_orbit_windows.rs',
            'src/bin/mixed640_uniform_fixture.json',
            'target/release/eisenstein_fixed'))
    manifest['prior_panel_job_id'] = '14dd3766e7d643e380872b915398ce96'
    manifest['comparison_variant'] = 'selected-entry-prefetch'
    manifest_sha = write(MANIFEST,manifest)
    print(json.dumps({'rules_sha256':rules_sha,'manifest_sha256':manifest_sha,
                      'repetitions':16,'outputs_per_arm':122880},sort_keys=True))


if __name__ == '__main__':
    main()
