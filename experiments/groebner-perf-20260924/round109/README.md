# Seeded completion discovery

The round108 fixed-degree matrix can derive useful rows without producing a
complete Gröbner basis. Its fallback currently restarts F4 from the original
equations. This experiment supplies the derived rows first, followed by every
original equation, to that unchanged F4 producer. It substitutes the derivations
of the seed rows into the continuation's proof and independently verifies the
result against the original packed coefficients.

This is a frozen, untimed Python reference experiment, not a native performance
implementation or a novel F6 claim. The retained original equations preserve the
input ideal; the final checker must establish both ideal equality and Gröbner
completion. A composed graph alone establishes neither.

The first discovery retains all 13 round108 fixtures and optimized/UBSan modes.
It uses the original 80-million total producer-work and 200-million checker-work
caps, the 20-million matrix cap, and the existing row/term limits. Only a matrix
call that actually returns a candidate can supply seeds. Matrix exhaustion keeps
the original remaining-budget fallback. The Python bridge adds declared charges
for seed materialization, packing, proof substitution/pruning and final transport.
Retained seed nodes are reserved from the continuation's two-million-node cap.
All failed attempts and checks consume the shared remaining budgets.

`compose.py` validates graph topology and input mappings, substitutes the seed
proofs, and prunes unreachable nodes under explicit work and node caps. Random
nested-multiplication controls check polynomial semantics; exhaustive small caps
and malformed unused nodes check failure behavior.

Run from a committed checkout:

```
python experiments/groebner-perf-20260924/round109/discover.py \
  --reference /absolute/path/to/round108 \
  --output /absolute/path/to/new-evidence-directory
```

The reference directory must contain the previously built, source-bound round108
libraries and polynomial resources. All recorded hashes are checked before any
worker loads them. The discovery reuses those local binaries and does not claim a
fresh portable build. Each case gets a fresh worker, a 60-second timeout and a
record preserving process failures. The parent takes the shared local heavy lock.
No Sage is used. CPU timing and IC speedup remain null. The small planted PDP
fixtures are correctness controls, not natural-yield or complete DLP measurements.

For a fresh local/CI build plus independent audit and artifact controls, run
`python experiments/groebner-perf-20260924/round109/run_validation.py --output OUT`.
The independent audit streams polynomial values as Python integers, checks every
original-input derivation and reproduces proof composition. Exact Boolean
zero/staircase certification and independent curve replay cover these small
fixtures. The raw continuation proof is retained for reproducible substitution.
