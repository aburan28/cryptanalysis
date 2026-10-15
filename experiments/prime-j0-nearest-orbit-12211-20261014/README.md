# Rolling unit-orbit table for 18-position scalar multiplication

A descending unit-class accumulator evaluates all selected digits from
their unrotated table seeds, then rotates the accumulated point at most
twice. On the frozen case-0 public point it replaces **10 affine `x`
constant multiplications with two aggregate rotations**, while retaining
the same 18 nontrivial mixed additions, no projective join, and the same
2,448,196-byte table. The six release correctness test families pass for
both the direct orbit evaluator and this rolling evaluator.

The minimum-norm digits for `π = 112−τ` on secp256k1 are closed under the
six unit actions `±1`, `±ω`, and `±ω²`, with `ω = τ−2` up to the choice of
generator. Quotienting the exact 12,211-digit set leaves **2,036** point
seeds: one zero seed and 2,035 six-element orbits. The norm-34 terminal
ball leaves **699** seeds. At 64 bytes per affine point, 18 digit windows
and one terminal row need **2,390,208 bytes of point payload**, a reduction
of **4,777,984 bytes** from the sign-only nearest-digit table. The recoder
still has 18 positions and the same norm and terminal certificates.

For each digit residue, store a seed index, power in `{0,1,2}`, and sign.
The exact screen defines `ω(a,b)=(a+3b,−a−2b)`, chooses the
lexicographically least pair in each six-unit orbit as its seed, and proves
by exhaustive integer checks that its code reproduces every selected
digit. The residue action is multiplication by `12100` modulo `12211`.
The same construction folds the terminal ball. The screen hashes the
ordered seeds and all 12,211 three-byte codes; a native implementation
must charge its actual metadata and point layout in addition to the
point-payload figure.

`group_replay.py` evaluates the proposed lookup with affine secp256k1
points. It builds each touched seed point as `aB+bτ(B)`, applies the
curve's cube-root endomorphism and sign, adds the 18 digit points and
the terminal point, then compares with independent binary scalar
multiplication. The [replay receipt](group-replay.json) includes frozen
and fresh deterministic scalars, the exact input seed, point-output
digest, and touched-table counts.

The [native overlay](native_overlay.py) generates an orbit-coded evaluator
from the hash-pinned nearest-digit Rust source. It retains the original
six-candidate recoder, constructs 2,036 digit seeds and 699 terminal seeds,
and maps each selected digit or terminal pair to a seed and unit code.
The release executable reports **2,448,196 retained bytes**, including
the seed points, digit pairs, Rust code records, table descriptors,
and terminal index arrays. That is **4,745,148 fewer bytes** than the
7,193,344-byte sign-only nearest-digit implementation. Its six test
families passed: all 12,211 residues and 109,899 quotient cases; all
219,816 signed digit images across 18 windows; all 2,095 canonical
terminal images; 128 frozen scalar replays; and 518 additional scalar
replays against independent binary multiplication. The first native
compilation failed on test expression types; that raw failure log is
preserved separately from both green runs.

The direct orbit evaluator's frozen case-0 replay reproduced the parent
public point with 18 nontrivial mixed additions, no projective join, 10
affine `x` constant multiplications, 18 digit reads, and one terminal
read. The [rolling overlay](rolling_overlay.py) recodes all 18 digits and
the terminal pair, then visits unit classes 2, 1, 0. Its one accumulator
computes `S₀ + ω(S₁ + ω(S₂))`, where each `Sⱼ` sums only unrotated seed
points with their selected signs. Skipped classes are handled by rotating
directly to the next occupied class. Its [native test log](rolling-native-test.log)
records all six passing families; the [case-0 log](rolling-native-case0.log)
records two aggregate rotations and the same public point. Both local
wall-time fields are ordinary-host diagnostics and do not rank latency.

The [Lean module](NearestOrbit12211.lean) checks `ω³=1`, norm
preservation across all six images, the residue multiplier, sign action,
the rolling three-class identity, and the two-rotation upper bound. It
imports the checked nearest-digit global-minimum module.
Its `#print axioms` output in [lean-check.log](lean-check.log) contains
only `propext`, `Classical.choice`, and `Quot.sound`. The exact 2,036/699
counts are checked by `screen.py`. The
[finite covariance module](NearestOrbitCovariance.lean) proves that
`nearestDigit ((12100*r) % 12211) = ω(nearestDigit r)` for every
`r < 12211`. It uses 96 generated, kernel-checked chunks of at most
128 residues; [the build log](covariance-lean-check.log) reports only
`propext` and `Quot.sound` for the final theorem. The first monolithic
proof was stopped after 12.2 minutes and 6.6 GB observed RSS; the
resource-cap [receipt](covariance-monolithic-cap.json), its
[source attempt](NearestOrbitCovarianceMonolithic.lean.attempt), and a
subsequent noncomputable-definition build error are preserved separately.
The concrete secp256k1 endomorphism
correspondence is independently exercised by the affine point replay.

| Result | Lean declaration | Scope |
| --- | --- | --- |
| Cubic unit action | `omega_cube` | Every integer coefficient pair. |
| Norm-preserving orbit | `orbit_preserves_norm` | Every member of the six-image orbit. |
| Residue rotation | `omega_residue` | Every integer coefficient pair modulo 12,211. |
| Sign action | `negate_residue` | Every integer coefficient pair. |
| Rolling accumulator identity | `rolling_three_classes` | Arbitrary sums in the three unit classes. |
| Aggregate rotation bound | `rotation_count_le_two` | Every class-occupancy pattern. |
| Runtime digit covariance | `runtime_digit_covariant` | Every residue `r < 12211`; exact selected pair. |

Reproduce the screen and proof from this checkout with the pinned Lean
4.34.1 toolchain and built parent modules:

```sh
python3 experiments/prime-j0-nearest-orbit-12211-20261014/screen.py
python3 experiments/prime-j0-nearest-orbit-12211-20261014/group_replay.py
LEAN_PATH=/private/tmp/lean-8011-fresh:/private/tmp/lean-12211-direct:/private/tmp/adaptive-unit-lean lean experiments/prime-j0-nearest-orbit-12211-20261014/NearestOrbit12211.lean
python3 experiments/prime-j0-nearest-orbit-12211-20261014/generate_covariance.py
LEAN_PATH=/private/tmp/lean-8011-fresh:/private/tmp/lean-12211-direct:/private/tmp/adaptive-unit-lean lean experiments/prime-j0-nearest-orbit-12211-20261014/NearestOrbitCovariance.lean
```

For the native checks, prepare the direct one-bucket source crate as
described in the [parent experiment](../prime-j0-nearest-digit-12211-20261014/README.md),
apply that experiment's `native_overlay.py`, then apply this experiment's
`native_overlay.py`. The second overlay checks the resulting Rust source
hash before editing. Build and test with:

```sh
python3 experiments/prime-j0-nearest-orbit-12211-20261014/native_overlay.py /absolute/path/to/source-crate
CARGO_TARGET_DIR=/private/tmp/nearest-orbit-target cargo test --manifest-path /absolute/path/to/source-crate/Cargo.toml --offline --locked --release --bin eisenstein_fixed split_prime_ -- --test-threads=1 --nocapture
python3 experiments/prime-j0-nearest-orbit-12211-20261014/rolling_overlay.py /absolute/path/to/source-crate
CARGO_TARGET_DIR=/private/tmp/nearest-orbit-target cargo test --manifest-path /absolute/path/to/source-crate/Cargo.toml --offline --locked --release --bin eisenstein_fixed split_prime_ -- --test-threads=1 --nocapture
```

The next gate is a Tier 1 or Tier 0 isolated, alternating same-scalar
panel with A/A noise controls to rank the direct and rolling orbit
evaluators against the sign-only nearest-digit and norm-4,831 paths.
The finite covariance theorem, exhaustive screen, and native point-image
tests provide separate checks of the selected-map symmetry.
