# Packed normal-basis CUDA backend

`--packed` selects a GF(2^131) backend that retains the existing ECC2K-130
iteration function, seed derivation, distinguished-point predicate and report
format. The original bitsliced backend remains available and remains the
default, including for existing checkpoints and other fields.

The latest [paired-product configuration](PAIRED-PRODUCTS.md) measures
**6.211583 B scalar iterations/s** and **6.126760 B/s** during normal
distinguished-point collection on RTX PRO 6000. Its guide includes all flags.

The latest [polynomial-chain configuration](POLYNOMIAL-CHAIN.md) measures
**6.058466 billion scalar iterations/s**, and **5.974502 B/s** during normal
distinguished-point collection, on RTX PRO 6000. Its guide includes all flags
and the complete GPU audit command.

The latest measured [Frobenius-network configuration](FROBENIUS-NETWORK.md)
reaches **5.832583 billion scalar iterations/s** on RTX PRO 6000, with
**5.737182 B/s** during normal distinguished-point collection. Its guide
contains the full opt-in flag set and audit command.

The opt-in [denominator cache](DENOMINATOR-CACHE.md), combined with the
single-product multiplier, measures **4.098489 billion scalar iterations/s**
on RTX PRO 6000. Its guide includes the exact flags and validation command.

An opt-in [single-product multiplier](SINGLE-PRODUCT.md) further raises measured
RTX PRO 6000 throughput to **3.511807 billion iterations/s** with four resident
blocks per SM. Enable it with `ECC_PACKED_SINGLE_PRODUCT=1` on Modal, or
`PACKED_SINGLE_PRODUCT=1` with make. The measurements below describe the original
two-product packed multiplier.

The final GPU audit on RTX PRO 6000 Blackwell Server Edition, CUDA 12.8.1,
source `c307bb6`, measured:

| Mode | Repetitions | Throughput (billion scalar iterations/s) |
|---|---:|---:|
| Bitsliced control, 49,283,072 walks | 1 | 0.852294 |
| Packed, 1,540,096 walks | 3 | **2.957961 median** (2.957695–2.958816) |
| Packed, 49,283,072 walks | 1 | **3.140074** |
| Packed, normal DP cutoff 34 and restarts | 1 | **2.938099** |

All modes used the same GPU allocation and executable. The normal-DP run
completed 100,931,731,456 iterations, wrote 2,605 reports and dropped none.
Reference replay was disabled during that timed run after the separate GPU
replay/restart/resume validation passed. Each sustained packed benchmark
repetition performed 50,465,865,728 iterations. Synchronization, DP fetching
and host processing are included; initial setup is excluded in both backends.
These are full-walk measurements, not multiplication microbenchmarks.

## Run it

```bash
ECC_GPU=RTX-PRO-6000 modal run modal_app.py::validate --packed
ECC_GPU=RTX-PRO-6000 modal run modal_app.py::bench \
  --packed --batch 32 --threads 128 --min-blocks 2 \
  --steps 1024 --launches 32 --repeats 3
```

For a directly built CUDA binary:

```bash
make gpu ARCH='-gencode arch=compute_120,code=sm_120'
./ecc2k130 --curve 131 --packed --bench --steps 1024 --launches 32 --verify 0
```

The packed backend advances **one walk per slot**, not 32 bit lanes. At 48,128
CUDA threads and batch 32, this is 1,540,096 concurrent walks. The client counts
exactly those scalar iterations; it does not retain the bitsliced factor of
32 in the throughput numerator. More steps per launch make a sustained test
practical despite the lower concurrent-walk count.

`bench`, `validate`, `autotune`, `profile`, `search`, and `fanout` accept the
packed flag. Packed search requires `--curve 131`. Generated-leaf and streaming
Karatsuba settings do not apply to this multiplier, and the Modal interface
rejects them rather than labeling duplicate builds as different candidates.
The bitsliced shared-memory-spilling option is also rejected in packed mode.
The original autolab/performance model describes bitsliced code and must not be
used to infer packed performance. Actual GPU timing selects settings.

For sustained collection after validation, `search` and `fanout` expose
`--verify`: use `--verify 0` when measuring collection throughput. Replaying a
normal-cutoff trail on the CPU can be expensive; this remains a separate
correctness check. The default verification budget remains four for backward
compatibility. Choose an unused run ID and use `--walks 0` for automatic GPU
worker sizing, or explicitly choose the desired parallel-walk count.

## Arithmetic

The representation is unchanged mathematically: bit i is the coefficient of
`gamma_(i+1)` in the permuted type-II normal basis used by `eccF131`. The bits
are packed into five little-endian 32-bit words rather than spread over 131
words of 32 parallel bit lanes. The upper 29 bits of the fifth word are zero.

The field identity

`gamma_i * gamma_j = gamma_(i+j) + gamma_(i-j)`

reduces multiplication to two packed polynomial products, one with the second
operand reversed. Indices fold using `gamma_k = gamma_(263-k)` and
`gamma_0 = 0`. Shifts, bit reversals and XOR combine the products into the
131-bit result. The 128-bit portions use the repository's integer-mask
carryless multiplication primitives; the final three bits are handled
explicitly. No integer carries are used as field additions.

Squaring interleaves the low 65 coefficients with the reversed high 66
coefficients. Frobenius powers repeat that permutation. Inversion uses the
same eight-multiplication Itoh–Tsujii addition chain as the existing field.
The walk still computes `sigma^j(R)+R` with
`j = 3 + ((HW(x)/2) mod 8)` and batches the affine denominators. Multiplication
is kept out of line to share its instruction body across the walk's call sites.

This changes the mapping to GPU registers and memory, not the random-walk
definition or the expected cryptanalytic work. The measured speedup is an
implementation result.

## Reports, restarts and checkpoints

Distinguished-point records use the existing seed, iteration count and three
64-bit limbs per coordinate. The CPU solver can replay packed reports and merge
their corpora with existing reports because the seed-to-point and walk maps are
the same. Use distinct run IDs for independent workers as before.

Marked walks are restarted between launches from their incremented seeds.
Overdue walks request a restart through a separate counter and do not emit
false distinguished points. The `--max-iters` check retains the existing
periodic guard schedule.

Packed checkpoints use **version 2, lanes=1** with five storage words per field
element. They are deliberately distinct from bitsliced/CPU checkpoints. Resume
with the same backend, batch, worker count and run ID. The client now refuses an
existing incompatible or incomplete checkpoint instead of silently starting
fresh and overwriting it. Start a different backend with a new checkpoint path
or a distinct Modal run ID; no automatic checkpoint conversion is performed.

## Validation

```bash
make test-packed
python3 codegen/testpackedclient.py ./ecc2k130
```

The host arithmetic test compares multiplication, squaring, inversion and all
walk Frobenius exponents against the independent reference, including every
unit coefficient and dense/random inputs. The GPU integration test checks:

- reference replay of real GF(2^131) reports across launches, restarts and resume;
- restarted seeds appearing in the compatible corpus format;
- byte-identical checkpoints for resumed and uninterrupted execution;
- scalar iteration accounting, with no bitsliced lane multiplier;
- refusal to read a packed checkpoint through the wrong backend, preserving it;
- overdue restarts with no false distinguished-point reports.

The standalone prototype also checked initial points and multi-step endpoints
against the reference before the backend was integrated. GPU performance on
other architectures has not been established by the RTX PRO 6000 measurements.
