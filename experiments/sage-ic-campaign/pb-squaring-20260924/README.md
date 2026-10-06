# Polynomial-basis squaring experiment

This archive measures a change to `Pb.sqr` in both local and tracked runner
field sources. The incumbent calls general field multiplication with equal
operands. The candidate expands each input byte into even polynomial
coefficients, then reduces the result modulo the field polynomial. Inputs
outside the field's canonical bit width retain the incumbent path.

`baseline/` and `source/` contain exact field-source snapshots. Frozen intents
bind these, the curve sources, the benchmark, and the runner by SHA-256. The
primary and confirmation runs each contain eight fresh-process cells: local
and runner copies at degrees 11, 15, 53, and 131. Each cell uses 12 balanced
rounds, new seeded inputs, exact output checks, first-call timings, exclusive
operation/verification/cleanup times, and peak RSS. Fixture construction is
outside the measured calls.

`test_square.py` covers exhaustive degrees 2–8, including noncanonical
inputs, random wide fields, and complete point scalar operations. The archive
verifier checks hashes, receipts, phase sums, medians, exactness, and gains:

```sh
python3 experiments/sage-ic-campaign/pb-squaring-20260924/verify_archive.py
```

These are arithmetic and complete scalar-call results, not a full
index-calculus speedup. A DLP claim requires charged setup, relation work,
linear algebra, target descent, and verified log recovery on one workload.
