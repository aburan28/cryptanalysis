# E-1: stop the bit-parallel root search at an empty mask

The early-stop variant omits every wider cyclic zero-run mask once a mask is
empty. It retains the exact canonical root key and smallest-shift tie rule.
On the frozen N83 one-target stage, all six retained rows matched the merged
bit-parallel reference on lookup samples, first witnesses, arithmetic counts,
35,837 full-key probes, and target status. The exploratory median partner
canonicalization interval changed from 3.126 to 2.810 seconds. Median
complete target-stage intervals were 22.264 and 22.116 seconds on the shared
Mac, whose load varied substantially. A physical-host isolation receipt is
required for a controlled CPU wall-time comparison.

For a binary word, a set bit in the width-`w` mask marks a cyclic run of `w`
zeros starting at that position. Every run of length greater than `w`
contains a run of length `w`. Therefore an empty width-`w` mask proves all
wider masks empty. The candidate stops doubling at that point and performs
the same binary lifting over the remaining nonempty widths. Full-word
comparison resolves longest-gap ties exactly as in the reference.

The curve is `EC1N83Ckb1h876c2921cb64`, workload `981ac530e67e`, and
proposal `Q2026101009`. The parent factor base has 30,977,592 usable points
and 186,612 folded columns. Each arm indexes the same 2,000,000 sampled
pair states and 4,000,000 exact 16-byte root records before scanning one
public target. The sparse 26-bit bitmap-rank directory, singleton tags,
full-key binary search, 1,024 MiB RSS cap, and 180-second per-arm timeout
are identical. Candidate and run IDs remain null for this bounded stage.

| Method | Median target stage | Median partner canonicalization | Median index build | Table bytes | Median peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full bit parallel | 22.264 s | 3.126 s | 7.213 s | 93,360,128 | 630,489,088 B |
| Empty-mask early stop | 22.116 s | 2.810 s | 5.818 s | 93,360,128 | 630,538,240 B |

The counterbalanced six-row order was reference/candidate,
candidate/reference, reference/candidate. The retained target-stage ranges
were 12.938–23.862 seconds for the reference and 5.069–22.933 seconds for
the candidate; these wide ranges make the local wall intervals exploratory.
Index building is target independent. The target-stage clock includes query
preparation, batched S3 roots, partner canonicalization, exact lookup, and
native relation checks. Each retained run recorded `state_cap_no_relation`
within the RSS cap. Raw phases, memory, operation counts, and row order are
in [`summary.json`](summary.json).

Four Rust release tests passed, including exhaustive small fields,
100,000 randomized N83 key/shift comparisons, exact duplicate first-witness
lookup, and batched S3 roots. Independent wrapper replays of both modes
produced pair certificate
`2665304bcdb73b73a19a155744d2fcfde7cb8dfde41e7ef05c454b2a47add288`;
[`replay_check.json`](replay_check.json) contains both raw-output digests.

The first local panel hit `ENOSPC` while writing candidate row 2; its raw
rows and error are retained in [`attempt1`](attempt1). The second panel
completed rows 1–3, then hit `ENOSPC` writing the row-4 stdout receipt on
the Mac volume. [`attempt2`](attempt2) records that interruption. The
checkout moved to SSD scratch, and rows 4–6 were replayed with the same
binary, source hash, protocol, workload, and arm order. The summary uses
only completed rows. No host-isolation receipt accompanies these runs.

Run `python3 run.py` here to verify the frozen crypto snapshot, build, and
execute the six-arm panel. Set `N83_E1_TARGET_DIR` to place Cargo output on
a volume with adequate free space. `make_manifest.py` validates all frozen
source and input hashes and prepares a paired manifest for the repository's
[isolated CPU benchmark service](../../../docs/ISOLATED_BENCHMARKS.md).
