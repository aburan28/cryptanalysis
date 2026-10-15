# Six-unit radix 233−τ with 16 positions

The radix π = 233−τ, with τ²−3τ+3 = 0, has norm 53,593. A nearest-norm digit for each quotient residue and a six-unit orbit table give a 16-position scalar recoding on the secp256k1 GLV coefficient lattice. The selected digit table has 8,933 orbit seeds, including zero. Its maximum norm is 17,787. The terminal norm is bounded by 16 after 16 steps, with 10 terminal orbit seeds. A direct 64-byte-per-point payload for all digit windows and terminal seeds is 9,148,032 bytes; table metadata and alignment add to this.

The six-candidate selector searches the two centered residue lifts and three nearby `b` coordinates per lift, using `(norm, |b|, |a|, a, b)` to break ties. For each of the 26,797 sign-canonical residues, `screen.py --full-global` compares it against all `b` with `|b| ≤ 155` and three nearest congruent `a` values. The inequality `N(a,b) ≥ 3b²/4` bounds every possible digit better than the observed maximum. The screen checks sign and six-unit covariance for all 53,593 residues. Its frozen 128-scalar integer recoding replay reaches terminal norm at most 7. The independent affine group replay checks 388 scalars, including 260 fresh and boundary inputs, against ordinary scalar multiplication and records the point digest.

| Evidence | Result |
| --- | --- |
| Full digit and radius screen | [`screen.json`](screen.json) |
| Independent affine point replay | [`group-replay.json`](group-replay.json) |
| Lean source and axiom audit | [`NearestOrbit53593.lean`](NearestOrbit53593.lean), [`lean-check.log`](lean-check.log) |

Run from this repository checkout:

```sh
python3 experiments/prime-j0-nearest-orbit-53593-20261014/screen.py --full-global > experiments/prime-j0-nearest-orbit-53593-20261014/screen.json
python3 experiments/prime-j0-nearest-orbit-53593-20261014/group_replay.py > experiments/prime-j0-nearest-orbit-53593-20261014/group-replay.json
LEAN_PATH=/private/tmp/lean-8011-fresh:/private/tmp/lean-12211-direct:/private/tmp/adaptive-unit-lean lean experiments/prime-j0-nearest-orbit-53593-20261014/NearestOrbit53593.lean
```

The Lean module proves the radix norm, norm scaling, quotient residue, exact digit-step identity, and unit-action residue identity. Its `#print axioms` output has only standard Lean foundations. The complete minimum-digit selection, terminal bound, and 16-step group reconstruction are verified by the pinned computational screens and affine replay; their full Lean formalization is open. The proof bridge for the point action is the established GLV relation `τG = λτG` from the parent implementation.

The next experiment is a native implementation with a frozen source/input/table manifest, paired against the 18-position radix on the same scalar set and Tier 1 RunPod envelope. Include point precomputation, memory and setup accounting, conversion, and alternating A/A gates. No latency result is attached to this format yet.
