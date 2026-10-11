# Port measured ONB arithmetic to the IC runner copy

The tracked IC runner under `ecc2k130/runner/codegen` had kept the original
ONB field and curve methods. This patch syncs its ONB field with the verified
`ecc2k130/codegen/field.py` and applies the same square routing to its
`Curve` class. The runner-only `NormalView` class remains present and unchanged.

The `baseline` directory records the exact runner sources before editing.
`intent.json` freezes the paired workload and acceptance gates. `run-a.json`
and `run-b.json` are alternating warm CPU timings. `cold-point.json` has
fresh-process timings for one valid and one invalid abscissa. The benchmark
uses the runner's Euclid inverse and parity trace with instrumentation removed
from both sides; real runner tests exercise its counted wrappers.

Run from repository root:

```sh
python3 experiments/sage-ic-campaign/runner-onb-sync-20260924/verify_archive.py
```

These are local CPU arithmetic diagnostics. The complete IC/DLP cost is not
measured by this archive.
