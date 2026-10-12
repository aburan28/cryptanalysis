# Q1504: exact N131 W6 base prices the direct scan at 2^64.137 calls in the expected-rank scenario

The exact enumerated degree-131 weight-at-most-six factor base has
**B=6,559,634,788** subgroup-usable points and **K=25,036,774** signed
Frobenius columns. Applying Q1502's paired-sign second-pair kernel to this
base requires, for one fixed first pair and four signed complements,
**26,238,539,152 = 2^34.611 group-add attempts** and
**91,834,887,032 = 2^36.418 batch field multiplication calls** before
counting inversion internals. The arithmetic also includes 26,238,539,152
batch squarings and 25,623,576 batch inversions at 512 x-coordinate pairs
per batch.

Q1414's exact-base uniform-query rank-supply bound gives the following
necessary query counts. The rightmost columns price the explicit scenario
in which each query performs **one complete Q1502 four-sign scan**. They
exclude all other stages and do not price early stopping or a guided query
law.

| Q1414 rank objective | Necessary uniform queries | One full scan per query, batch multiplication calls | Gap above 2^61 in that unit |
| --- | ---: | ---: | ---: |
| 50% rank success | 110,435,936 | **2^63.137** | **2.137 bits** |
| 95% rank success | 209,828,278 | **2^64.063** | **3.063 bits** |
| Expected rank at least K | 220,871,871 | **2^64.137** | **3.137 bits** |

This calculation uses the **exact W6 base**, rather than Q1462's sampled
conditional W7 estimate. The base is on
`EC1N131Ckb1h6816f880945e`, with canonical cyclic-Frobenius x-key
SHA-256 `e5f66c3944069924b9af7b8c22887e216702c8ac11a3a2ad072437e7d81ecb3`.
The candidate and run IDs remain null because a complete IC pipeline has
not been measured. The stage code is `PDP4hybrid`; `isogeny: "none"`.

The Q1502 signed-pair arithmetic saved 30% of its batch multiplication
calls relative to Q1501, or 0.515 bits, before this repricing. On the
exact W6 uniform-query scenario, a complete scan still costs 3.137 bits
more per query than Q1414's zero-other-cost ceiling for expected rank K.
Natural first-pair and relation yield, rank novelty under the proposed
collector, matrix construction and solution, target descent, and scalar
replay remain uncharged. The fully charged N131 solve exponent is therefore
null. This record rules out treating this **full-scan-per-query scenario**
as a sub-2^61 route; it does not rule out early-stopping scans, multiple
rows per query, nonuniform guided queries, or a sublinear second-pair
solver.

The next algorithmic gate is a second-pair search that avoids a complete
linear scan. A useful N83 experiment must pair its search cost with
independently verified ordinary relation yield and novel rank. Q1503's
fixed-pair SAT caps locate the remaining work in the algebraic middle link,
while the N53 full-rank and fresh-target receipts provide a complete
control for the revised handoff.

The [protocol](protocol.json), [freeze](freeze.json),
[analysis](analysis.json), [calculator](analyze.py), and
[read-only validator](validate.py) bind
Q1413's exact base receipt, Q1414's query bound, and Q1502's measured
kernel operation formula. Recompute the result with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261012_n131_w6_direct_scan_budget/validate.py
```
