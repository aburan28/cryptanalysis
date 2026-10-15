# Unit-orbit table for 18-position minimum-norm scalar multiplication

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
digest, and touched-table counts. This is a correctness and memory
candidate; no native retained-memory measurement or isolated CPU timing
has been recorded for this orbit layout.

The [Lean module](NearestOrbit12211.lean) checks `ω³=1`, norm
preservation across all six images, the residue multiplier, and sign
action. It imports the checked nearest-digit global-minimum module.
Its `#print axioms` output in [lean-check.log](lean-check.log) contains
only `propext`, `Classical.choice`, and `Quot.sound`. The exact 2,036/699
counts and covariance of the selected finite digit map are independently
checked by `screen.py`; a kernel-checked finite-map covariance theorem
remains to be built. The concrete secp256k1 endomorphism correspondence
is independently exercised by the affine point replay.

| Result | Lean declaration | Scope |
| --- | --- | --- |
| Cubic unit action | `omega_cube` | Every integer coefficient pair. |
| Norm-preserving orbit | `orbit_preserves_norm` | Every member of the six-image orbit. |
| Residue rotation | `omega_residue` | Every integer coefficient pair modulo 12,211. |
| Sign action | `negate_residue` | Every integer coefficient pair. |

Reproduce the screen and proof from this checkout with the pinned Lean
4.34.1 toolchain and built parent modules:

```sh
python3 experiments/prime-j0-nearest-orbit-12211-20261014/screen.py
python3 experiments/prime-j0-nearest-orbit-12211-20261014/group_replay.py
LEAN_PATH=/private/tmp/lean-8011-fresh:/private/tmp/lean-12211-direct:/private/tmp/adaptive-unit-lean lean experiments/prime-j0-nearest-orbit-12211-20261014/NearestOrbit12211.lean
```

The next implementation gate is a native orbit table with all 12,211
digit codes, terminal-code coverage, independent scalar replay, and an
exact retained-byte receipt. Its one-accumulator path applies up to two
affine `x` multiplications per nontrivial digit unit code. An oriented
one- or two-accumulator schedule could instead defer some rotations;
that choice requires source-level operation counts and an isolated
same-scalar timing panel before a latency ranking.
