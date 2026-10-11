# Pair-sum table for an 88 GB memory budget

The complete 256-branch table occupies **80,976,964,608 bytes** (80.98 decimal
GB, 75.42 GiB), leaving 7,023,035,392 bytes within an 88 GB coordinate budget.
It is fully materialized on disk, not a sparse allocation.

| Property | Value |
| --- | ---: |
| Base branches | 256 |
| Frobenius powers | 131 |
| Signed directions | 67,072 |
| Unordered pairs with repetition | 2,249,360,128 |
| Bytes per entry | 36 |
| Infinity entries | 33,536 |

`pairs.bin` SHA-256:

```
7b261b965ab740479dc28569df3938c2291321964afd0d6e4ac7f7b54e075c32
```

The construction uses the public ECC2K-130 generator and synthetic target
Q=[65537]P. The original 128-branch table is preserved separately. The first
128 coefficient pairs match it, but direction strides and file offsets change.

## Access

For branch h, Frobenius exponent k and sign eps:

```
d = 2*(256*k+h)+eps
delta[d] = (-1)^eps * sigma^k(a[h]*P+b[h]*Q)
```

For two direction IDs, order them as u<=v:

```
index = v*(v+1)/2+u
byte_offset = 36*index
pairs[index] = delta[u]+delta[v]
```

Use 64-bit pair indices, multiplication and byte offsets. Direction IDs now
exceed 16 bits, and pair indices exceed signed 32 bits.

Encoding: nine little-endian uint32 words in the polynomial basis
z^131+z^13+z^2+z+1. Words 0..3 hold low x, 4..7 low y, and word 8 holds
`x_top | (y_top << 3)`. Infinity is eight zero words followed by `0x80000000`;
all other high bits are reserved. Coefficients can be recovered from the two
directions using `coefficients.json`, without another large coefficient array.

For an old 128-branch direction d, use
`k,h=divmod(d//2,128)` and `new_d=2*(256*k+h)+(d&1)`. Recompute the triangular
pair index from the two remapped directions.

## Evidence

`manifest.json` records the completed generation, full-file checksum,
source/binary hashes, commands and source snapshot. Checks include:

* All 2,249,360,128 computed results checked on the curve.
* 2,099 disk samples matched independent Python point addition.
* 4,192 earlier normal-basis conjugates and their signs matched.
* 1,307 independent field vectors and 16 independent scalar checks passed.
* `extension-audit.json` confirms all 33,536 old signed directions and 2,053
  remapped pair samples agree with the 128-branch table.

All 13 unit tests passed. Preparation, generation, independent checks and full
hashing took 230.99 seconds; compilation is excluded. This is a precomputation
measurement, not rho or GPU throughput.

The 80.98 GB `pairs.bin` and 2.4 MB `directions.bin` are not committed to Git.
They are available through `tables/catalog.json`, while this directory keeps
the coefficient labels, receipt and extension audit needed to verify them.

The artifact supplies pair sums. It does not implement the intermediate
branch predictor needed to replace two walk updates with one point addition,
and it is not compatible with existing production walk/checkpoint identities.

Reproduce into a new directory:

```sh
python3 ecc2k130/research/step_table/generate_large_pairs.py \
  --out ecc2k130/research/step_table/pair256-88gb-new \
  --branches 256 --budget-gb 88 --threads 8 --audit-samples 2048
```
