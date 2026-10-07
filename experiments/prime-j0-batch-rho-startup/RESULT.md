# One-target batch-normalized paired rho startup

The fresh public `glv-j0-32` target `(4104446912, 4232867958)` was
frozen in commit `b8af5780` from independent affine Python arithmetic.
Its fixture scalar is `1730551` relative to base
`(481899190, 1998487369)` and the rho seed is
`5646505813695430397`. The solver received the public point and seed,
never the fixture scalar. Every invocation started an empty
distinguished-point table.

The six serial Release solves and six serial UBSan solves all recovered
and independently replayed the fixture scalar. The generic reference,
paired2, and paired2-batch arms each recorded 8,707 reference-equivalent
rho operations, 259 distinguished-point entries, eight multiplier-table
evaluations, nine restarts, and 1,207 reference-equivalent startup
operations. The fixed-seed rho trajectory therefore remained paired.

| Startup arm | Table output inversions | Restart output inversions | Total candidate output inversions | τ steps | Mixed adds | Rotations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| paired2 | 8 | 9 | 17 | 224 | 125 | 80 |
| paired2-batch | 1 | 9 | 10 | 224 | 125 | 80 |

The eight table outputs were all nonidentity. Batch normalization saved
seven inversions, with the same 1,104-byte prepared point object,
preparation work, 68 recodings, and 68 pair scores. It adds prefix and
reverse-product field multiplications: the batch routine executes three
extra Montgomery multiplications per table entry compared with eight
independent normalizations, or 24 extra multiplications for this table.
Those operations are inside the online interval. This is an arithmetic
tradeoff, not a field-operation or CPU speedup claim.

Local Release `online_ms` values were `0.913,0.980` for the generic
reference, `0.874,0.808` for paired2, and `0.826,0.859` for
paired2-batch in the frozen serial order. Preparation and warm-up varied
across the runs. The UBSan panel also overlapped a separate local test
process, so its timing is only a correctness diagnostic. The raw
`panel_local.json` and `panel_ubsan.json` retain
all fields and set `cpu_speedup_claim` and `isolation_receipt` to
`null`. No controlled CPU ratio is available.

`make_isolated_manifest.py` binds this exact target to the strict serial
runner. It can pair the batch arm against the generic rho reference for
the primary one-target question or against paired2 to isolate the table
normalization change. A qualifying physical Linux host receipt is still
required before promoting wall-time comparisons. This opt-in research
mode does not change automatic routing; academic novelty is unproved.
