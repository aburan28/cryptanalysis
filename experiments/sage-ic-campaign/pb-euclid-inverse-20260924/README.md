# Polynomial-basis Euclid inversion experiment

This archive measures a change to `Pb.inv` in both `ecc2k130/codegen/field.py`
and `ecc2k130/runner/codegen/field.py`. The incumbent computes
`a^(2^m-2)` using field multiplication; the candidate applies polynomial
extended Euclid and reduces the result modulo the field polynomial. It keeps
the incumbent's `inv(0) == 0` behavior and reduces noncanonical inputs first.

`baseline/` and `source/` contain exact field-source snapshots. Both frozen
intents identify those snapshots, the unchanged curve sources, and the
benchmark and runner by SHA-256. `run-primary-001/` and `run-confirm-001/`
hold fresh-process receipts and logs for local and runner variants at degrees
11, 15, and 53. Each cell has twelve balanced rounds, exact output checks,
separate first-call timings, exclusive operation/verification/cleanup times,
and peak RSS. Inputs differ between the two runs. Fixture generation is
excluded from the measured operations.

`test_inverse.py` checks all nonzero elements in several small fields, random
wide-field inputs, zero and noncanonical values, and curve addition, doubling,
and scalar multiplication. `test-runner-full.log` records 29 passing tests and
one unrelated missing fixture, `docs/ic/params/ecc2k130-fixed.json`.

Recheck the frozen evidence with:

```sh
python3 experiments/sage-ic-campaign/pb-euclid-inverse-20260924/verify_archive.py
```

The results are operation and curve-call measurements. They are not an
end-to-end index-calculus or recovered-DLP speedup. Complete IC comparisons
need a frozen workload, all charged phases, and a correctness certificate.
