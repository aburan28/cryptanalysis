#!/usr/bin/env python3
"""Recompute the elementary residue data for the tau exceptional locus."""

from hashlib import sha256
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
P = 2**256 - 2**32 - 977


def main():
    residue = pow(7, (P - 1) // 2, P)
    assert P % 28 == 15
    assert residue == P - 1
    receipt = {
        'schema': 1,
        'prime_decimal': str(P),
        'prime_mod_28': P % 28,
        'euler_power_base': 7,
        'euler_power_exponent_decimal': str((P - 1) // 2),
        'euler_power_mod_prime_decimal': str(residue),
        'checker_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'proof_status': 'numeric_residue_check; quadratic_reciprocity_step_written_not_lean_checked',
    }
    (HERE / 'secp256k1-seven-nonresidue-check.json').write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'ok': True, 'prime_mod_28': 15,
                      'euler_power_equals_minus_one': True}, sort_keys=True))


if __name__ == '__main__':
    main()
