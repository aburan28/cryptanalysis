#!/usr/bin/env python3
"""Retain exact Lean build and axiom-audit output for CapacityBound.lean."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    version = subprocess.run(['lean', '--version'], cwd=HERE,
                             text=True, capture_output=True, check=True)
    result = subprocess.run(['lean', 'CapacityBound.lean'], cwd=HERE,
                            text=True, capture_output=True)
    expected = [
        "'N83CompactOrbitCapacity.k899_requested_slots_fit' does not depend on any axioms",
        "'N83CompactOrbitCapacity.k900_maximum_crosses_boundary' does not depend on any axioms",
        "'N83CompactOrbitCapacity.table_slot_bytes_at_boundary' does not depend on any axioms",
    ]
    assert result.returncode == 0 and result.stderr == ''
    assert result.stdout.strip().splitlines() == expected
    receipt = {
        'schema': 'n83_capacity_lean_proof_check_v1',
        'toolchain': (HERE / 'lean-toolchain').read_text().strip(),
        'lean_version_stdout': version.stdout,
        'command': ['lean', 'CapacityBound.lean'],
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'source_sha256': hashlib.sha256((HERE / 'CapacityBound.lean').read_bytes()).hexdigest(),
        'declarations': [line.split("'")[1] for line in expected],
        'foundations': 'Lean 4 core natural-number arithmetic and decide; no Mathlib dependency or custom axioms',
        'lean4checker_fresh': 'unavailable' if shutil.which('lean4checker') is None else 'not_run',
    }
    with (HERE / 'proof_check.json').open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps({'status': 'PASS', 'declarations': receipt['declarations']}))


if __name__ == '__main__':
    main()
