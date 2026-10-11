# N83 E-1 Frobenius-orbit prefilter experiment

This experiment measures a target-independent membership filter in front of
the exact packed root index from the cached-coordinate implementation. For
each of the 4,000,000 indexed polynomial roots, the candidate inserts all 83
Frobenius conjugates into a 256 MiB blocked Bloom filter. Each membership
query reads one 64-bit word. A negative answer skips basis conversion and
canonical lookup; a possible hit follows the original exact lookup and
first-witness path. The filter has no false negatives for indexed orbits.

The frozen public-point workload is `981ac530e67e` on curve
`EC1N83Ckb1h876c2921cb64`, with 2,000,000 sampled pair states, one target,
and a 1,024 MiB RSS cap. The candidate source SHA-256 is
`24ab23c595edf987d377598bbacd89510914407f5c72873a02f213dcc1b9eb1f`.
`protocol.json`, `stage_manifest.json`, and `workload.json` bind the exact
inputs, source, run order, and limits. `summary.json` and the six raw run files
retain the statuses, phase timings, operations, memory, and lookup samples.

| Mode | Median target process CPU | Median target wall | Median index process CPU | Median peak RSS |
| --- | ---: | ---: | ---: | ---: |
| Cached coordinates | 1.565 s | 1.748 s | 1.318 s | 587 MiB |
| Orbit prefilter | 1.847 s | 2.164 s | 30.565 s | 830 MiB |

All three adjacent pairs had higher target process CPU for the filter arm,
with candidate/reference ratios 1.171, 1.141, and 1.278. It rejected
7,413,494 of 8,000,000 partner roots before exact lookup and reduced exact
table probes from 471,510 to 34,749. The filter reduced median partner-check
wall time from 1.094 s to 0.884 s, while query preparation rose from 0.130 s
to 0.688 s. Its median target-independent filter construction took 32.570 s.
The raw run rows retain exclusive phase sums; the displayed medians are
computed independently for each column.

Both arms recorded `state_cap_no_relation`, identical lookup samples and
target-stage invariants, and zero invariant mismatches. The Rust tests cover
Frobenius-orbit membership, first-inserted witness lookup, every GF(32)
point-partner case, and every tested Frobenius shift. All eight tests passed.
The Mac panel is an exploratory timing diagnostic without a host-isolation
receipt. The one-word prefilter is therefore retained as a negative result;
the cached-coordinate implementation remains the E-1 promotion candidate.

Reproduce with `N83_E1_TARGET_DIR` set to a separate build directory and
`python3 run.py` from this directory. Build, source checks, and fixture
construction happen before the native target timer.
