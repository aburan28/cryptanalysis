# Six-unit radix 233−τ with 16 positions

The radix π = 233−τ, with τ²−3τ+3 = 0, has norm 53,593. A nearest-norm digit for each quotient residue and a six-unit orbit table give a 16-position scalar recoding on the secp256k1 GLV coefficient lattice. The selected digit table has 8,933 orbit seeds, including zero. Its maximum norm is 17,787. The terminal norm is bounded by 16 after 16 steps, with 10 terminal orbit seeds. A direct 64-byte-per-point payload for all digit windows and terminal seeds is 9,148,032 bytes; table metadata and alignment add to this.

The six-candidate selector searches the two centered residue lifts and three nearby `b` coordinates per lift, using `(norm, |b|, |a|, a, b)` to break ties. For each of the 26,797 sign-canonical residues, `screen.py --full-global` compares it against all `b` with `|b| ≤ 155` and three nearest congruent `a` values. The inequality `N(a,b) ≥ 3b²/4` bounds every possible digit better than the observed maximum. The screen checks sign and six-unit covariance for all 53,593 residues. Its frozen 128-scalar integer recoding replay reaches terminal norm at most 7. The independent affine group replay checks 388 scalars, including 260 fresh and boundary inputs, against ordinary scalar multiplication and records the point digest.

| Evidence | Result |
| --- | --- |
| Full digit and radius screen | [`screen.json`](screen.json) |
| Independent affine point replay | [`group-replay.json`](group-replay.json) |
| Lean algebra and bound audits | [`NearestOrbit53593.lean`](NearestOrbit53593.lean), [`lean-check.log`](lean-check.log), [`NearestOrbit53593Bound.lean`](NearestOrbit53593Bound.lean), [`lean-bound-check.log`](lean-bound-check.log) |
| Reproducible native source overlay | [`native_overlay.py`](native_overlay.py) |
| Common 128-scalar batch timer | [`native_batch_overlay.py`](native_batch_overlay.py) |
| RunPod single-scalar Tier 1 panel | [`tier1-analysis.json`](tier1-analysis.json), [`analyze_tier1.py`](analyze_tier1.py), [`tier1-runpod-20261014`](tier1-runpod-20261014) |

Run from this repository checkout:

```sh
python3 experiments/prime-j0-nearest-orbit-53593-20261014/screen.py --full-global > experiments/prime-j0-nearest-orbit-53593-20261014/screen.json
python3 experiments/prime-j0-nearest-orbit-53593-20261014/group_replay.py > experiments/prime-j0-nearest-orbit-53593-20261014/group-replay.json
LEAN_PATH=/private/tmp/lean-8011-fresh:/private/tmp/lean-12211-direct:/private/tmp/adaptive-unit-lean lean experiments/prime-j0-nearest-orbit-53593-20261014/NearestOrbit53593.lean
LEAN_PATH=/private/tmp/lean-8011-fresh:/private/tmp/lean-12211-direct:/private/tmp/adaptive-unit-lean lean experiments/prime-j0-nearest-orbit-53593-20261014/NearestOrbit53593Bound.lean
```

The Lean algebra module proves the radix norm, norm scaling, quotient residue, exact digit-step identity, and unit-action residue identity. The bound module proves primality by trial division, the one-step norm contraction, all 16 numeric radius inequalities, and `selected_terminal_bound`: every selected lattice representative with 16 valid digit steps of norm at most 134² has terminal norm below 4². Both `#print axioms` audits contain only standard Lean foundations. The selector's exhaustive minimum-digit certificate and the binding of the concrete selector to the theorem's digit hypothesis remain computationally verified; a full Lean proof of that binding and of the point-level 16-step group reconstruction is open. The point action in the affine replay uses the established GLV relation `τG = λτG` from the parent implementation.

The native overlay pins the SHA-256 of the 18-position rolling Rust source before transforming it. The release test binary passed its full 53,593-residue digit test and independently checked all 128 frozen scalar points. It reports 9,363,076 retained bytes, including digit/code arrays and Rust table bookkeeping. This local correctness run does not supply a qualified latency comparison.

The separate batch timer applies the same hash-pinned CLI addition to both native variants. It parses the 128 frozen scalars and builds each table before timing, then runs all 128 multiplications for a declared repetition count and verifies every resulting point after the timer. The timing field covers the entire batch; dividing it by the operation count yields hot-table throughput, not single-scalar latency. The two modes answer different measurement questions and have separate RunPod panels.

The single-scalar RunPod panel paired the 16-position implementation against the 18-position rolling implementation on the same first five frozen scalars, with eight alternating repetitions and adjacent A/A controls. All 240 arms and 120 pairs were valid and artifact-stable. The descriptive median 18-position/16-position ratio was 1.024; seven of 40 comparisons failed the preregistered adjacent A/A interval [0.80,1.25]. The qualified latency ratio is therefore unknown. The 16-position table averaged 1,745 ms to prepare, versus 516 ms for the 18-position table; those target-independent times are outside the online interval. The full raw receipts, including every calibration failure, are retained with the panel.

The next experiment is a native implementation with a frozen source/input/table manifest, paired against the 18-position radix on the same scalar set and Tier 1 RunPod envelope. Include point precomputation, memory and setup accounting, conversion, and alternating A/A gates. No latency result is attached to this format yet.
