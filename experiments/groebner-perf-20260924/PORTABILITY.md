# Building and reviewing the Gröbner performance work

This package includes the Boolean certificate and solver support required by
rounds 1–3, their frozen controls and recorded evidence, and the standalone
Metal RREF experiments. The round-three results are the current verifier/GPU
follow-up. Historical Rust preprocessing snapshots and receipts are included
as research provenance; this PR does not modify the separately hosted Rust
implementation or the migrated `suite/` F4/GPU work.

The portable builder requires Python 3.10+ and a C++17 compiler. It builds the
current verifier, its undefined-behavior-sanitized counterpart, and the dual
solver's CLI/library without Sage, and does not overwrite measured receipts:

```sh
python3 experiments/groebner-perf-20260924/build_portable.py
python3 experiments/groebner-perf-20260924/verify_archive.py
python3 experiments/groebner-perf-20260924/ci_check.py
```

On Linux use `CXX=g++` if Clang's shared UBSan runtime is unavailable. Python
unit tests additionally use SymPy. The `Boolean Groebner certificates` CI runs
normal/UBSan differential checks on Linux and macOS, checks the shipped source
and evidence hashes, and exercises original-equation/curve replay, concurrent
verification, malformed inputs, explicit Python/native selection and fallback.
A separate Linux job installs M4RI and tests Boolean field-pair completion and
the native/M4RI runners. The original Sage/Singular validation receipts remain
in `round3/results/`; `round3/validate.py` reruns that external oracle where
Sage is installed. CI does not present Python comparisons as new Singular runs.

For the Apple GPU prototype, install M4RI and run the portable builder with
`--metal`. It uses `M4RI_PREFIX` or pkg-config. Execute the generated
`round3/build/tiled-rref` binary with `round3/tiled_rref.metal` and
`round3/matrices.json` as its two arguments; redirect output to a new result
path to preserve the frozen receipts. GPU execution needs local Metal access.
Hosted CI validates CPU correctness; the 2,264 local GPU comparisons are
recorded evidence, not a claim that hosted CI ran Metal hardware.

Historical measurement JSON and original recipes retain their absolute local
paths and binary hashes. Compiled binaries are deliberately not distributed.
`verify_archive.py` resolves recorded repository paths relative to the current
checkout, verifies the shipped bytes, and reports historical local binaries
and system libraries as external. It never asserts that a rebuild on another
OS is byte-identical. `distribution-manifest.json` separately covers the
shipped package. `round3/summarize.py` is the original machine-local audit;
use the portable audit in other checkouts.

The shared checkout contains other ongoing experiments; they are not part of
this PR. Runtime cache helpers included here are dependencies of the existing
Boolean F5B Python reference. Neither new cloud infrastructure nor Redis
services are required or enabled by the verifier/CI.

See [NEXT_STEPS.md](NEXT_STEPS.md) for prioritized experiments and the primary
single-target online IC acceptance gate. The reported verifier and matrix
speedups remain component diagnostics. They are not IC-versus-rho results.
