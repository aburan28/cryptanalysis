# Q20261010111900: sparse-quadratic S3 scan cuts field multiplications

Precomputing the quadratic Boolean-mask terms in a fixed-output S3
equation reduced charged field multiplications by **49.36% at N53** and
**52.38% at N83** on matched complete scans. Both batch windows
reproduced the baseline's exact decisions: one right pair for each
known-solution control and zero pairs for the selected first ordinary
outer-root output at each degree. Checked Sage replay independently
verified that each distinct control pair extends to a four-point
relation on the exact base and public target.

The [protocol](PROTOCOL.md) gives the polynomial identity and work
boundary. The [freeze](freeze.json) pins source, binary, bridge, input,
curve, actual base B, folded columns K, workloads, caps, and all eight
[matched baseline scans](../compact-s3-m4-fixed-output-root-scan-20261010/runs).
The [build receipt](build_receipt.json) includes three passing Rust
tests; the new exhaustive degree-five test compares all nonzero first
coordinates and outputs against the direct S3 root implementation.

| Degree and input | Window | Root calls | Field mul: baseline → new | Reduction | New scan seconds | Right pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 control | 4,096 | 24,857 | 260,577 → 131,946 | 49.36% | 0.0040 | 1 |
| N53 control | 16,384 | 24,857 | 260,589 → 131,958 | 49.36% | 0.0023 | 1 |
| N53 ordinary | 4,096 | 24,857 | 260,577 → 131,946 | 49.36% | 0.0022 | 0 |
| N53 ordinary | 16,384 | 24,857 | 260,589 → 131,958 | 49.36% | 0.0025 | 0 |
| N83 control | 4,096 | 30,967,383 | 325,139,937 → 154,845,185 | 52.38% | 59.10 | 1 |
| N83 control | 16,384 | 30,967,383 | 325,156,944 → 154,862,192 | 52.37% | 57.82 | 1 |
| N83 ordinary | 4,096 | 30,967,383 | 325,139,937 → 154,845,185 | 52.38% | 39.37 | 0 |
| N83 ordinary | 16,384 | 30,967,383 | 325,156,944 → 154,862,192 | 52.37% | 40.68 | 0 |

All scans completed their full raw mask domains within the frozen
120-second native cap and 512-MiB RSS cap. The target-dependent
quadratic precompute and Montgomery batch inversion are included in
the new scan time and operation counts. Inversion counts matched the
baseline: 8/4 at N53 and 7,563/1,894 at N83 for the 4,096/16,384
windows. The eight [run receipts](runs), [native audit](verification.json),
and [checked Sage replay](sage_replay.json) retain per-cell detail.
Each pair found under two windows is one distinct control relation.
The ordinary zero-pair decision applies to one fixed output per degree.
Scan wall times are exploratory because the host has no CPU-isolation
receipt and had concurrent Rust builds.

## N131 distance to the challenge

The [analysis receipt](analysis.json) uses Q1414's exact W≤6 base and
uniform subgroup-query supply bound: at least 209,828,278 queries are
needed for 95% rank success under optimistic novel-row assumptions.
If this collector performs one complete raw W≤6 scan for each query,
those queries require at least `2^60.26` S3 root calls. The measured
N83 4,096-window kernel uses 5.0003 field multiplications per root,
versus 10.4994 in the matched baseline. Carrying these operation
ratios to N131 changes the conditional multiplication count from
**`2^63.65` to `2^62.58`**, a **1.07-bit reduction**. The new count
is still **1.58 bits above `2^61` in multiplication calls alone**.
Inversions, base construction, query generation, relation checks,
final matrix work, target descent, and replay add further work.

The batch-inversion loop gives a code-specific floor without carrying
the N83 root ratio to N131. A window of `L` nonzero denominators uses
exactly `3(L-1)` field multiplications to form and unwind its prefix
products, plus one inversion. At N131 W≤6, the 4,096-window schedule
has **1,601,407 windows** for `D=6,559,349,863` masks, hence
`3(D-1,601,407)=19,673,245,368` batch-inversion multiplications per
complete scan. Charging Q1414's 209,828,278-query minimum gives
**`2^61.84` multiplications from batching alone**, 0.84 bits above
`2^61`. This floor applies to the measured Montgomery batch-inversion
collector under the stated uniform-query and full-scan conditions;
it is not a lower bound for a different inversion algorithm or a
guided collector.

The separate uniform *fixed-field-output* screen retains its
`2^122.89` root-call requirement for this complete-scan collector
under that stronger output-law assumption. The two ordinary outputs
measured here do not establish that law. The complete cold and
one-target online N131 `2^x` remain null; natural relation yield and
novel rank on the exact N83 base are the next measurements needed to
decide whether a guided collector can avoid full scans.
