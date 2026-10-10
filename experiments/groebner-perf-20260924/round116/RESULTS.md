# Certified initial batching: deterministic work reduction

The opt-in hybrid batch reduces complete-query F4 producer work on each of
five frozen 12-variable point-decomposition continuations. It first row-reduces
the initial generators in one proof-carrying matrix, then normalizes those
rows against the incrementally installed basis before the unchanged S-pair
queue. The normalization step is essential: a pure batch without it reached
79,999,698 units of the shared 80,000,000-unit producer cap on seed 1 and
returned `inconclusive`.

| Frozen query | Ordered work | Hybrid-batch work | Reduction | Local paired median complete-query batch/ordered |
| --- | ---: | ---: | ---: | ---: |
| `pdp-12-seed-1` | 41,399,086 | 36,960,141 | 10.72% | 0.840 |
| `pdp-12-seed-2` | 39,736,180 | 37,574,838 | 5.44% | 0.984 |
| `pdp-12-seed-3` | 45,420,758 | 38,804,755 | 14.57% | 1.545 |
| `pdp-12-seed-4` | 40,795,304 | 28,424,984 | 30.32% | 0.688 |
| `pdp-12-seed-5` | 43,000,957 | 39,161,473 | 8.93% | 1.028 |

The work count is the deterministic producer counter under the common
80-million cap. It includes the same matrix and continuation budget policy
for both arms and differs because the new generator order changes subsequent
F4 work. The wall-time column is a stage diagnostic from five alternating
AB/BA pairs per query on a contended M4 Pro host; its variation does not
qualify as a controlled CPU speedup. The full-query timer includes input
construction, native F4, proof checking, and curve replay. The paired run
retains all 60 executions, including warmups.

The independent checker accepted the new derivation DAG, reverse ideal
membership, Buchberger pairs, and Boolean field pairs for all five optimized
and five UBSan workers. Every result matched the frozen final reduced basis,
assignment, original equations, and curve replay. A separate 21-, 32-, and
64-variable control accepted exact certificates under a 300-unit checker
work budget and rejected modified proof output; those eight-equation linear
systems test scale of exact verification, not the difficult PDP distribution.

An observation-only profile of the ordered engine used five repetitions per
query. Initial serial generator reduction represented 48.5–61.6% of its
deterministic F4 work; packed matrix work represented 30.2–41.4%; symbolic
support lookup was under 1%. These fractions motivated the batch boundary.
The preceding continuation profile in `round113` splits F4 from certificate
composition and places F4 at 96.72–98.14% of native continuation time on
the same difficult cases.

Reproduce the exact local evidence with the commands in [README.md](README.md).
`archive.py` checks the raw worker records, frozen reference rows, source and
build receipts, then verifies every byte of its content-addressed archive.
The local archive contains 341 logical files deduplicated into 142 objects;
its SHA-256 is
`85cd52d914a8513fee55e36bc40c4a0ad1640ff4132ff74c0eb8e739b2aa08b2`.
The GitHub workflow reruns the complete 52-row frozen reference audit, both
builds, the paired profile, optimized/UBSan proof checks, and the larger
variable controls on macOS and Ubuntu. A host-isolated complete-query panel
with a full receipt remains the promotion gate for CPU wall-time claims.
