#!/usr/bin/env python3
"""Build the pinned mixed-radix proof and audit its theorem dependencies."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
MODULES = (
    'AlternateRadix.lean', 'HornerRadix.lean', 'JointSeedGraph.lean',
    'JointHorner.lean', 'Triple81Radix.lean', 'Triple81Digit.lean',
    'Triple243Radix.lean', 'Triple243Digit.lean', 'TripleMixedRadix.lean',
)
THEOREMS = (
    'equilateral_basis', 'floor_corner_norm_bound',
    'selected_initial_norm_bound', 'mixed_sixteen_step_terminal_bound',
    'mixed_sixteen_step_terminal_below_table', 'mixed_quotients_terminal',
    'terminal_coordinates_in_table', 'two_scalar_mixed_horner',
    'mixed_horner_tripling_count',
)
STANDARD_AXIOMS = {'propext', 'Quot.sound', 'Classical.choice'}


def main() -> None:
    toolchain = (HERE / 'lean-toolchain').read_text().strip()
    assert toolchain == 'leanprover/lean4:v4.34.1'
    steps = []
    version = subprocess.run(['lean', '--version'], cwd=HERE, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    steps.append({'command': ['lean', '--version'], 'returncode': version.returncode,
                  'output': version.stdout})
    assert version.returncode == 0 and 'version 4.34.1' in version.stdout
    checker = shutil.which('lean4checker')
    with tempfile.TemporaryDirectory(prefix='triple-mixed-lean-') as temp:
        env = dict(os.environ, LEAN_PATH=temp)
        for name in MODULES:
            output = str(Path(temp) / (Path(name).stem + '.olean'))
            command = ['lean', '-o', output, name]
            result = subprocess.run(command, cwd=HERE, env=env, text=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            steps.append({'command': command, 'returncode': result.returncode,
                          'output': result.stdout})
            assert result.returncode == 0, result.stdout
            if name == 'TripleMixedRadix.lean':
                for theorem in THEOREMS:
                    line = next(line for line in result.stdout.splitlines()
                                if line.startswith(f"'TripleMixedRadix.{theorem}' "))
                    assert 'sorryAx' not in line, line
                    if 'does not depend on any axioms' not in line:
                        axioms = set(line.split('[')[1].split(']')[0].split(', '))
                        assert axioms <= STANDARD_AXIOMS, line
        if checker:
            command = [checker, '--fresh', str(Path(temp) / 'TripleMixedRadix.olean')]
            result = subprocess.run(command, cwd=HERE, env=env, text=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            steps.append({'command': command, 'returncode': result.returncode,
                          'output': result.stdout})
            assert result.returncode == 0, result.stdout
    receipt = {
        'schema': 1, 'toolchain': toolchain,
        'source_sha256': {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in MODULES},
        'theorems': list(THEOREMS),
        'lean4checker_fresh_available': checker is not None,
        'steps': steps,
    }
    (HERE / 'triple-mixed-lean-check.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'theorems': THEOREMS,
                      'toolchain': toolchain}, sort_keys=True))


if __name__ == '__main__':
    main()
