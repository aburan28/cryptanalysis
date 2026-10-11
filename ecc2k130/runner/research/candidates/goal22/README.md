# Measured ECC2K-130 GPU candidate

Candidate: `warps4_poly_compact640`. Median: 22.100934 billion complete scalar updates/sec, 5 timing samples.

Target hardware: one RTX PRO 6000 Blackwell Server Edition, sm_120.
Compiler identity, raw output, replay/resume checks and timing counts are retained in `measurement.json`. The five-sample throughput and walk-validation acceptance checks passed.

DP34 collection rate: 21.548499 B/s (zero means not measured in this receipt).

Build using the compiler recorded in the receipt:

```sh
make gpu-goal22
```

This is an isolated research build. It does not update running workers. Batch geometry must match the campaign before any deployment.

Validation limits are recorded in `acceptance.json`: Compute Sanitizer was unavailable, the inherited test-clmad suite is not fully green, and this is not a fleet/S3/RDS end-to-end measurement.

The main changes share each inverse across four warps, expose disjoint buffers
to the compiler, compact live metadata, and reduce the per-update polynomial
square in packed even/odd coefficient streams. The walk and field result stay
identical, as checked by the reference and complete DP corpora.

Same-run baseline: 19.852741 B/s. Measured gain: **11.32%**.

The five accepted rates and all raw counts are in `measurement.json`; the
higher short screening rates are not used for acceptance. Each accepted sample
performs 504,658,657,280 complete point updates (about 23 seconds per sample).

After building, reproduce the benchmark on the target GPU with:

```sh
./ecc2k130 --curve 131 --packed --bench --steps 1024 --launches 256 --verify 0
```

Arithmetic derivation and long-division checks are in
`research/gen_square_reduce.py`; the exact generated map is
`include/square_reduce.h`. Compiler: CUDA 13.3.73; batch 16; 640 threads/block.
