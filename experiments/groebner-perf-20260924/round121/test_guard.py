"""Cross-check the bounded field-pair probe against a separate set oracle."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import random
import sys

from guard_query import HERE, FieldObstruction, abi


def leading(row):
    return max(row, key=lambda term: (term.bit_count(), -term))


def multiply(row, mask):
    result = set()
    for term in row:
        target = term | mask
        if target in result:
            result.remove(target)
        else:
            result.add(target)
    return result


def oracle(nvars, rows):
    basis = [set(row) for row in rows]
    leads = [leading(row) for row in basis]
    for i, head in enumerate(leads):
        for bit in range(nvars):
            if not (head >> bit & 1):
                continue
            value = multiply(basis[i], 1 << bit)
            while value:
                top = leading(value)
                reducer = next((j for j, lead in enumerate(leads)
                                if (top & lead) == lead), None)
                if reducer is None:
                    return i, bit, top
                product = multiply(basis[reducer], top & ~leads[reducer])
                if not product or leading(product) != top:
                    return 'invalid'
                value.symmetric_difference_update(product)
    return None


def view(nvars, rows):
    terms = [term for row in rows for term in sorted(row)]
    offsets = [0]
    for row in rows:
        offsets.append(offsets[-1] + len(row))
    term_buffer = (abi.U64 * len(terms))(*terms)
    offset_buffer = (abi.U64 * len(offsets))(*offsets)
    packed = abi.PackedInput(nvars, 0, 0, None, None)
    proof = abi.ProofView(1, nvars, 1, 0, len(rows), len(terms), 0,
                          term_buffer, offset_buffer, None, None)
    return packed, proof, term_buffer, offset_buffer


def main():
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    path = HERE / 'build' / ('field_obstruction' + suffix)
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt['binaries'][path.name]
    library = C.CDLL(str(path))
    library.find_field_obstruction.argtypes = [C.POINTER(abi.PackedInput),
        C.POINTER(abi.ProofView), abi.U64, C.POINTER(FieldObstruction)]
    library.find_field_obstruction.restype = C.c_int

    def native(nvars, rows, cap=1_000_000):
        packed, proof, terms, offsets = view(nvars, rows)
        stats = FieldObstruction()
        code = library.find_field_obstruction(C.byref(packed), C.byref(proof),
                                              cap, C.byref(stats))
        return code, stats

    rng = random.Random(20261009)
    controls = [(2, [{0}]), (3, [{1}]), (3, [{1, 2}])]
    for nvars in range(2, 7):
        for _ in range(40):
            rows = [set(rng.sample(range(1 << nvars),
                                   rng.randint(1, min(7, 1 << nvars))))
                    for _ in range(rng.randint(1, 5))]
            controls.append((nvars, rows))
    found = invalid = 0
    for nvars, rows in controls:
        expected = oracle(nvars, rows)
        code, stats = native(nvars, rows)
        if expected == 'invalid':
            assert code == 0 and stats.status == 3
            invalid += 1
            continue
        assert code == bool(expected), (nvars, rows, expected, code)
        assert stats.status == code and stats.work > 0
        if expected is not None:
            assert (stats.witness_row, stats.witness_bit, stats.witness_term) == expected
            found += 1
    code, stats = native(3, [{1, 2}], cap=0)
    assert code == 0 and stats.status == 2
    code, stats = native(13, [{1}])
    assert code == 0 and stats.status == 0
    code, stats = native(3, [{8}])
    assert code == 0 and stats.status == 3
    print('F4_FIELD_OBSTRUCTION_ORACLE_PASS', len(controls), found, invalid, flush=True)


if __name__ == '__main__':
    main()
