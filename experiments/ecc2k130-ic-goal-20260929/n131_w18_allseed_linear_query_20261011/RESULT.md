# Target-linear product formation in the N131 W18 all-seed inverse

The complete W18 pair-output membership scan now forms **all 524,286 seed-and-branch product candidates with 19 field multiplications** after one supplied reciprocal coordinate arrives. It uses the linearity of halftrace and multiplication by a fixed field element to replace one field multiplication per candidate with XORs of target-scaled basis images. All four frozen queries gave exact semantic matches to the prior all-seed oracle, including both recovered source pairs, the published-point zero-hit control, and the trace-one fast exit. Checked Sage independently replayed 1,560 branch identities on 260 frozen seeds across the three trace-zero queries. The [terminal audit](terminal_audit.json) binds the source, binaries, paired runs, and Sage evidence.

For seed `s=Σ_i s_i t^(i+1)`, supplied nonzero reciprocal coordinate `c`, and odd-degree halftrace `H`, the prior exact inverse forms

`p_e = c⁻¹[H(c²) + H(s²) + e]`, for `e∈{0,1}`.

Because `H` and multiplication by `c⁻¹` are `GF(2)`-linear, prepare `u_i=c⁻¹H(t^(2i+2))` for the 18 W18 basis elements and `v=c⁻¹H(c²)`. Then `p_0=v+Σ_i s_i u_i` and `p_1=p_0+c⁻¹`. The [generated implementation](native.cpp) builds the scaled-seed XOR table inside the charged query interval and retains every linear-image, source-mask, pair-equation, rotation, and column check from the [prior complete inverse](../n131_w18_allseed_pair_inverse_20261011/RESULT.md). The trace-one branch skips the table.

The exact curve is `EC1N131Ckb1heb5f1998f20b` over `GF(2)[t]/(t^131+t^13+t²+t+1)`. Its W18 six-rotation source has **B=1,575,684** usable points and **K=131,068** folded columns. The [frozen protocol](protocol.json) fixes all source and binary hashes, four coordinates, alternating arm order, one worker, a 120-second native query cap, and 4-GiB RSS. Reusable all-seed map construction remains outside the supplied-coordinate query interval in both arms; target-scaled basis and XOR-table construction are inside it.

| Supplied coordinate | Candidate-product field multiplications, reference → linear | Reference query, local | Linear query, local | Linear peak RSS | Exact hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| W18 seed 13,686, rotation 26 | 524,286 → **19** | 0.467856 s | 0.101080 s | 159,940,608 B | 1 |
| W15-subspace seed 12,004 | 524,286 → **19** | 0.353095 s | 0.225763 s | 159,940,608 B | 1 |
| Published-point raw lift 0 | 524,286 → **19** | 0.418824 s | 0.181626 s | 159,940,608 B | 0 |
| Trace-one `c=1` | 0 → 0 | 0.000003 s | 0.000003 s | 153,632,768 B | 0 |

The **27,594-fold reduction in candidate-product field multiplications** is an exact operation-count result for this stage. The query still performs all seed-map membership tests and the prior per-seed algebraic consistency checks. Local wall times vary substantially even for the unchanged reference executable on this unisolated host, so the timing rows are diagnostics rather than a controlled CPU speedup claim. The XOR table adds about 6.3 MB at peak in these runs.

The [paired receipts](case_000_comparison.json) through the four indexed cases record exact output equivalence and both native intervals. The [Sage replay](sage_validation.json), run after the checked [runtime receipt](sage_runtime_info.json), computed direct and basis-XOR halftraces and products for every selected seed and checked both positive products against the emitted hits. The earlier all-seed inverse already has a complete opposite-pivot native replay and sampled Sage group-sign checks; exact semantic agreement transfers those controls to this query transform.

This is a faster supplied-coordinate membership component with `candidate_id: null`. The next decisive construction must propose pair coordinates from the public N131 target while keeping enough seed and block-product support, charge every failed proposal and membership call, and return an independently verified unpinned relation within one worker, 600 seconds, and 4 GiB. Relation yield, useful rank, factor logs, and the paired single-target rho result follow that gate.

Reproduce the archive check with `python3.12 /Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929/n131_w18_allseed_linear_query_20261011/verify.py`.
