#!/usr/bin/env python3
"""Differentially audit the frozen Rust signed-limb alternate-radix step."""

from hashlib import sha256
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import json
import subprocess
import tarfile

from audit_native_alt_digit_selector import ARCHIVE, ARCHIVE_SHA256, MEMBER, digest, section
from screen_alt_digit_prime import LIMIT, NORM, TAU_RESIDUE, digit, norm

HERE = Path(__file__).resolve().parent
FRONT = 'prime-j0-alt-radix-native/src/bin/eisenstein_fixed.rs'
RECEIPT = HERE / 'native-alt-unit-step-audit.json'
RANDOM_SEED = 0x334110557
RANDOM_CASES = 4096


def signed_words(value: int) -> list[int]:
    magnitude = abs(value)
    assert magnitude < 1 << 192
    return [int(value < 0)] + [(magnitude >> (64*i)) & ((1 << 64)-1) for i in range(3)]


def from_words(values: list[int]) -> int:
    magnitude = sum(values[i+1] << (64*i) for i in range(3))
    return -magnitude if values[0] else magnitude


def inputs() -> list[tuple[int, int]]:
    result = [(residue, 0) for residue in range(NORM)]
    edges = [0, 1, -1, (1 << 64)-1, -(1 << 64)+1,
             1 << 64, -(1 << 64), (1 << 128)-1,
             -(1 << 128)+1, (1 << 130)-1, -(1 << 130)+1]
    result.extend((a, b) for a in edges for b in edges)
    rng = Random(RANDOM_SEED)
    for _ in range(RANDOM_CASES):
        a = rng.getrandbits(130) * (-1 if rng.getrandbits(1) else 1)
        b = rng.getrandbits(130) * (-1 if rng.getrandbits(1) else 1)
        result.append((a, b))
    return result


def native_source(front: str, windows: str) -> str:
    methods = [
        section(front, '    fn from_i8(value: i8)', '    fn rem_euclid_small('),
        section(windows, '    fn from_i32(value: i32)', '    fn rem_euclid_power_of_two('),
        section(windows, '    fn div_rem_small_radix(', '    fn div_rem_radix384_fast('),
        section(windows, '    fn times_alt_split_prime_small(', '    fn alt_split_prime_table_index('),
    ]
    constants = section(windows, 'const ALT_SPLIT_PRIME_NORM:',
                        'impl Signed192 {\n    fn times_alt_split_prime_small')
    selector = section(windows, 'fn nearest_alt_split_prime_digit(',
                       'fn alt_split_prime_unit_step(')
    step = section(windows, 'fn alt_split_prime_unit_step(',
                   'fn alt_orbit_omega_pair(')
    main = '''use std::io::{self, BufRead};
fn main() {
    let digit_pairs: Vec<(i16,i16)> = (0..=ALT_SPLIT_PRIME_DIGIT_LIMIT as i32)
        .map(nearest_alt_split_prime_digit).collect();
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let values: Vec<u64> = line.split(',').map(|word| word.parse().unwrap()).collect();
        assert_eq!(values.len(), 8);
        let a = Signed192 { negative: values[0] != 0,
            limbs: [values[1], values[2], values[3]] };
        let b = Signed192 { negative: values[4] != 0,
            limbs: [values[5], values[6], values[7]] };
        let (next_a, next_b, index, negative) =
            alt_split_prime_unit_step(a, b, &digit_pairs);
        println!("{},{},{},{},{},{},{},{},{},{}",
            u8::from(next_a.negative), next_a.limbs[0], next_a.limbs[1],
            next_a.limbs[2], u8::from(next_b.negative), next_b.limbs[0],
            next_b.limbs[1], next_b.limbs[2], index, negative);
    }
}
'''
    return ('#![allow(dead_code)]\n' + constants +
            '#[derive(Clone, Copy, Debug, Eq, PartialEq)]\n'
            'struct Signed192 { negative: bool, limbs: [u64; 3] }\n'
            'impl Signed192 {\n' + ''.join(methods) + '}\n' +
            selector + step + main)


def run() -> dict:
    receipt = {'schema': 1, 'archive': ARCHIVE.name,
               'archive_sha256': digest(ARCHIVE.read_bytes()),
               'front_member': FRONT, 'windows_member': MEMBER,
               'random_seed': RANDOM_SEED, 'random_cases': RANDOM_CASES,
               'status': 'running'}
    assert receipt['archive_sha256'] == ARCHIVE_SHA256
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        front_bytes = archive.extractfile(FRONT).read()
        windows_bytes = archive.extractfile(MEMBER).read()
    receipt['front_sha256'] = digest(front_bytes)
    receipt['windows_sha256'] = digest(windows_bytes)
    harness = native_source(front_bytes.decode(), windows_bytes.decode())
    receipt['harness_sha256'] = digest(harness.encode())
    cases = inputs()
    payload = ''.join(','.join(map(str, signed_words(a)+signed_words(b)))+'\n'
                      for a,b in cases).encode()
    receipt['input_sha256'] = digest(payload)
    receipt['case_count'] = len(cases)
    receipt['rustc_version'] = subprocess.run(
        ['rustc', '--version'], capture_output=True, text=True, check=True).stdout.strip()
    with TemporaryDirectory(prefix='alt-step-audit-') as temp:
        root = Path(temp)
        source_path, binary_path = root / 'audit.rs', root / 'audit'
        source_path.write_text(harness)
        built = subprocess.run(['rustc', '--edition=2021', '-O', str(source_path),
                                '-o', str(binary_path)], capture_output=True, text=True)
        receipt['compile_exit_code'] = built.returncode
        receipt['compile_stderr'] = built.stderr
        if built.returncode:
            receipt['status'] = 'compile_failed'
            return receipt
        receipt['binary_sha256'] = digest(binary_path.read_bytes())
        executed = subprocess.run([str(binary_path)], input=payload, capture_output=True)
        receipt['run_exit_code'] = executed.returncode
        receipt['run_stderr'] = executed.stderr.decode(errors='replace')
        receipt['stdout_sha256'] = digest(executed.stdout)
        if executed.returncode:
            receipt['status'] = 'run_failed'
            return receipt
    lines = executed.stdout.decode().splitlines()
    receipt['output_count'] = len(lines)
    mismatches = []
    max_next_norm = 0
    for case_index, ((a,b), line) in enumerate(zip(cases, lines)):
        values = list(map(int, line.split(',')))
        if len(values) != 10:
            mismatches.append({'case': case_index, 'reason': 'format', 'line': line})
            continue
        next_a, next_b = from_words(values[:4]), from_words(values[4:8])
        index, negative = values[8:]
        residue = (a + TAU_RESIDUE*b) % NORM
        expected_negative = int(residue > LIMIT)
        expected_index = NORM-residue if expected_negative else residue
        da, db = digit(expected_index)
        if expected_negative:
            da, db = -da, -db
        numerator = a-da+TAU_RESIDUE*(b-db)
        assert numerator % NORM == 0
        k = numerator // NORM
        expected_a, expected_b = 331*k-(b-db), k
        max_next_norm = max(max_next_norm, norm(next_a, next_b))
        if (next_a, next_b, index, negative) != (expected_a, expected_b,
                                                  expected_index, expected_negative):
            mismatches.append({'case': case_index, 'input': [a,b],
                               'actual': [next_a,next_b,index,negative],
                               'expected': [expected_a,expected_b,
                                            expected_index,expected_negative]})
    receipt['mismatch_count'] = len(mismatches)
    receipt['first_mismatches'] = mismatches[:10]
    receipt['maximum_next_norm'] = max_next_norm
    receipt['status'] = 'passed' if len(lines) == len(cases) and not mismatches else 'failed'
    return receipt


if __name__ == '__main__':
    result = run()
    RECEIPT.write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps(result, sort_keys=True))
    if result['status'] != 'passed':
        raise SystemExit(1)
