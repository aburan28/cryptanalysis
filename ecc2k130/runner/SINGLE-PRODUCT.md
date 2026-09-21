# Single-product packed multiplier

The packed GF(2^131) backend can use one polynomial product per field
multiplication, with word-parallel basis conversions at its boundaries.
The normal-basis representation, walk map, distinguished-point predicate,
reports and packed checkpoint format stay compatible. The old two-product
multiplier remains the default and the comparison control.

The additional [denominator cache](DENOMINATOR-CACHE.md) avoids a duplicated
Frobenius calculation in each step and measures 4.098489 B/s with this
multiplier on RTX PRO 6000. The results below describe the multiplier without denominator caching.

## Run the measured setting

From `ecc2k130/` on a checkout containing this change:

```bash
ECC_GPU=RTX-PRO-6000 ECC_PACKED_SINGLE_PRODUCT=1 \
  modal run modal_app.py::bench --packed \
  --batch 32 --threads 128 --min-blocks 4 \
  --steps 1024 --launches 32 --repeats 3
```

For a full GPU audit that checks reports, restarts and checkpoints before
measuring both benchmark mode and normal distinguished-point collection:

```bash
ECC_GPU=RTX-PRO-6000 ECC_PACKED_SINGLE_PRODUCT=1 \
  modal run packed_audit.py --output packed-audit.json
```

The audit retains raw output, source and binary hashes, compiler version,
GPU UUID/driver, all repetitions and failure status in the local JSON file
and the `ecc2k130` Modal Volume. A failed validation or incomplete benchmark
causes a nonzero local exit. Normal collection also requires a positive
report count, zero drops, and a matching corpus-file record count.

For a directly built binary:

```bash
make -B gpu ARCH='-gencode arch=compute_120,code=sm_120' \
  BATCH=32 THREADS=128 MINBLOCKS=4 PACKED_SINGLE_PRODUCT=1
python3 codegen/testpackedclient.py ./ecc2k130
./ecc2k130 --curve 131 --packed --bench --steps 1024 --launches 32 --verify 0
```

Set the multiplier option to `0` for a two-product comparison. The Modal
environment setting is fixed for both the baked binary and every subsequent
rebuild. Kernel startup output and benchmark identity state the active
multiplier. Changing a make variable requires a rebuild (`-B` above).

Changing occupancy can change the automatic worker count. To resume an
existing packed checkpoint, explicitly preserve its worker count and batch
size; the multiplier itself does not require checkpoint conversion. The
new four-block setting automatically uses 96,256 worker threads on the
188-SM RTX PRO 6000, versus 48,128 for the previous two-block setting.

## Final integrated audit

The [final audit JSON](benchmarks/single-product/final-audit.json) records a
successful run of `packed_audit.py` from source `d2eb5a8`, using the documented
four-block configuration on one RTX PRO 6000 allocation:

| Mode | Repetitions | Median billion iterations/s | Range |
|---|---:|---:|---:|
| Benchmark | 3 | **3.511807** | 3.510384–3.512679 |
| Normal DP cutoff 34, restarts and corpus writing | 3 | **3.483697** | 3.483651–3.483863 |

Every repetition completed 100,931,731,456 scalar walk iterations. Each
collection repetition wrote **2,633 records and dropped zero**, and its corpus
size matched the report count. The GPU integration suite passed before timing.
CPU trail replay was disabled during timed collection after this separate
correctness gate; synchronization, restarts and host report processing were
included. Setup was excluded. The JSON preserves source/binary hashes and the
compiler/GPU identity; its GPU clock/state snapshot was taken before validation,
not sampled throughout the timed runs.

This final benchmark is about **4.10 times** the user's 0.857163 B/s baseline.
The previous development comparisons below establish the effect of changing
only the multiplier before tuning occupancy.

## Development comparison

All rates below count complete scalar ECC2K-130 walk iterations on one NVIDIA
RTX PRO 6000 Blackwell Server Edition, CUDA 12.8.1, driver 580.95.05.
They include synchronization and host processing and exclude initial setup.
Batch is 32 and CUDA block size is 128 throughout.

| Multiplier | Blocks resident per SM | Repetitions | Median billion iterations/s |
|---|---:|---:|---:|
| Two-product control | 2 | 2 | 2.956981 |
| Single-product | 2 | 3 | 3.366572 |
| Single-product | 4 | 3 | **3.507395** |

The two-block control and candidate were alternated on the same GPU allocation;
that comparison isolates the multiplier improvement (13.85%). The four-block
measurement used a separate allocation after GPU integration validation, with
rates **3.508560, 3.507395, 3.506162 B/s**. The four-block kernel used 128
registers/thread and reported 304 local bytes/thread. Each repetition completed
**100,931,731,456** scalar iterations: 3,080,192 walks × 1,024 steps × 32 launches.
The two-block repetitions completed 50,465,865,728 iterations each.

These development measurements used source `29bf9d8771daabb6d477e6ea12403f068a4dd50b`.
Raw outputs are preserved in the [multiplier comparison](benchmarks/single-product/multiplier-comparison.json),
[occupancy screen](benchmarks/single-product/occupancy-screen.json) and
[validated four-block measurements](benchmarks/single-product/validated-four-blocks.json).
The [original packed-backend audit](PACKED.md) measured a bitsliced control at
0.852294 B/s; the user's original baseline was 0.857163 B/s. The 3.507395 B/s
result is about 4.09 times the latter. This is an implementation improvement;
it does not change the expected cryptanalytic work of the walk.

## Arithmetic and validation

The generator reuses the polynomial basis defined by `codegen/build.py`.
An input conversion applies the existing inverse parity recursion to packed
bits. It groups the suffix-XOR factors by shift distance: for a destination
coefficient `i` and power-of-two shift `h`, the exponent is
`popcount(i mod h)`. In characteristic two, its binary digits select masked
shifts `h * 2^j`. The output conversion applies the forward parity recursion
and folds the polynomial product back to the original normal basis.

The expensive carryless product is therefore evaluated once. Both conversions
use fixed word shifts and masks. The generator checks its linear transforms
on every basis vector against the independent IR evaluator; linearity extends
that equality to every input. `make check-cli` also compares the checked-in
generated header byte-for-byte with regenerated output.

`make test-packed` builds and checks both multipliers against the independent
field reference, including all 17,161 pairs of unit coefficients, dense/random
inputs, squaring, inversion and every Frobenius exponent used by the walk.
The GPU integration test independently checks real report replay, restarts,
byte-identical resumed execution, scalar iteration counting, preservation of
incompatible checkpoints, and overdue restarts without false reports.
The development audit also resumed a two-product checkpoint with the
single-product implementation and matched the uninterrupted two-product
checkpoint byte-for-byte.

Performance on other GPUs has not been measured. Nsight profiling is not
required for these measurements; the earlier Modal profiler preparation
failure remains a separate operational issue.
