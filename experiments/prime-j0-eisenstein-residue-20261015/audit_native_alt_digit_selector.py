#!/usr/bin/env python3
"""Exhaustively compare the frozen Rust digit selector with an independent model."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import tarfile

from screen_alt_digit_prime import LIMIT, NORM, TAU_RESIDUE, digit, norm

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'alt-radix-native-provenance.tar.gz'
ARCHIVE_SHA256 = '38194c291c28fe76efd057cdb6f08c60784e0ce9bc0c5dbdadea9cc9113b7090'
MEMBER = 'prime-j0-alt-radix-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs'
RECEIPT = HERE / 'native-alt-digit-selector-audit.json'


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def section(source: str, start: str, end: str) -> str:
    assert source.count(start) == 1, start
    start_at = source.index(start)
    assert source.count(end, start_at) == 1, end
    return source[start_at:source.index(end, start_at)]


def run() -> dict:
    receipt = {'schema': 1, 'archive': ARCHIVE.name,
               'archive_sha256': digest(ARCHIVE.read_bytes()),
               'member': MEMBER, 'status': 'running'}
    assert receipt['archive_sha256'] == ARCHIVE_SHA256
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        archived = archive.extractfile(MEMBER)
        assert archived is not None
        source_bytes = archived.read()
    receipt['member_sha256'] = digest(source_bytes)
    source = source_bytes.decode()
    constants = section(source, 'const ALT_SPLIT_PRIME_NORM:', 'impl Signed192 {\n    fn times_alt_split_prime_small')
    selector = section(source, 'fn nearest_alt_split_prime_digit(', 'fn alt_split_prime_unit_step(')
    receipt['selector_sha256'] = digest(selector.encode())
    harness = ("#![allow(dead_code)]\n" + constants + selector +
               "fn main() {\n"
               "    for residue in 0..=ALT_SPLIT_PRIME_DIGIT_LIMIT as i32 {\n"
               "        let (a, b) = nearest_alt_split_prime_digit(residue);\n"
               "        println!(\"{residue},{a},{b}\");\n"
               "    }\n"
               "}\n")
    receipt['harness_sha256'] = digest(harness.encode())
    version = subprocess.run(['rustc', '--version'], capture_output=True, text=True, check=True)
    receipt['rustc_version'] = version.stdout.strip()
    with TemporaryDirectory(prefix='alt-digit-audit-') as temp:
        root = Path(temp)
        source_path, binary_path = root / 'audit.rs', root / 'audit'
        source_path.write_text(harness)
        compile_command = ['rustc', '--edition=2021', '-O', str(source_path), '-o', str(binary_path)]
        built = subprocess.run(compile_command, capture_output=True, text=True)
        receipt['compile_exit_code'] = built.returncode
        receipt['compile_stderr'] = built.stderr
        if built.returncode:
            receipt['status'] = 'compile_failed'
            return receipt
        receipt['binary_sha256'] = digest(binary_path.read_bytes())
        executed = subprocess.run([str(binary_path)], capture_output=True)
        receipt['run_exit_code'] = executed.returncode
        receipt['run_stderr'] = executed.stderr.decode(errors='replace')
        receipt['stdout_sha256'] = digest(executed.stdout)
        if executed.returncode:
            receipt['status'] = 'run_failed'
            return receipt
    lines = executed.stdout.decode().splitlines()
    receipt['residue_count'] = len(lines)
    mismatches = []
    pairs = []
    max_norm = 0
    for residue, line in enumerate(lines):
        values = tuple(map(int, line.split(',')))
        if len(values) != 3 or values[0] != residue:
            mismatches.append({'residue': residue, 'actual_line': line, 'reason': 'format'})
            continue
        _, a, b = values
        pairs.append((a, b))
        expected = digit(residue)
        value_norm = norm(a, b)
        max_norm = max(max_norm, value_norm)
        if (a, b) != expected or (a + TAU_RESIDUE*b-residue) % NORM or value_norm >= NORM:
            mismatches.append({'residue': residue, 'actual': [a, b],
                               'expected': list(expected), 'norm': value_norm})
    receipt['pair_sha256'] = digest(json.dumps(pairs, separators=(',', ':')).encode())
    receipt['maximum_digit_norm'] = max_norm
    receipt['mismatch_count'] = len(mismatches)
    receipt['first_mismatches'] = mismatches[:10]
    receipt['status'] = 'passed' if len(lines) == LIMIT+1 and not mismatches else 'failed'
    return receipt


if __name__ == '__main__':
    result = run()
    RECEIPT.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    if result['status'] != 'passed':
        raise SystemExit(1)
