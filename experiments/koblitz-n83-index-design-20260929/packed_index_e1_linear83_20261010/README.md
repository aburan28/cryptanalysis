# E-1: unroll the N83 linear basis conversion

The N83 packed root index now has a fixed 11-table conversion path for the
83-bit polynomial and cycle representations. It replaces the generic loop
over byte tables with 11 explicit lookups and XORs, while retaining the
early-stop root canonicalizer, sparse 26-bit bitmap-rank directory, exact
full-key lookup, and first-witness rule. On the frozen one-target stage, the
six retained rows matched every correctness and arithmetic invariant. Median
process CPU use fell from 4.981 to 4.588 seconds (7.9%) on this exploratory
local panel. The unrolled path is selected only for the N83 mode and checks
that both maps have exactly 11 tables before running.

The curve is `EC1N83Ckb1h876c2921cb64`, workload `981ac530e67e`, and
proposal `Q2026101010`. The parent factor base has 30,977,592 usable points
and 186,612 folded columns. Each arm indexes the same 2,000,000 pair states
and 4,000,000 exact 16-byte root records, then scans the same public target.
The table occupies 93,360,128 bytes in both arms. The cap is 1,024 MiB RSS
and 180 seconds per arm. All six rows ended `state_cap_no_relation` at the
specified pair-state cap. Candidate and run IDs remain null for this bounded
stage.

| Method | Median child CPU | Median index build wall | Median target stage wall | Median query preparation wall | Median peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Generic byte-table loop | 4.981 s | 1.455 s | 4.725 s | 0.944 s | 568,803,328 B |
| Unrolled 83-bit conversion | 4.588 s | 1.392 s | 4.218 s | 0.595 s | 572,112,896 B |

The counterbalanced order was reference/candidate, candidate/reference,
reference/candidate. Child CPU times were 4.930–4.998 seconds for the
reference and 4.541–4.703 seconds for the candidate. The target-stage clock
starts after reusable factor-base and index construction. Its exclusive
components are query preparation, batched S3 roots, partner checking, and a
2.3–3.7 ms measurement/control residual per row. Partner checking includes
canonicalization and exact lookup; those two nested intervals must not be
added again. The complete phase rows, CPU use, RSS, operation counts, and
status are in [`summary.json`](summary.json). These local wall intervals are
exploratory under the repository's
[CPU isolation gate](../../../docs/ISOLATED_BENCHMARKS.md). The process CPU
figures describe this bounded stage; a physical-host run is the next step
for a controlled wall-time comparison.

Five Rust release tests passed, including 100,000 random N83 comparisons of
the unrolled and generic maps, exact duplicate first-witness lookup parity,
small-field canonicalization, and batched S3 roots. Independent wrapper
replays of both modes produced the same pair certificate
`2665304bcdb73b73a19a155744d2fcfde7cb8dfde41e7ef05c454b2a47add288`;
[`replay_check.json`](replay_check.json) records the raw-output digests.

Run `python3 run.py` here to verify the frozen crypto snapshot, build, and
execute the six-arm panel. Set `N83_E1_TARGET_DIR` to a volume with enough
free space for Cargo output. `make_manifest.py` validates the source and
input hashes and prepares a paired manifest for the isolated benchmark
service. Its physical-host run is the next measurement step.
