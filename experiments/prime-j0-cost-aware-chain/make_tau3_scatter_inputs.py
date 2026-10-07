#!/usr/bin/env python3
"""Create fresh, reproducible scalar fixtures after scatter design is frozen."""
import hashlib
import json
from pathlib import Path
import random
import struct
import sys

SEED = 202610061135
COUNT = 4096


def sha256(data): return hashlib.sha256(data).hexdigest()


def make(repo, design_path, output_dir):
    design_bytes = design_path.read_bytes()
    design = json.loads(design_bytes)
    assert design['status'] == 'frozen_retrospective_design'
    earlier = ['compact-pos-inputs.json', 'tau3-fused-inputs.json',
               'tau3-sparse-inputs.json', 'tau3-radix27-inputs.json']
    excluded = {'glv-j0-32': set(), 'j0-56': set()}
    earlier_hashes = {}
    for name in earlier:
        data = (repo / name).read_bytes()
        earlier_hashes[name] = sha256(data)
        for case in json.loads(data)['cases']:
            seen = excluded[case['curve']['name']]
            blob = (repo / case['scalar_file']).read_bytes()
            assert sha256(blob) == case['scalar_file_sha256']
            seen.update(v for (v,) in struct.iter_unpack('<Q', blob))
    source = json.loads((repo / 'compact-pos-inputs.json').read_text())
    rng = random.Random(SEED)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for case in source['cases']:
        curve = case['curve']['name']
        order = case['curve']['order']
        values = []
        while len(values) < COUNT:
            value = rng.randrange(order)
            if value not in excluded[curve]:
                excluded[curve].add(value)
                values.append(value)
        blob = b''.join(struct.pack('<Q', v) for v in values)
        name = case['id'] + '.scalars.bin'
        (output_dir / name).write_bytes(blob)
        cases.append({'id': case['id'], 'curve': case['curve'], 'base_x': case['base_x'],
                      'base_y': case['base_y'], 'count': COUNT, 'scalar_file': name,
                      'scalar_file_sha256': sha256(blob)})
    manifest = {'schema': 1, 'status': 'fresh_disjoint_fixture',
                'design_sha256': sha256(design_bytes), 'seed': SEED,
                'selection_law': 'Python Random.randrange(order), reject values in prior four fixtures and earlier new cases on same curve',
                'prior_manifest_sha256': earlier_hashes,
                'source_sha256': sha256(Path(__file__).read_bytes()),
                'cases': cases}
    content = json.dumps(manifest, indent=2, sort_keys=True).encode() + b'\n'
    manifest_path = output_dir / 'inputs.json'
    if manifest_path.exists() and manifest_path.read_bytes() != content:
        raise ValueError('fixture changed')
    manifest_path.write_bytes(content)
    return {'manifest_sha256': sha256(content), 'cases': len(cases), 'scalars': COUNT * len(cases)}


if __name__ == '__main__':
    if len(sys.argv) != 4: raise SystemExit('usage: make_tau3_scatter_inputs.py REPO DESIGN OUTPUT_DIR')
    print(json.dumps(make(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])), sort_keys=True))
