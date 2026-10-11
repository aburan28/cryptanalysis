# Local ONB trace parity

The tracked `ecc2k130/codegen/field.py:Onb.trace` now computes the parity of
normal-basis coordinates for canonical field elements. It preserves the prior
Frobenius-sum result for noncanonical raw vectors. The source in
`baseline/field.py` is the exact parent version.

The `intent.json` workload and gates were frozen before editing the source.
`run-a.json` and `run-b.json` contain alternating paired warm timings;
`cold-trace.json` contains seven alternating fresh-process measurements per
side. `verify.py` compares exact trace and curve outputs. Run the archive
check from the repository root:

```sh
python3 experiments/sage-ic-campaign/onb-trace-parity-20260924/verify_archive.py
```

Results concern the local Python ONB CPU path. They are arithmetic-stage
measurements, not complete verified IC or DLP cost comparisons.
