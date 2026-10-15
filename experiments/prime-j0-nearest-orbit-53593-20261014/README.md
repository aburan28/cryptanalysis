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
| RunPod hot-table throughput panel | [`tier1-batch-analysis.json`](tier1-batch-analysis.json), [`analyze_batch_tier1.py`](analyze_batch_tier1.py) |
| Prime-norm radix shape sweep | [`radix-frontier.json`](radix-frontier.json), [`radix_frontier.py`](radix_frontier.py) |
| Norm-35,533 refinement | [`screen190.json`](screen190.json), [`group-replay190.json`](group-replay190.json), [`native190_overlay.py`](native190_overlay.py), [`NearestOrbit35533Bound.lean`](NearestOrbit35533Bound.lean) |

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

The Tier 1 batch panel ran 16 repetitions of 2,048 scalar multiplications per arm, with the 18-position rolling binary in both adjacent A/A controls. All 96 arms and 48 pairs were valid, artifact hashes remained stable, and every adjacent A/A ratio passed the preregistered [0.90,1.11] gate. The comparison's paired median 18-position/16-position throughput ratio was **1.0340**, with a repeat-level bootstrap 95% interval of **[1.0285,1.0366]** for this frozen scalar set and cloud allocation. Mean online cost was 12.57 versus 12.16 microseconds per scalar. Mean target-independent table preparation was 507 versus 1,727 ms, and retained bytes were 2,448,196 versus 9,363,076. These are hot-table throughput measurements for the 128-scalar law; the single-scalar latency panel above remains gated by its calibration failures.

The single-scalar RunPod panel paired the 16-position implementation against the 18-position rolling implementation on the same first five frozen scalars, with eight alternating repetitions and adjacent A/A controls. All 240 arms and 120 pairs were valid and artifact-stable. The descriptive median 18-position/16-position ratio was 1.024; seven of 40 comparisons failed the preregistered adjacent A/A interval [0.80,1.25]. The qualified latency ratio is therefore unknown. The 16-position table averaged 1,745 ms to prepare, versus 516 ms for the 18-position table; those target-independent times are outside the online interval. The full raw receipts, including every calibration failure, are retained with the panel.

A separate exact table-shape sweep checked the prime-norm `T−τ` radices for `180 ≤ T ≤ 233`, retaining only the 10 prime norms. For each row it enumerated every residue, checked sign and six-unit covariance, computed the 16-step terminal radius, and counted the digit and terminal orbit tables. Within this declared sweep, `T=190`, norm 35,533, has the smallest direct point payload: 6,300,480 bytes with 16 positions and terminal radius 78.

For `190−τ`, the wider global digit search agreed with the six-candidate selector on all 17,767 sign-canonical residues, unit covariance held on all 35,533 residues, and independent affine replay matched 388 scalars. The hash-pinned native overlay passed its 35,533-residue test and 128 frozen-point holdout, retaining 6,829,948 bytes including metadata and a dense terminal-code map. Its Lean modules prove the radix algebra, unit residue action, prime norm, 16 numeric contractions, and conditional selected-representative terminal norm below 78²; the axiom audits are in `lean190-check.log` and `lean190-bound-check.log`. The link from the concrete selector to the theorem's digit hypothesis is covered by the exhaustive screen and remains a Lean proof obligation. A matched native RunPod timing panel is the next gate.

The next experiment is a native implementation with a frozen source/input/table manifest, paired against the 18-position radix on the same scalar set and Tier 1 RunPod envelope. Include point precomputation, memory and setup accounting, conversion, and alternating A/A gates. No latency result is attached to this format yet.
