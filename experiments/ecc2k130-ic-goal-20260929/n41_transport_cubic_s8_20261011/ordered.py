"""Exact same-rotation pair symmetry cut on the transported N41 circuit."""

import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import circuit as core

HERE = Path(__file__).resolve().parent
OUT = HERE/'ordered'
spec = importlib.util.spec_from_file_location('n41_transport_base_run', HERE/'run.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def ordered_build(c, field, columns, target_zs):
    meta = core.build(c, field, columns, target_zs)
    masks = meta['masks']
    codes = sorted(columns)
    forbids = 0
    for pair in range(4):
        left, right = masks[2*pair:2*pair+2]
        for a in codes:
            for b in codes:
                if a <= b:
                    continue
                core.shared.old.old.old.clause(
                    c, core.shared.old.old.old.forbid(a, left) +
                    core.shared.old.old.old.forbid(b, right))
                forbids += 1
    assert forbids == 4*32*31//2
    meta['ordered_pair_forbids'] = forbids
    return meta


def source_files():
    return {'base_run.py': HERE/'run.py',
            'base_circuit.py': HERE/'circuit.py',
            'ordered.py': HERE/'ordered.py',
            'ordered_fixture.json': OUT/'fixture.json',
            'sage_runtime_info.json': HERE/'sage_runtime_info.json',
            'prepare_sage.py': HERE/'prepare_sage.py',
            'native_receipt.json': core.ROOT/'n131_w18_four_pairs/native_join/receipt.json',
            'screen.json': core.ROOT/'n131_w18_four_pairs/screen.json',
            'n131_circuit.py': core.N131,
            'n41_cubic_circuit.py': core.shared.N41/'circuit.py',
            'basis_circuit.py': core.shared.SPARSE/'circuit.py',
            'basis_sparse.py': core.shared.SPARSE/'sparse.py',
            'n41_horner_circuit.py': core.shared.ROOT/'n41_single_branch_horner_20261011/circuit.py',
            'karatsuba_circuit.py': base.ROOT/'experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py',
            'circuit_sat.py': base.ROOT/'experiments/koblitz-s5-invariant-20260924/circuit_sat.py',
            'cryptominisat5': base.SOLVER}


def configure():
    OUT.mkdir(exist_ok=True)
    base.source_files = source_files
    base.HERE = OUT
    base.circuit = SimpleNamespace(N=core.N, ROTATIONS=core.ROTATIONS,
                                   Field=core.Field, build=ordered_build)


def prepare():
    fixture = json.loads((HERE/'fixture.json').read_text())
    for pair in range(4):
        i = 2*pair
        if fixture['known_masks'][i] > fixture['known_masks'][i+1]:
            for key in ('known_masks', 'known_columns', 'source_D', 'source_P'):
                fixture[key][i], fixture[key][i+1] = fixture[key][i+1], fixture[key][i]
    assert all(fixture['known_masks'][2*i] < fixture['known_masks'][2*i+1]
               for i in range(4))
    base.save(OUT/'fixture.json', fixture)


def freeze():
    prepare()
    base.freeze()
    protocol = json.loads((OUT/'protocol.json').read_text())
    protocol['factor_base_B'] = 256
    protocol['method_refinement'] = 'canonical numeric mask order within each same-rotation pair'
    base.save(OUT/'protocol.json', protocol)
    print(json.dumps({'status': protocol['status'], 'factor_base_B': 256,
                      'ordered_pair_forbids': 4*32*31//2}))


if __name__ == '__main__':
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'control', 'query'))
    mode = parser.parse_args().mode
    {'freeze': freeze, 'control': base.control, 'query': base.query}[mode]()
