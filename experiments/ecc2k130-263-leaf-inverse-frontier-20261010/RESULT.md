# First-leaf x release recalls the cancellation witness on both curves

Freeing only leaf 0's 131-bit `x` word returned an independently verified
SAT and exact-target group model in 0.518/0.517 seconds on the ECC2K-130
source/oriented degree-263 descendant. Each model has the same six leaf
masks as the archived positive witness: leaves 0 and 1 are identical and
their projective pair state is the identity. The solver therefore recalled
the fixed exceptional witness; these models add no new decomposition or
relation row. Freeing leaf 0's `z`, or either coordinate of leaf 5, reached
the frozen CryptoMiniSat search bound on both curves. The eight-cell
[independent audit](runs/R1/audit.json) reconstructs each exact input and
transcript, checks every SAT clause and native XOR, and replays the signed
point sum against the archived target.

This is the precommitted [single-coordinate protocol](PROTOCOL.md) for
proposal `Q1420`, on curves `EC1N131Ckb1h136f03e58c98` and
`EC1N131Cbinh833014327b07`. Both W24 bases have `B=16,772,828` distinct
subgroup-usable points; the one-target workload ID is `eee7f6ee5f6b`.
Each cell keeps the parent XCNF, six selected masks, four projective states,
target selector, solver binary, and all other external coordinates fixed.
It releases one named 131-bit input word, leaving 2,115 fixed units instead
of the parent's 2,246. The [source](runs/R1/source_cells.json) and
[descendant](runs/R1/descendant_native_cells.json) receipts contain every
full-input SHA-256, unit delta, and formula size. Protocol/source commit
`0130f5e75` and input commit `1785b7f08` preceded measurement.

| Curve | Freed coordinate | Audited status | Solver wall s | Peak sampled RSS MiB | Final conflicts | Restart rows |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Source | leaf 0 `x` | `SAT_VERIFIED_GROUP` | 0.518 | 127.859 | 5 | 1 |
| Source | leaf 0 `z` | `BOUNDED_UNKNOWN` | 145.969 | 262.969 | 897,630 | 1,439 |
| Source | leaf 5 `x` | `BOUNDED_UNKNOWN` | 124.057 | 226.391 | 1,063,899 | 1,639 |
| Source | leaf 5 `z` | `BOUNDED_UNKNOWN` | 129.766 | 166.375 | 777,568 | 1,356 |
| Descendant native | leaf 0 `x` | `SAT_VERIFIED_GROUP` | 0.517 | 130.344 | 5 | 1 |
| Descendant native | leaf 0 `z` | `BOUNDED_UNKNOWN` | 124.036 | 168.031 | 787,809 | 1,330 |
| Descendant native | leaf 5 `x` | `BOUNDED_UNKNOWN` | 123.394 | 231.625 | 768,859 | 1,323 |
| Descendant native | leaf 5 `z` | `BOUNDED_UNKNOWN` | 121.898 | 211.078 | 789,086 | 1,330 |

Every bounded cell entered active search and ended with `s INDETERMINATE`,
exit code 15, with neither the 150-second external wall nor 4-GiB RSS guard
firing. The solver's internal limit was 120 seconds; the source leaf-0 `z`
wall interval extended to 145.969 seconds before it exited. The SAT cells
returned exit code 10 with five final conflicts each. The source assignment
passed 337,063 ordinary clauses and 227,932 native XORs; the descendant
passed 336,505 clauses and 232,515 XORs. Both exact group replays found two
matching sign assignments, including the archived all-zero sign vector.
The two models' leaf masks exactly match the parent's state-release controls,
including the duplicate first pair and identity intermediate. All eight
transcripts and the audit are committed; a second auditor run produced
byte-identical JSON.

The [environment record](runs/R1/environment.json) pins the Apple M4 Pro,
macOS 26.6, Python 3.13.1, CryptoMiniSat 5.14.7 binary SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`,
one solver thread, and measured interval. Host-wide CPU isolation was not
established, so wall times are exploratory solver-stage diagnostics. The
status split was observed under this fixed cap, but the exceptional
first-pair cancellation prevents interpreting x0 as a natural PDP yield or
an independent rank gain.

The next frozen gate should construct and independently verify a positive
six-leaf witness with distinct factor-base points, finite pair and tree
intermediates, and an exact target sum on each curve. Repeat the x-only/z-only
release at matched leaf positions, keeping the same solver and resource
policy. If a coordinate remains bounded after the cancellation shortcut is
removed, test a **selective** functional inverse or propagation lemma for
that leaf equation, comparing formula size and exact SAT controls before an
ordinary query. The prior full functional W24/m6 circuit enlarged the XCNF
20.448-fold; a local change is the better first test. Only a verified
ordinary relation advances to the frozen equal-B yield/rank screen.
`candidate_id` remains `null` while ordinary yield, novel rank, final matrix,
target descent, and one-target online cost are unset.

Reproduce the archive-only audit with:

```sh
python3 -B experiments/ecc2k130-263-leaf-inverse-frontier-20261010/audit.py \
  --scratch-dir /private/tmp \
  --out /private/tmp/leaf-split-audit-replay.json
cmp /private/tmp/leaf-split-audit-replay.json \
  experiments/ecc2k130-263-leaf-inverse-frontier-20261010/runs/R1/audit.json
```
