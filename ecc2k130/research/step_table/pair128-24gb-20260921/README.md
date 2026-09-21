# Materialized pair-sum table within a 24 GB budget

Generation completed on 2026-09-21. `pairs.bin` contains real computed point
coordinates, with 20,244,545,536 bytes allocated on disk for a
20,244,542,976-byte payload. It is not a sparse reservation.

| Property | Value |
| --- | ---: |
| Base branches H | 128 |
| Frobenius powers | 131 |
| Signs per conjugate | 2 |
| Signed source directions | 33,536 |
| Unordered pairs with repetition | 562,348,416 |
| Bytes per pair | 36 |
| Payload bytes | 20,244,542,976 |
| Decimal GB | 20.244542976 |
| Coordinate budget | 24,000,000,000 bytes |

The construction uses the public ECC2K-130 generator and the **synthetic**
target Q=[65537]P. It does not use the challenge target. This artifact is a
precomputed sum table; it does not implement the intermediate selector needed
to replace two walk updates with one addition, and it establishes no rho or
GPU speedup.

Payload SHA-256:

```
809ae24f958e97f9d6f8854322ccd8ea62dc5660759619d32001a150be4e5a65
```

## Files and custody

* `coefficients.json`: deterministic construction seed, subgroup parameters,
  generator/target, and all 128 (a,b) coefficient pairs.
* `manifest.json`: sizes, hashes, complete-generation receipt, validation
  counts, compiler/platform/commands, and measured construction duration.

The 20.24 GB `pairs.bin` payload and 1.2 MB `directions.bin` are deliberately
not committed to Git. They are published through the repository's
`tables/catalog.json`; the manifest binds their sizes and SHA-256 hashes. The
original local generation directory also retains logs, executable, field
vectors, inputs, and a hash-matching source snapshot.

## Lookup and coefficient recovery

For base branch h in [0,128), Frobenius power k in [0,131), and sign eps in
{0,1}, the signed direction index is

```
d = 2 * (128*k + h) + eps
delta[d] = (-1)^eps * sigma^k(a[h]*P + b[h]*Q)
```

For two direction indices, order them so u<=v. The pair-sum entry is

```
index = v*(v+1)/2 + u
byte_offset = 36*index
pairs[index] = delta[u] + delta[v]
```

All indexing and offsets must use 64-bit arithmetic. The coefficient labels
for a direction are `(-1)^eps * eigenvalue^k * (a[h],b[h]) mod ell`; sum the
two direction labels to recover a pair's labels. This avoids storing another
two large scalars per pair.

Every entry has nine **little-endian uint32** words in polynomial basis
`z^131+z^13+z^2+z+1`:

```
word 0..3: x bits 0..127
word 4..7: y bits 0..127
word 8 bits 0..2: x bits 128..130
word 8 bits 3..5: y bits 128..130
```

The point at infinity is encoded as eight zero words followed by
`0x80000000`. Other high bits are reserved and must be zero. There are exactly
16,768 infinity entries, one for each source point/inverse pair. Diagonal
entries contain proper point doublings. A reader must handle infinity; this
is a new table/index format, not a drop-in production checkpoint format.

To read one entry without loading the 20 GB file into RAM:

```python
from pathlib import Path
import struct

root = Path('/path/to/verified/table-cache')
u, v = sorted((0, 2))
assert 0 <= u <= v < 33536
index = v * (v + 1) // 2 + u
with (root / 'pairs.bin').open('rb') as source:
    source.seek(36 * index)
    words = struct.unpack('<9I', source.read(36))
if words == (0, 0, 0, 0, 0, 0, 0, 0, 0x80000000):
    point = None
else:
    assert words[8] & ~63 == 0
    x = sum(words[i] << (32*i) for i in range(4)) | ((words[8] & 7) << 128)
    y = sum(words[4+i] << (32*i) for i in range(4)) | ((words[8] >> 3) << 128)
    point = (x, y)
```

## Validation performed

* 1,307 field product/inverse vectors from independent Python polynomial arithmetic.
* All 128 base entries checked as aP+bQ and as [a+65537*b]P.
* Signed Frobenius orbit duplicates rejected using the known synthetic scalars.
* All 33,536 source directions checked on the curve, with Frobenius closure.
* All 562,348,416 pair results checked on the curve during generation.
* One pair per inversion batch also checked against individual affine addition.
* 4,192 positive conjugates and their signs matched the existing independent
  normal-basis reference prefix.
* 16 base entries matched separate Python scalar multiplication.
* 1,075 disk entries, including random, boundary, doubling, and inverse-pair
  cases, matched independent Python point addition.
* The entire payload was read to calculate SHA-256 after writes completed and
  the file was synchronized to disk.

The generator used eight CPU threads and bounded batches. The recorded
preparation/generation/audit/hash duration was 55.49 seconds; this is a table
construction measurement, not rho throughput. Compilation is outside that
duration. Full commands and environment are in `manifest.json`.

Reproduce into a new directory from the repository root:

```sh
python3 ecc2k130/research/step_table/generate_large_pairs.py \
  --out ecc2k130/research/step_table/pair128-24gb-new \
  --branches 128 --threads 8 --audit-samples 1024
```
