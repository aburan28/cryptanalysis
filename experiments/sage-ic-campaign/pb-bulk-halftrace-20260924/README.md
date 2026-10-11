# Explicit bulk half trace in polynomial-basis IC factor-base collection

This change adds `CurvePb.prepareHalfTrace()` to the local and tracked runner
curve sources. It computes and retains the half-trace images of the polynomial
basis vectors. Subsequent canonical half traces XOR the images selected by
the input bits; noncanonical inputs keep the previous calculation. The cache
is built only when a caller explicitly asks for it.

The tracked runner's `indexcalc.factorBase` accepts `bulkHalfTrace=True`, and
`runTrials` exposes it as `--basis pb --bulk-half-trace`. Preparation occurs
inside `factorBase`, so its time is charged to that complete stage. The
default path and ONB path are unchanged; requesting bulk preparation with an
ONB curve raises a clear error.

The frozen intent binds the field, baseline/candidate curve sources, baseline
and candidate `indexcalc.py`, benchmark, and runner by SHA-256. Primary and
fresh-process confirmation runs pair six complete factor-base calls in
balanced order at degrees 11, 13, 53, and 131. Each repetition uses a fresh
curve and charges preparation. The benchmark verifies exact points and
Frobenius orbits, records operation/verification/cleanup times and peak RSS,
and excludes shared `NormalView` construction from the factor-base boundary.

`test_bulk.py` checks exact half traces and point recovery in both curve
copies, cache idempotence, complete runner factor bases, and the ONB guard.
Recheck the frozen receipts with:

```sh
python3 experiments/sage-ic-campaign/pb-bulk-halftrace-20260924/verify_archive.py
```

These are complete factor-base stage costs. A verified DLP speedup still
requires charged setup, relation collection, linear algebra, target descent,
and log recovery on a frozen IC workload.
