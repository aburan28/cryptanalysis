# Native seventeen-window scalar prototype

The patch `native-frontier17.patch` adds a fixed-base secp256k1 mode with
six radix-128 windows, ten radix-256 windows, and a final radix-128
window. It loads the exact cycle-cover atlases from the frontier
experiment, forms exponent-zero and exponent-one projective buckets,
and returns `B0+tau(B1)` through the existing binary-inversion output
path. The scratch build retained **4,553,140 bytes**, including all
64,463 affine table slots, three atlases, and native table metadata.

The patch was generated against commit `f8cb6c314` and passed
`git apply --check --cached` against that commit's index. It is kept as
an immutable integration artifact while the shared native files remain
reserved by another coordinated task. Its source and patch hashes are
in `receipt.json`.
Run `python3 experiments/prime-j0-tau-frontier-native-prototype-20261010/verify_receipt.py`
from the repository root to reconstruct both patched source hashes in a
temporary Git index and check the committed logs and atlases.

## Correctness evidence

- The native table test independently formed and compared all 64,446
  nonidentity stored points across the 17 windows.
- The native scalar test matched all 4,096 scalars in the prior radix-384
  panel; its first 128 points also matched binary multiplication.
- `fixture129.out` contains 129 checked fixed-base cases, each with
  `verified=1` and the new mode label.
- `release-tests.log` records the complete release test suite: 100
  passed, zero failed.
- The separate affine verifier in the frontier experiment matched
  8,192 prior panel points against binary multiplication.

These are correctness and storage measurements. The existing RunPod Pod
fails the CPU isolation preflight, so a paired online timing result
requires a qualifying host. The evaluator uses scalar-dependent atlas
and table indices and remains an experimental public-scalar path until
a constant-time policy is designed and verified for secret inputs.

`make_inputs.py` and `verify_inputs.py` fix a new 4,096-scalar panel with
seed `20261010138`, disjoint modulo the subgroup order from the prior
panels. Draw it only after this patch, its atlases, and input generator
are committed. After the shared source reservation clears, apply the
patch to the current native branch, rebase it if that branch changed,
and rerun the correctness checks on the integrated source.
