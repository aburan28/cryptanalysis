# Polynomial-basis batch chains

The packed walk can retain batch-product prefixes, partial inverses and lambda
in the existing optimal polynomial basis. This avoids repeated basis
conversions between consecutive multiplications. Coordinates, Frobenius powers,
Hamming weights, reports and packed checkpoints keep their normal-basis
representation. The field inversion helper is unchanged, with conversions at
its boundary.

The additional [paired-product configuration](PAIRED-PRODUCTS.md) measures
6.211583 B/s with polynomial chains enabled. The results below describe the
chain implementation before that additional optimization.

## Run the measured configuration

```bash
ECC_GPU=RTX-PRO-6000 \
ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 ECC_PACKED_POLY_CHAIN=1 \
  modal run modal_app.py::bench --packed \
  --batch 32 --threads 128 --min-blocks 4 \
  --steps 1024 --launches 32 --repeats 3
```

For GPU arithmetic checks, complete-walk integration checks, and repeated
benchmark/normal-collection measurements:

```bash
ECC_GPU=RTX-PRO-6000 \
ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 ECC_PACKED_POLY_CHAIN=1 \
  modal run packed_audit.py --min-blocks 4 --output polynomial-chain-audit.json
```

For a direct CUDA build:

```bash
make -B gpu ARCH='-gencode arch=compute_120,code=sm_120' \
  BATCH=32 THREADS=128 MINBLOCKS=4 PACKED_SINGLE_PRODUCT=1 \
  PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 PACKED_PERM_SIGMA=3 PACKED_POLY_CHAIN=1
```

The new option defaults to zero and requires denominator caching. It adds a
second 20-byte denominator representation per concurrent walk; GPU allocation
sizing accounts for it. This scratch storage and the batch prefixes are not
part of checkpoints. Preserve the original worker count and batch when
resuming, because changing occupancy can change automatic worker count.

## Final integrated audit

The [final audit](benchmarks/polynomial-chain/final-audit.json) ran source
`9d7fa99` on one RTX PRO 6000 Blackwell Server Edition, CUDA 12.8.1 and
driver 580.95.05:

| Mode | Repetitions | Median billion scalar iterations/s | Range |
|---|---:|---:|---:|
| Benchmark | 3 | **6.058466** | 6.057843–6.059248 |
| DP cutoff 34, restarts and corpus writing | 3 | **5.974502** | 5.973729–5.977002 |

Every repetition completed **100,931,731,456** complete scalar walk iterations:
3,080,192 walks × 1,024 steps × 32 launches. Each collection run wrote
**2,633 records**, dropped zero, and had a matching corpus-file record count.
CPU trail replay was disabled after the separate correctness gates passed.
Synchronization, restarts and host report processing are timed; initial setup
is excluded. The GPU state snapshot is taken before validation and does not
trace clock frequencies throughout the timed runs.

The published source digest matches the audited source. The JSON retains raw
outputs, compiler/GPU identity, source/binary hashes and successful validation.
These results do not establish 60 B/s. Other GPU architectures are unmeasured.

## Controlled development comparison

The [development comparison](benchmarks/polynomial-chain/development-comparison.json)
alternated three builds on one GPU for three rounds, keeping the single-product
multiplier, by-value arguments, Frobenius networks and denominator cache enabled:

| Configuration | Median B iterations/s | Range |
|---|---:|---:|
| Normal-basis chain, six blocks/SM | 5.832342 | 5.831165–5.837701 |
| Polynomial chain, four blocks/SM | **6.054107** | 6.049952–6.054995 |
| Polynomial chain, six blocks/SM | 5.537085 | 5.523034–5.581942 |

The selected four-block configuration is 3.80% faster than that control. This
comparison changes both the intermediate representation and occupancy; it
does not isolate either change alone. The six-block polynomial configuration
was slower and is not recommended. Both polynomial configurations passed GPU
integration and matched the control checkpoint byte-for-byte at common
worker/step counts.

## Exact reduction and validation

For the existing polynomial-basis generator, the minimal polynomial is

`f=(x^3+x^2+1)(1+x^64+x^96+x^112+x^120+x^128)+x^124`.

Let `A=1+x+x^3` and let `F` be the reciprocal polynomial. The generator uses
`F=A(1+x^8+x^16+x^32+x^64+x^128)+x^7` and the identity
`F(F+A)=x^7+A^2*x^256`. Therefore `(F+A)/x^7` is a sparse truncated inverse
sufficient for reducing a degree-260 product. The emitted reduction uses word
shifts, bit reversals and XOR; no approximate arithmetic is involved.

The generator compares reduction with polynomial long division on every
input basis vector and 1,000 dense cases. `make check-cli` verifies that the
checked-in header matches regenerated output. Host arithmetic tests compare
the polynomial multiplication and basis conversions with the independent
normal-basis reference, including all 17,161 basis pairs.

The final GPU arithmetic gate passed:

- 3,120 Frobenius vectors;
- 1,261 polynomial reductions against long division;
- 18,185 polynomial products, including all 17,161 basis pairs.

The complete-walk GPU integration gate also passed report replay, restarts,
exact checkpoint resume, scalar accounting, incompatible-checkpoint
preservation and overdue-guard checks. Compiler/resource evidence alone is
never used as a throughput result.
