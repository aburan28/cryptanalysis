#!/usr/bin/env python3
"""Build and audit the pinned norm-58807 radix and digit proofs."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
MODULES = ('AlternateRadix.lean', 'HornerRadix.lean',
           'JointSeedGraph.lean', 'JointHorner.lean',
           'Triple243Radix.lean', 'Triple243Digit.lean')
STANDARD_AXIOMS = {'propext', 'Quot.sound', 'Classical.choice'}
THEOREMS = {
    'Triple243Radix': (
        'conjugate_primePair243', 'prime_norm243', 'quotient_norm_step',
        'quotient_step', 'valid_trace_evaluates', 'point_horner243',
        'two_scalar_horner243', 'sixteen_step_terminal_bound',
        'sixteen_quotients_terminal'),
    'Triple243Digit': (
        'rounding_error', 'rounded_in_native_window', 'norm_identity',
        'rounded_digit_norm_below_radix',
        'selected_digit_norm_below_radix', 'exact_quotient'),
}


def main():
    toolchain = (HERE / 'lean-toolchain').read_text().strip()
    assert toolchain == 'leanprover/lean4:v4.34.1'
    steps = []
    version = subprocess.run(['lean', '--version'], cwd=HERE, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    steps.append({'command': ['lean', '--version'], 'returncode': version.returncode,
                  'output': version.stdout})
    assert version.returncode == 0 and 'version 4.34.1' in version.stdout
    checker = shutil.which('lean4checker')
    with tempfile.TemporaryDirectory(prefix='triple243-lean-') as temp:
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
            for theorem in THEOREMS.get(Path(name).stem, ()):
                line = next(line for line in result.stdout.splitlines()
                            if line.startswith(f"'{Path(name).stem}.{theorem}' "))
                assert 'sorryAx' not in line, line
                if 'does not depend on any axioms' not in line:
                    axioms = set(line.split('[')[1].split(']')[0].split(', '))
                    assert axioms <= STANDARD_AXIOMS, line
        if checker:
            for module in THEOREMS:
                command = [checker, '--fresh', str(Path(temp) / f'{module}.olean')]
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
        'theorems': THEOREMS,
        'lean4checker_fresh_available': checker is not None,
        'steps': steps,
    }
    (HERE / 'triple243-lean-check.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'theorems': THEOREMS,
                      'toolchain': toolchain}, sort_keys=True))


if __name__ == '__main__':
    main()
