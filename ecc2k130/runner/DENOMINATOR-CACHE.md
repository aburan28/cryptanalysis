# Cache packed walk denominators

The packed walk computes `d = x + sigma^j(x)` in its forward batch-product
pass and uses the same value during the reverse pass. `PACKED_CACHE_DENOM=1`
keeps this value in scratch storage and avoids the second Frobenius computation.
The jump index fits in the unused high bits of the fifth scratch word, removing
the separate local `js` array. Those bits are masked out before any field use.

This changes neither the walk map nor its reports or packed checkpoints. The
cache is transient, rebuilt before use on every step, and excluded from
checkpoint storage. GPU allocation sizing accounts for its additional 20
bytes per concurrent walk. The original path remains the default.

The additional [Frobenius networks](FROBENIUS-NETWORK.md) raise measured
throughput to 5.832583 B/s with this cache enabled. The measurements below
describe denominator caching before that additional optimization.

## Run the measured configuration

```bash
ECC_GPU=RTX-PRO-6000 ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
  modal run modal_app.py::bench --packed \
  --batch 32 --threads 128 --min-blocks 6 \
  --steps 1024 --launches 32 --repeats 3
```

To independently check GPU report replay, restarts and checkpoints, followed
by repeated benchmark and normal DP-34 collection measurements:

```bash
ECC_GPU=RTX-PRO-6000 ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
  modal run packed_audit.py --min-blocks 6 --output denominator-cache-audit.json
```

For a directly built binary:

```bash
make -B gpu ARCH='-gencode arch=compute_120,code=sm_120' \
  BATCH=32 THREADS=128 MINBLOCKS=6 PACKED_SINGLE_PRODUCT=1 PACKED_CACHE_DENOM=1
python3 codegen/testpackedclient.py ./ecc2k130
./ecc2k130 --packed --curve 131 --bench --steps 1024 --launches 32 --verify 0
```

Set `ECC_PACKED_CACHE_DENOM=0` on Modal, or `PACKED_CACHE_DENOM=0` for make,
to reproduce an uncached control. The Modal flag is preserved through image
creation and rebuilds and recorded in benchmark identity. Kernel startup also
prints the cache mode. Other GPUs have not been measured.

Changing the occupancy setting can change the automatic worker count. To resume
an existing packed checkpoint, preserve its worker count and batch explicitly.
Changing only the cache mode is compatible with the same checkpoint.

## Final integrated audit

The [final audit](benchmarks/denominator-cache/final-audit.json) ran the documented
Modal command from source `7d86a84`, with six resident blocks/SM:

| Mode | Repetitions | Median billion scalar iterations/s | Range |
|---|---:|---:|---:|
| Benchmark | 3 | **4.098489** | 4.094088–4.099016 |
| DP cutoff 34, restarts and corpus writing | 3 | **4.061011** | 4.058859–4.062382 |

All six repetitions completed **151,397,597,184 scalar iterations** each. Each
collection run wrote **3,900 records**, dropped none, and had a matching corpus
file size. Full GPU integration passed before timing. CPU trail replay was
then disabled during timed collection. Synchronization, restarts and host
report processing are included; initial setup is excluded.

The JSON retains source and binary hashes, compiler/GPU identity, raw outputs,
all repetitions and the successful validation result. The GPU state snapshot
was taken before validation, not sampled throughout timing. The source digest
of the published implementation matches this audited source; subsequent changes
add only documentation and evidence.

## Controlled development comparison

The [raw comparison](benchmarks/denominator-cache/development-comparison.json)
used source `c5e6bcd`, CUDA 12.8.1 and driver 580.95.05 on one RTX PRO 6000
Blackwell Server Edition. All builds used the single-product multiplier,
batch 32 and block size 128. Three rounds alternated control, cached4 and
cached6 within the same GPU allocation:

| Configuration | Median billion scalar iterations/s | Range |
|---|---:|---:|
| No cache, four resident blocks/SM | 3.506509 | 3.506357–3.508939 |
| Cache, four resident blocks/SM | 4.024103 | 4.023724–4.025189 |
| Cache, six resident blocks/SM | **4.094367** | 4.094112–4.095766 |

The unchanged-occupancy comparison improves throughput by 14.76%; the tuned
six-block configuration improves it by 16.76%. The six-block runs each
completed 151,397,597,184 full scalar walk iterations: 4,620,288 walks ×
1,024 steps × 32 launches. The four-block samples completed 100,931,731,456
iterations each. There is no bitsliced factor of 32 in the numerator.

Both cached configurations passed the full GPU integration suite before
timing: reference report replay, restarts, exact checkpoint resume, scalar
iteration accounting, incompatible-checkpoint preservation, and overdue
restarts without false reports. Their checkpoints also matched the uncached
control byte-for-byte at a common worker count and step count.

These benchmark results establish approximately 4.09 B/s on the stated GPU;
they do not establish the 60 B/s goal or performance on other architectures.
