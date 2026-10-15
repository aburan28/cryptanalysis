#!/usr/bin/env python3
"""Freeze the compact affine lazy-rotation panel before submission."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
BASE = HERE/'tier1-alt-prefetch-cpu40-manifest.json'
RULES = HERE/'tier1-alt-lazy-rotation-cpu40-rules.json'
MANIFEST = HERE/'tier1-alt-lazy-rotation-cpu40-manifest.json'
PANEL = '/workspace/isolated-bench/panels'
ROOT = '/workspace/bench-sources'
HASHES = {
    'overlay':'52beffc74aaf111db25104381b464f6ff2eef3c255249c2cc77fdfa56298ca2e',
    'reference_front':'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef',
    'reference_windows':'f5dcba53fd1db7eb5b2c47cc9ccc3cc85c1c60ca45e1efb53e5f4aab5ff23154',
    'reference_binary':'d5ecff11f55f80aed1a2aa56766dc1691a760404a5aecbb1feb5c049fce2e270',
    'lazy_rotation_front':'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef',
    'lazy_rotation_windows':'ddc5dcc136d4b8bec8a7dece2dad7225a5d681a3e756dea2b3258123775e62e8',
    'lazy_rotation_binary':'6b194fbde6291c66e74454e49cdd21bbf15f48bb92a1952b9c34ad986c4ad408',
}


def write(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
    return sha256(path.read_bytes()).hexdigest()


def main():
    assert sha256((HERE/'native_alt_lazy_rotation_overlay.py').read_bytes()).hexdigest() == HASHES['overlay']
    base = json.loads(BASE.read_text())
    rules = {
        'schema':1, 'tier':'tier1_instance', 'execution_cpu':40, 'service_cpu':2,
        'purpose':'Store 64-byte affine points and multiply by beta on rotation selection instead of storing 96-byte two-x entries',
        'case_order':['cal_before','compare_lazy_rotation','cal_after'],
        'arm_order':'A/A, lazy-rotation comparison, A/A; runner alternates reference and candidate per repeat',
        'aa_acceptance':[0.90,1.11], 'repetitions':16, 'outer_repeats':10,
        'comparison_acceptance':('all 16 comparison pairs valid; adjacent A/A ratios in '
            '[0.90,1.11]; paired bootstrap 95% log-ratio interval excludes one'),
        'fixture_sha256':base['cases'][0]['expected_fields']['fixture_sha256'],
        'table_bytes':{'reference':27429548,'lazy_rotation':18487788,'cap':33554432},
        'hashes':HASHES,
        'timing_boundary':base['measurement_boundary'],
    }
    rules_sha = write(RULES,rules)
    manifest = deepcopy(base)
    reference = f'{ROOT}/prime-j0-alt-radix-prefetch-long10/target/release/eisenstein_fixed'
    candidate = f'{ROOT}/prime-j0-alt-radix-lazy-rotation/target/release/eisenstein_fixed'
    for case, name in zip(manifest['cases'], rules['case_order']):
        case['id'] = name
        case['reference'] = [reference,'--benchmark-alt-radix-uniform','128','96']
        case['candidate'] = [candidate if name == 'compare_lazy_rotation' else reference,
                             '--benchmark-alt-radix-uniform','128','96']
    manifest['artifacts'] = [
        '/workspace/cryptanalysis/scripts/isolated_bench.py',
        f'{PANEL}/allocation.json', f'{PANEL}/host-probe.json',
        f'{PANEL}/{RULES.name}', f'{PANEL}/native_alt_lazy_rotation_overlay.py',
        f'{PANEL}/native_alt_prefetch_overlay.py',
    ]
    for name in ('prime-j0-alt-radix-prefetch-long10','prime-j0-alt-radix-lazy-rotation'):
        manifest['artifacts'].extend(f'{ROOT}/{name}/{item}' for item in (
            'Cargo.toml','Cargo.lock','src/bin/eisenstein_fixed.rs',
            'src/bin/eisenstein_fixed/unit_orbit_windows.rs',
            'src/bin/mixed640_uniform_fixture.json',
            'target/release/eisenstein_fixed'))
    manifest['prior_panel_job_id'] = 'b773ba315139428ab2d5935a9c848b33'
    manifest['comparison_variant'] = 'compact-affine-lazy-rotation'
    manifest_sha = write(MANIFEST,manifest)
    print(json.dumps({'rules_sha256':rules_sha,'manifest_sha256':manifest_sha,
                      'repetitions':16,'outputs_per_arm':122880},sort_keys=True))


if __name__ == '__main__':
    main()
