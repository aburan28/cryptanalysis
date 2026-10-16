#!/usr/bin/env python3
"""Build the pinned graph theorem modules and retain their kernel audit."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
MODULES = ('AlternateRadix.lean', 'HornerRadix.lean', 'JointSeedGraph.lean',
           'JointHorner.lean')
THEOREMS = {
    'JointSeedGraph': ('omega_square_q_coefficient', 'unit_root_value',
                       'certifiedStep_valid', 'certifiedTrace_valid',
                       'requested_seed_values', 'requested_projection'),
    'JointHorner': ('combine_horner', 'two_scalar_horner',
                    'two_scalar_horner_from_graph'),
}


def main():
    toolchain = (HERE / 'lean-toolchain').read_text().strip()
    assert toolchain == 'leanprover/lean4:v4.34.1'
    steps = []
    version = subprocess.run(['lean', '--version'], cwd=HERE,
                             text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    steps.append({'command': ['lean', '--version'], 'returncode': version.returncode,
                  'output': version.stdout})
    assert version.returncode == 0 and 'version 4.34.1' in version.stdout
    checker = shutil.which('lean4checker')
    with tempfile.TemporaryDirectory(prefix='joint-seed-graph-lean-') as temp:
        env = dict(os.environ, LEAN_PATH=temp)
        outputs = {}
        for name in MODULES:
            output = str(Path(temp) / (Path(name).stem + '.olean'))
            command = ['lean', '-o', output, name]
            result = subprocess.run(command, cwd=HERE, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            steps.append({'command': command, 'returncode': result.returncode,
                          'output': result.stdout})
            assert result.returncode == 0, result.stdout
            outputs[Path(name).stem] = result.stdout
        for module, theorems in THEOREMS.items():
            for theorem in theorems:
                line = next(line for line in outputs[module].splitlines()
                            if line.startswith(f"'{module}.{theorem}' "))
                assert 'sorryAx' not in line and (
                    'does not depend on any axioms' in line or
                    all(axiom in ('propext', 'Quot.sound', 'Classical.choice')
                        for axiom in line.split('[')[1].split(']')[0].split(', '))), line
        if checker:
            command = [checker, '--fresh',
                       str(Path(temp) / 'JointHorner.olean')]
            result = subprocess.run(command, cwd=HERE, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            steps.append({'command': command, 'returncode': result.returncode,
                          'output': result.stdout})
            assert result.returncode == 0, result.stdout
    receipt = {
        'schema': 3, 'toolchain': toolchain,
        'source_sha256': {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in MODULES},
        'new_theorems': {module: list(theorems)
                         for module, theorems in THEOREMS.items()},
        'lean4checker_fresh_available': checker is not None,
        'steps': steps,
    }
    output = HERE / 'joint-seed-graph-lean-check.json'
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'theorems': THEOREMS,
                      'toolchain': toolchain}, sort_keys=True))


if __name__ == '__main__':
    main()
