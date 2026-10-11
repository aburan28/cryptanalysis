"""Independent polynomial-space oracle for raw GPU affine witnesses."""
import argparse
import ctypes as ct
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import platform
import random
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rref(rows, columns):
    rows = list(rows)
    rank = 0
    for column in columns:
        chosen = next((j for j in range(rank, len(rows)) if rows[j] >> column & 1), None)
        if chosen is None:
            continue
        rows[rank], rows[chosen] = rows[chosen], rows[rank]
        for j in range(len(rows)):
            if j != rank and rows[j] >> column & 1:
                rows[j] ^= rows[rank]
        rank += 1
    return rows, rank


def original_rows(columns, e):
    return [sum(((coefficient >> j) & 1) << k for k, coefficient in enumerate(columns))
            for j in range(e)]


def expected_affine(columns, y, e):
    # Independent integer row reduction, constant at bit zero throughout.
    rows, rank = rref(original_rows(columns, e), range(y + 1, len(columns)))
    affine, dimension = rref(rows[rank:], range(1, y + 1))
    canonical, count = rref(affine, range(y + 1))
    return tuple(canonical[:count]), rank, dimension


def verify_record(columns, y, e, record):
    header = record[0] & 0xffffffff
    qrank, rank, unit = header & 255, (header >> 8) & 255, (header >> 16) & 1
    assert header == 0x80000000 | qrank | (rank << 8) | (unit << 16)
    expected, expected_qrank, expected_rank = expected_affine(columns, y, e)
    assert qrank == expected_qrank and rank == expected_rank
    assert qrank + rank <= e and rank <= y
    original = original_rows(columns, e)
    returned = []
    for i, packed in enumerate(record[1:]):
        row, witness = packed & 0xffffffff, packed >> 32
        if i >= rank and i != y:
            assert packed == 0
            continue
        if i == y and not unit:
            assert packed == 0
            continue
        assert witness and witness < 1 << e and row < 1 << (y + 1)
        reconstructed = 0
        for j in range(e):
            if witness >> j & 1:
                reconstructed ^= original[j]
        assert row == reconstructed
        if i == y:
            assert row == 1
        returned.append(row)
    canonical, count = rref(returned, range(y + 1))
    assert tuple(canonical[:count]) == expected
    return len(returned)


class Probe:
    def __init__(self, branches, y, e):
        self.branches, self.y, self.e = branches, y, e
        self.features = 1 + y * (y + 1) // 2
        self.path = HERE / 'build/projection-probe-metal.dylib'
        self.lib = lib = ct.CDLL(str(self.path))
        for name, result, arguments in (
            ('probe_create', ct.c_void_p, [ct.c_uint32] * 3),
            ('probe_destroy', None, [ct.c_void_p]),
            ('probe_error', ct.c_char_p, []),
            ('probe_device', ct.c_char_p, [ct.c_void_p]),
            ('probe_solve', ct.POINTER(ct.c_uint64), [ct.c_void_p, ct.POINTER(ct.c_uint32), ct.c_uint64, ct.c_uint32, ct.c_uint32])):
            function = getattr(lib, name)
            function.restype, function.argtypes = result, arguments
        self.handle = lib.probe_create(branches, y, e)
        if not self.handle:
            raise ValueError(lib.probe_error().decode())
        self.device = lib.probe_device(self.handle).decode()

    def solve(self, columns, symmetric=False):
        assert len(columns) == self.branches
        packed = (ct.c_uint32 * (self.features * self.branches))(*(c for row in columns for c in row))
        result = self.lib.probe_solve(self.handle, packed, ct.sizeof(packed), symmetric, True)
        if not result:
            raise RuntimeError(self.lib.probe_error().decode())
        return [list(result[b * (self.y + 2):(b + 1) * (self.y + 2)]) for b in range(self.branches)]

    def close(self):
        if self.handle:
            self.lib.probe_destroy(self.handle)
            self.handle = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rng = random.Random(2026100250)
    report = {'schema': 'gpu-affine-witness-oracle/1', 'status': 'RUNNING',
              'architecture': platform.machine(), 'platform': platform.platform(),
              'timing_eligible': False, 'cases': [], 'rows': 0, 'branches': 0,
              'sources': {p.name: sha(p) for p in HERE.iterdir() if p.suffix in ('.py', '.cpp', '.h', '.mm', '.metal')},
              'binary_sha256': sha(HERE / 'build/projection-probe-metal.dylib')}
    for y in range(1, 11):
        for e in (1, 2, 7, 16, 31, 32):
            branches = 64
            probe = Probe(branches, y, e)
            try:
                report['device'] = probe.device
                f = probe.features
                for trial in range(3):
                    matrices = [[rng.getrandbits(e) for _ in range(f)] for _ in range(branches)]
                    # Force a mixture of zero, inconsistent, affine, rank deficient
                    # and repeated/cancelled equations in every freshly overwritten table.
                    matrices[0] = [0] * f
                    matrices[1] = [1] + [0] * (f - 1)
                    matrices[2] = [rng.getrandbits(e) for _ in range(y + 1)] + [0] * (f - y - 1)
                    matrices[3] = [((1 << e) - 1) if rng.randrange(2) else 0 for _ in range(f)]
                    symmetric = trial == 1
                    if symmetric:
                        for high in range(8):
                            for low in range(high):
                                matrices[low + 8 * high] = matrices[high + 8 * low][:]
                    records = probe.solve(matrices, symmetric)
                    count = rows = 0
                    for branch in range(branches):
                        if symmetric and branch % 8 < branch // 8:
                            continue
                        rows += verify_record(matrices[branch], y, e, records[branch])
                        count += 1
                    report['rows'] += rows
                    report['branches'] += count
                    report['cases'].append({'variables': y, 'equations': e, 'trial': trial,
                                            'symmetric': symmetric, 'branches': count,
                                            'rows': rows, 'input_sha256': hashlib.sha256(json.dumps(matrices).encode()).hexdigest(),
                                            'output_sha256': hashlib.sha256(json.dumps([records[b] for b in range(branches) if not symmetric or b % 8 >= b // 8]).encode()).hexdigest()})
                # Deliberately corrupt a known unit witness/row: the oracle must reject it.
                records[1][-1] ^= 1
                try:
                    verify_record(matrices[1], y, e, records[1])
                except AssertionError:
                    pass
                else:
                    raise AssertionError('mutated row escaped independent replay')
            finally:
                probe.close()
        print('GPU_WITNESS_ORACLE_PASS', y, flush=True)
    for y, e in ((1, 1), (1, 2), (2, 2), (2, 3)):
        f = 1 + y * (y + 1) // 2
        matrices = [list(v) for v in itertools.product(range(1 << e), repeat=f)]
        probe = Probe(len(matrices), y, e)
        try:
            records = probe.solve(matrices)
            for columns, record in zip(matrices, records):
                report['rows'] += verify_record(columns, y, e, record)
            report['branches'] += len(matrices)
            report['cases'].append({'kind': 'exhaustive', 'variables': y, 'equations': e, 'branches': len(matrices)})
        finally:
            probe.close()
    # Explicit regression: feature-only RREF leaves several constant-one rows.
    probe = Probe(1, 1, 7)
    try:
        columns = [[58, 38]]
        records = probe.solve(columns)
        report['rows'] += verify_record(columns[0], 1, 7, records[0])
        report['branches'] += 1
        report['cases'].append({'kind': 'duplicate-unit-regression', 'columns': columns, 'records': records})
    finally:
        probe.close()
    # Actual frozen query specializations, independent of the native producer.
    fixture = HERE.parent / 'round40/fixtures/inputs.json.gz'
    report['fixture_sha256'] = sha(fixture)
    for item in json.loads(gzip.decompress(fixture.read_bytes())):
        y, e = item['ell'], item['n']
        if e > 32:
            continue
        x = 2 * y
        masks = [0] + [1 << j for j in range(y)] + [(1 << j) | (1 << k) for j in range(y) for k in range(j + 1, y)]
        index = {mask: j for j, mask in enumerate(masks)}
        branches = [0, (1 << x) - 1] + [rng.randrange(1 << x) for _ in range(14)]
        columns = []
        for branch in branches:
            row = [0] * len(masks)
            for monomial, coefficient in item['reference_anf']:
                fixed = monomial & ((1 << x) - 1)
                if branch & fixed == fixed:
                    row[index[monomial >> x]] ^= coefficient
            columns.append(row)
        probe = Probe(16, y, e)
        try:
            records = probe.solve(columns)
            for row, record in zip(columns, records):
                report['rows'] += verify_record(row, y, e, record)
            report['branches'] += 16
            report['cases'].append({'kind': 'original-ANF', 'name': item['name'], 'branch_ids': branches,
                                    'columns': columns, 'records': records})
        finally:
            probe.close()
    report['status'] = 'PASS'
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('GPU_WITNESS_ORACLE_PASS', report['branches'], 'branches;', report['rows'], 'row witnesses', flush=True)


if __name__ == '__main__':
    main()
