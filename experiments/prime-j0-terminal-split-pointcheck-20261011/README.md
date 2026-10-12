# Point-path replay for the split-terminal scalar scheme

The frozen split-terminal panel has a separate binary-curve correctness
receipt: both the original and selected radix paths evaluated to the same
secp256k1 point as direct multiplication on 256 previously unseen scalars.
The sample includes 178 selected paths with two terminal table points and
187 paths changed by the selector. The [point-check.json](point-check.json)
receipt binds the input, path certificate, earlier algebraic check, verifier
source, selected indices, and resulting point stream by SHA-256.

Run `python3 experiments/prime-j0-terminal-split-pointcheck-20261011/check_points.py`
from the repository root after the frozen panel artifacts are present. The
verifier uses its own secp256k1 group arithmetic. It adds the two terminal
parts when present, then evaluates the twelve radix-1024 digits by Horner's
rule, comparing each baseline and selected path with direct scalar
multiplication. Its source was added after the frozen screen, so the point
checks are confirmatory and did not participate in candidate selection.

The 4,096-case algebraic certificate and operation accounting are in
`../prime-j0-terminal-split-20261011/`. Native evaluator integration and
host-isolated CPU timing are the next measurement steps.
