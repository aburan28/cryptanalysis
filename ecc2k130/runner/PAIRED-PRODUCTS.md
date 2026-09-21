# Paired polynomial products

The reverse batch pass multiplies one partial inverse by two different
values. `PACKED_PAIR_PRODUCTS=1` computes those products in one routine,
allowing shared operand preparation. Both outputs remain separate field
elements. No iteration, report, seed or checkpoint semantics change.

The measured configuration also enables the explicit inversion schedule.
It uses the same eight-multiplication Itoh–Tsujii chain as before. Both options
remain disabled by default; paired products require polynomial chains.

## Reproduce the audited configuration

```bash
ECC_GPU=RTX-PRO-6000 \
ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 ECC_PACKED_POLY_CHAIN=1 \
ECC_PACKED_UNROLL_INV=1 ECC_PACKED_PAIR_PRODUCTS=1 \
  modal run packed_audit.py --min-blocks 4 --output paired-product-audit.json
```

For benchmark-only measurements, replace the entry point with
`modal_app.py::bench --packed --min-blocks 4 --steps 1024 --launches 32 --repeats 3`.
Direct make builds use the same variable names without the `ECC_` prefix.
Changing a make variable requires rebuilding (`make -B gpu`). Modal preserves
the settings through image creation and rebuilds and reports them in identity.

## Final audit

The [final audit](benchmarks/paired-products/final-audit.json) used source
`250d683` on one RTX PRO 6000 Blackwell Server Edition, CUDA 12.8.1,
driver 580.95.05, batch 32, block size 128 and minBlocks=4:

| Mode | Repetitions | Median B scalar iterations/s | Range |
|---|---:|---:|---:|
| Benchmark | 3 | **6.211583** | 6.208415–6.212546 |
| DP cutoff 34, restarts and corpus writing | 3 | **6.126760** | 6.122291–6.127200 |

Every run completed **100,931,731,456 complete scalar walk iterations**. Each
collection repetition wrote **2,633 records**, dropped zero, and had a
matching corpus-file count. CPU trail replay was disabled after the separate
correctness gates passed. Synchronization, restarts and host report processing
are timed; setup is excluded. The published source digest matches the audited
source. GPU state metadata is a snapshot before validation, not a clock trace.

The GPU arithmetic gate verifies 3,120 Frobenius vectors, 1,261 reductions,
18,185 individual polynomial products, and **18,185 paired cases checking
both outputs** against independent multiplication. Full GPU report replay,
restarts, exact resume, scalar accounting, incompatible-checkpoint
preservation and overdue-guard checks pass. Host and CLI/report checks pass.

## Controlled comparison

The [development comparison](benchmarks/paired-products/development-comparison.json)
screened three configurations and then ran three fresh paired confirmation
rounds on the same GPU allocation:

| Configuration | Confirmation median B iterations/s | Range |
|---|---:|---:|
| Separate products, five blocks/SM | 6.123614 | 6.119233–6.127273 |
| Paired products, four blocks/SM | **6.215430** | 6.213518–6.215858 |

The selected configuration is about 1.50% faster. This comparison changes both
product grouping and occupancy; it does not isolate either factor alone.
The three- and five-block paired-product screens were slower than the winner.
All variants passed integration and matched control checkpoints at common
worker/step counts.

These measurements do not establish 60 B/s or performance on other GPUs.
Worker count and batch must still match when resuming checkpoints. The
narrow-integer and inlining experiments are not enabled by this configuration.
