"""Compare built baseline/candidate clients, including checkpoint rate accounting.

Usage: python3 codegen/testwalkvariants.py BASELINE CANDIDATE
Both binaries must have identical batch/lane settings. Works with CPU or GPU
clients; it does not equate CPU equivalence with GPU validation.
"""
import pathlib
import re
import subprocess
import sys
import tempfile

from benchreport import reportsVerified


def run(binary, args):
    p = subprocess.run([str(binary)] + args, text=True, capture_output=True, timeout=180)
    if p.returncode or 'MISMATCH' in p.stdout:
        raise AssertionError(p.stdout + p.stderr)
    return p.stdout


def main():
    binaries = [pathlib.Path(p).resolve() for p in sys.argv[1:]]
    if len(binaries) != 2:
        raise SystemExit('usage: testwalkvariants.py BASELINE CANDIDATE')
    states = []
    with tempfile.TemporaryDirectory() as temp:
        for index, binary in enumerate(binaries):
            checkpoint = pathlib.Path(temp) / ('walk-%d.ckpt' % index)
            args = ['--curve', '131', '--bench', '--threads', '1', '--steps', '2',
                    '--launches', '2', '--verify', '0', '--checkpoint', str(checkpoint)]
            first = run(binary, args)
            resumed = run(binary, args)
            walks = int(re.search(r'= (\d+) walks', first).group(1))
            count = int(re.search(r'M it/s\s+(\d+) iterations', resumed).group(1))
            assert 'resumed from' in resumed, resumed
            assert count == 4 * walks, (count, walks, resumed)
            states.append(checkpoint.read_bytes())
            report = run(binary, ['--curve', '131', '--threads', '1', '--steps', '16',
                                  '--launches', '2', '--dp-weight', '50', '--verify', '16'])
            assert reportsVerified(0, report), report
            for curve in ('23', '41'):
                solved = run(binary, ['--curve', curve, '--instance', '0', '--threads', '1',
                                      '--steps', '16', '--launches', '128', '--verify', '4'])
                assert 'matches the planted discrete log: yes' in solved, solved
        assert states[0] == states[1], 'baseline and candidate final checkpoints differ'
    print('PASS: identical GF(2^131) resumed state; current-run iteration counts; '
          '131-bit report replay; planted logs on both binaries')


if __name__ == '__main__':
    main()
