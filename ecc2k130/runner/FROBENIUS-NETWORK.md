# Packed Frobenius permutation networks

The packed backend can apply the Frobenius powers used by the walk through
fixed bit-permutation networks. This replaces repeated squarings while
preserving the exact iteration, field representation, seeds, reports and
packed checkpoints. The measured configuration also passes the small field
operands by value and enables the previously measured denominator cache.

The additional [polynomial-chain configuration](POLYNOMIAL-CHAIN.md) measures
6.058466 B/s with these networks enabled. The results below describe the
network implementation before that additional change.

## Run the measured configuration

From `ecc2k130/`:

```bash
ECC_GPU=RTX-PRO-6000 \
ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 \
  modal run modal_app.py::bench --packed \
  --batch 32 --threads 128 --min-blocks 6 \
  --steps 1024 --launches 32 --repeats 3
```

The full audit first checks the GPU arithmetic and integration paths, then
measures both benchmark mode and normal distinguished-point collection:

```bash
ECC_GPU=RTX-PRO-6000 \
ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 \
  modal run packed_audit.py --min-blocks 6 --output Frobenius-audit.json
```

For a directly built CUDA binary, use these make variables:

```bash
make -B gpu ARCH='-gencode arch=compute_120,code=sm_120' \
  BATCH=32 THREADS=128 MINBLOCKS=6 PACKED_SINGLE_PRODUCT=1 \
  PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 PACKED_PERM_SIGMA=3
```

The options remain opt-in. `PACKED_PERM_SIGMA` is a bit mask:

| Value | Powers evaluated through the networks |
|---:|---|
| 0 | None; use the original repeated-squaring path |
| 1 | 3 through 10 |
| 2 | 16, 32 and 65 |
| 3 | Both groups; the measured recommendation |

Other exponents retain the original implementation. The first group handles
the walk jumps and some inversion steps; the second handles the large powers
in the inversion chain. `PACKED_BY_VALUE=1` changes multiplication argument
passing without changing field arithmetic. The corresponding Modal variables
have an `ECC_` prefix and are preserved through image creation and rebuilds.
Benchmark identity and kernel startup report the settings.

## Final integrated measurement

The [final audit](benchmarks/Frobenius-network/final-audit.json) ran source
`6b3996e` on one RTX PRO 6000 Blackwell Server Edition, CUDA 12.8.1,
driver 580.95.05, with the configuration above:

| Mode | Repetitions | Median billion scalar iterations/s | Range |
|---|---:|---:|---:|
| Benchmark | 3 | **5.832583** | 5.826473–5.834868 |
| DP cutoff 34, restarts and corpus writing | 3 | **5.737182** | 5.729669–5.738741 |

Each repetition completed **151,397,597,184** complete scalar walk iterations:
4,620,288 walks × 1,024 steps × 32 launches. Each collection run wrote
**3,900 records and dropped zero**, with a matching corpus-file record count.
CPU trail replay was disabled during timing after the separate replay test
passed. Synchronization, restarts and host report processing are included;
initial setup is excluded. The source digest of the published implementation
matches the audited source; later changes add documentation and evidence.

This is approximately 6.80 times the originally supplied 0.857163 B/s baseline.
The 60 B/s goal is not established by these measurements. Other GPU
architectures have not been measured. GPU clock/state metadata is a snapshot
before validation, not a trace of the timed runs.

## Controlled comparison

The [development experiment](benchmarks/Frobenius-network/development-comparison.json)
screened three network configurations, then used three fresh paired rounds
to confirm the selected six-block candidate on the same GPU allocation:

| Configuration | Confirmation median B iterations/s | Range |
|---|---:|---:|
| Cached denominator, by-value arguments, repeated squaring | 4.115575 | 4.115364–4.116106 |
| Same configuration, both Frobenius networks | **5.811421** | 5.808910–5.812715 |

This isolates a **41.21%** improvement from the networks. The initial screen
measured 4.332610 B/s for the large-inversion-power-only network and
5.741036 B/s for the full network with four resident blocks per SM. Those are
single screen samples, separate from the confirmation medians.

An earlier [argument-passing comparison](benchmarks/Frobenius-network/value-argument-comparison.json)
measured a smaller improvement from 4.101785 to 4.133229 B/s with denominator
caching held enabled. Both arguments and network changes are therefore
identified explicitly in the final configuration.

## Construction and verification

Bit i represents `gamma_(i+1)`. Frobenius power k maps it to the coefficient
indexed by `(i+1)*2^k mod 263`, folded using `gamma_j = gamma_(263-j)`.
The generator routes this permutation through a Beneš network padded to
256 bits. It verifies all 256 basis vectors for every one of the 131 powers.
Linearity extends those checks to every input vector.

The emitted subsets each use 64 word-swap operations and 56 distinct mask
rows. The walk table uses read-only global storage because jump indices vary
among threads. The large inversion powers use constant storage. Temporary
padding stays inside the functions; persistent field elements still have five
words, with the upper 29 bits clear.

Validation completed:

- `make check-cli` verifies the generated header exactly and runs the CLI,
  report and autotune checks.
- `make test-packed test-packed-network` compares multiplication, squaring,
  inversion and selected Frobenius powers with the independent field reference.
- The final audit runs `make test-packed-cuda` with the candidate flags and
  launch bounds: **3,120 GPU vectors** covering every field basis vector for
  the selected powers, including fallback powers, plus dense inputs.
- GPU integration checks real report replay, restarts, exact resume, scalar
  iteration counting, incompatible-checkpoint preservation and overdue guards.
- All development variants match the control checkpoint byte-for-byte at a
  common worker count and step count.

Changing occupancy can change automatic worker count. Preserve the original
worker count and batch when resuming a checkpoint. Changing only these
arithmetic options requires no checkpoint conversion.
