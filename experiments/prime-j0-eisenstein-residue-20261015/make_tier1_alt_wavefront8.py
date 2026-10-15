#!/usr/bin/env python3
"""Freeze the same-table eight-lane wavefront panel before submission."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
BASE = HERE/'tier1-alt-prefetch-cpu40-manifest.json'
RULES = HERE/'tier1-alt-wavefront8-cpu40-rules.json'
MANIFEST = HERE/'tier1-alt-wavefront8-cpu40-manifest.json'
PANEL = '/workspace/isolated-bench/panels'
ROOT = '/workspace/bench-sources'
HASHES = {
    'overlay':'d290df59ad54e06dfcd856d65fe12ea6151c06125bb021439533fef907595cd3',
    'reference_front':'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef',
    'reference_windows':'f5dcba53fd1db7eb5b2c47cc9ccc3cc85c1c60ca45e1efb53e5f4aab5ff23154',
    'reference_binary':'d5ecff11f55f80aed1a2aa56766dc1691a760404a5aecbb1feb5c049fce2e270',
    'wavefront_front':'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef',
    'wavefront_windows':'89e9727d072cce5505295dce3cf6b1da769229586f3e20aa11a000a3cb4d9cef',
    'wavefront_binary':'54c233c6138abdd8c3af3bf4eec6a7a0702853d13b7be728e16cda7a81193073',
}


def write(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
    return sha256(path.read_bytes()).hexdigest()


def main():
    assert sha256((HERE/'native_alt_wavefront_overlay.py').read_bytes()).hexdigest() == HASHES['overlay']
    base = json.loads(BASE.read_text())
    rules = {
        'schema':1, 'tier':'tier1_instance', 'execution_cpu':40, 'service_cpu':2,
        'purpose':'Transpose recoding, prefetch, and affine gather across eight scalars on the same norm-110557 table',
        'case_order':['cal_before','compare_wavefront8','cal_after'],
        'arm_order':'A/A, wavefront comparison, A/A; runner alternates reference and candidate per repeat',
        'aa_acceptance':[0.90,1.11], 'repetitions':16, 'outer_repeats':10,
        'comparison_acceptance':('all 16 comparison pairs valid; adjacent A/A ratios in '
            '[0.90,1.11]; paired bootstrap 95% log-ratio interval excludes one'),
        'fixture_sha256':base['cases'][0]['expected_fields']['fixture_sha256'],
        'table_bytes':{'reference':27429548,'wavefront':27429548,'cap':33554432},
        'hashes':HASHES,
        'timing_boundary':base['measurement_boundary'],
    }
    rules_sha = write(RULES,rules)
    manifest = deepcopy(base)
    reference = f'{ROOT}/prime-j0-alt-radix-prefetch-long10/target/release/eisenstein_fixed'
    candidate = f'{ROOT}/prime-j0-alt-radix-wavefront8/target/release/eisenstein_fixed'
    for case, name in zip(manifest['cases'], rules['case_order']):
        case['id'] = name
        case['reference'] = [reference,'--benchmark-alt-radix-uniform','128','96']
        case['candidate'] = [candidate if name == 'compare_wavefront8' else reference,
                             '--benchmark-alt-radix-uniform','128','96']
    manifest['artifacts'] = [
        '/workspace/cryptanalysis/scripts/isolated_bench.py',
        f'{PANEL}/allocation.json', f'{PANEL}/host-probe.json',
        f'{PANEL}/{RULES.name}', f'{PANEL}/native_alt_wavefront_overlay.py',
        f'{PANEL}/native_alt_prefetch_overlay.py',
    ]
    for name in ('prime-j0-alt-radix-prefetch-long10','prime-j0-alt-radix-wavefront8'):
        manifest['artifacts'].extend(f'{ROOT}/{name}/{item}' for item in (
            'Cargo.toml','Cargo.lock','src/bin/eisenstein_fixed.rs',
            'src/bin/eisenstein_fixed/unit_orbit_windows.rs',
            'src/bin/mixed640_uniform_fixture.json',
            'target/release/eisenstein_fixed'))
    manifest['prior_panel_job_id'] = '1445ccaffbf7479793ef49eb9005730e'
    manifest['comparison_variant'] = 'eight-lane-wavefront-gather'
    manifest_sha = write(MANIFEST,manifest)
    print(json.dumps({'rules_sha256':rules_sha,'manifest_sha256':manifest_sha,
                      'repetitions':16,'outputs_per_arm':122880},sort_keys=True))


if __name__ == '__main__':
    main()
