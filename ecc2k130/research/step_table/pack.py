"""Pack verified synthetic step-table prefixes for separate GPU experiments.

The binary is k-major/h-minor, nine little-endian 32-bit words per point in
polynomial basis: x[0:4], y[0:4], x_top | (y_top << 3).  Negative y is y XOR x.
This matches only the existing nine-word storage layout, not its field basis
or selector/tag ABI. The fast packed client uses a different polynomial basis.
"""

import argparse
import hashlib
import json
import pathlib
import re
import struct

import table

CORE_KEYS = ('schema', 'scope', 'm', 'branches', 'seed', 'ell', 'eigenvalue', 'knownScalar',
             'basis', 'generator', 'target', 'rows', 'conjugateLayout', 'conjugates')


def columns(header, name):
    body = re.search(r'\b%s\[131\]\[3\] = \{(.*?)\n\};' % name, header, re.S)
    if body is None:
        raise ValueError('missing basis matrix ' + name)
    values = []
    for row in re.findall(r'\{([^}]+)\}', body.group(1)):
        limbs = re.findall(r'0x[0-9a-f]+', row)
        if len(limbs) != 3:
            raise ValueError('invalid basis matrix row')
        values.append(sum(int(v, 16) << (64 * i) for i, v in enumerate(limbs)))
    if len(values) != 131:
        raise ValueError('invalid basis matrix size')
    return values


def linear(value, matrix):
    if not 0 <= value < 1 << 131:
        raise ValueError('coordinate exceeds 131 bits')
    result = 0
    while value:
        low = value & -value
        result ^= matrix[low.bit_length() - 1]
        value ^= low
    return result


def pack(record, branches):
    core = {k: record[k] for k in CORE_KEYS}
    identity = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if identity != record['identitySha256']:
        raise ValueError('table identity mismatch')
    if (record['schema'] != 'ecc2k-step-table-v1' or record['scope'] != 'synthetic-reference-only' or
            record['m'] != 131 or record['basis'] != 'permuted-type-II-ONB' or
            record['knownScalar'] != str(table.KNOWN)):
        raise ValueError('unsupported table identity')
    sourceBranches = record['branches']
    if branches not in (8, 16, 32, 64) or branches > sourceBranches:
        raise ValueError('invalid prefix size')
    if len(record['rows']) != sourceBranches or len(record['conjugates']) != 131 * sourceBranches:
        raise ValueError('incomplete table')
    headerPath = table.ROOT / 'generated/eccF131.h'
    header = headerPath.read_text()
    toPb, toNb = columns(header, 'GAMMA_TO_PB'), columns(header, 'Z_TO_ONB')
    for i in range(131):
        if linear(linear(1 << i, toPb), toNb) != 1 << i:
            raise AssertionError('basis matrices are not inverses')
    data = bytearray()
    field = table.Onb(131)
    for k in range(131):
        for h in range(branches):
            row = record['rows'][h]
            if row['branch'] != h:
                raise ValueError('wrong branch order')
            coords = [int(v, 16) for v in record['conjugates'][k * sourceBranches + h]]
            expected = [field.toCoords(field.frob(field.fromCoords(int(row[c], 16)), k)) for c in ('x', 'y')]
            if coords != expected:
                raise ValueError('invalid conjugate')
            x, y = [linear(v, toPb) for v in coords]
            words = [(x >> (32 * i)) & 0xffffffff for i in range(4)]
            words += [(y >> (32 * i)) & 0xffffffff for i in range(4)]
            words += [(x >> 128) | ((y >> 128) << 3)]
            data.extend(struct.pack('<9I', *words))
            # Exact packed load including its implicit negation, then convert
            # both coordinates back with the independent inverse matrix.
            unpacked = struct.unpack('<9I', data[-36:])
            px = sum(unpacked[i] << (32 * i) for i in range(4)) | ((unpacked[8] & 7) << 128)
            py = sum(unpacked[4 + i] << (32 * i) for i in range(4)) | ((unpacked[8] >> 3) << 128)
            if [linear(px, toNb), linear(py, toNb)] != coords or linear(py ^ px, toNb) != coords[0] ^ coords[1]:
                raise AssertionError('packed coordinate/sign round trip failed')
    metadata = {'schema': 'ecc2k-packed-step-prefix-v1', 'sourceTableSha256': identity,
                'branches': branches, 'frobeniusPowers': 131, 'entries': 131 * branches,
                'coordinateBasis': 'polynomial', 'polynomial': 'z^131+z^13+z^2+z+1',
                'layout': 'k-major, h-minor, little-endian uint32[9]: x_lo[4], y_lo[4], x_top|y_top<<3',
                'bytes': len(data), 'binarySha256': hashlib.sha256(data).hexdigest(),
                'basisHeaderSha256': hashlib.sha256(headerPath.read_bytes()).hexdigest(),
                'rows': record['rows'][:branches], 'gpuMeasured': False,
                'compatibility': 'new synthetic walk; not production campaign/checkpoint compatible; h>=16 needs wider tags'}
    return bytes(data), metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('table', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.table.read_text())
    args.out.mkdir(parents=True, exist_ok=False)
    for branches in (8, 16, 32, 64):
        if branches > record['branches']:
            continue
        data, meta = pack(record, branches)
        (args.out / ('table%d.bin' % branches)).write_bytes(data)
        (args.out / ('table%d.json' % branches)).write_text(json.dumps(meta, indent=2) + '\n')
        print('%d branches: %d entries, %d bytes, SHA-256 %s' %
              (branches, meta['entries'], len(data), meta['binarySha256']))


if __name__ == '__main__':
    main()
