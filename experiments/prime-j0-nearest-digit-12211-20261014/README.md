# Minimum-norm Eisenstein digits in one accumulator

For the fixed-base secp256k1 radix `π = 112 − τ`, this format selects a
minimum-norm Eisenstein digit in each residue class modulo `π`. It keeps the
18-position one-accumulator group path of the direct signed-digit format,
while contracting the quotient state faster. The exact 12,211-residue screen
found maximum digit norm **3,997**, versus `6105²` for centered integer
digits. After 18 positions the certified norm radius is **34** instead of
**89**, reducing the sign-canonical terminal table from 14,344 to **2,095**
points.

Each residue `r` is the class of `a + 112b` modulo 12,211. For
`0 ≤ r ≤ 6105`, form the two lifts `x ∈ {r, r−12211}`. For each lift, put
`b₀ = ⌊(2x+110)/221⌋` and test `b₀−1`, `b₀`, `b₀+1`, with `a=x−112b`.
Choose the candidate minimizing `(N(a,b), |b|, |a|, a, b)`, where
`N(a,b)=a²+3ab+3b²`. Negate the selected pair for residue `12211−r`.
The [exact screen](screen.py) verifies that these six candidates agree with
an independent wider search for every sign-canonical residue. The wider
search is exhaustive for a digit of norm at most 3,997: completing the
square gives `N(a,b) ≥ 3b²/4`, so any better digit has `|b| < 74`; for a
fixed `b`, only the nearest congruent `a` can improve the norm. The complete
lookup satisfies `N(d) ≤ 3997`. For `z=a+bτ` and selected `d=da+dbτ`,

```
k = (a−da+112(b−db))/12211
z' = (109k−(b−db)) + kτ,
```

so `z=d+πz'`. The [screen receipt](screen.json) retains the radius sequence,
all-residue checks, 128 frozen scalar replays, and exact memory counts.
The 18 digit windows store 6,106 affine points each and the terminal table
stores 2,095. Their minimum point payload is **7,168,192 bytes**. The
native implementation also retains the 24,424-byte canonical digit map and
structure metadata, for **7,193,344 retained bytes**. The direct integer
digit parent retained 7,953,280 bytes, so this saves **759,936 bytes** while
preserving one bucket and the same maximum of 18 nontrivial mixed additions.
Case 0 independently reproduced the parent public point with 18 nontrivial
mixed additions, 18 digit reads, one terminal read, and no projective join
or endomorphism rotation. Its local timing in `native-case0.log` is
exploratory.

The [native overlay](native_overlay.py) is hash-pinned to the generated source
of the [direct one-bucket parent](../prime-j0-direct-one-bucket-12211-20261014/README.md).
Its five release test families passed: 12,211 residue classes, 109,899
quotient cases, 2,095 terminal indices, 219,816 signed point images, 128
frozen scalar replays, and 518 independent additional scalar replays. The
first native attempt revealed a terminal-row range error; its failed log is
preserved. A second build exposed a static-array size mismatch; that log is
also preserved. The corrected native output is in `native-test.log`.

The Lean 4.34.1 proof chain establishes the full selected-scalar terminal
bound. The [bound module](SplitPrime12211NearestBound.lean) proves the norm
recurrence and the 18-step radius. The
[selector module](SplitPrime12211NearestSelector.lean) proves that selecting
the least-norm candidate preserves the residue. The
[finite certificate](SplitPrime12211NearestDigits.lean) checks all 6,106
sign-canonical residues and proves a digit norm at most 3,997. The
[step module](SplitPrime12211NearestStep.lean) proves that every selected
digit gives an integral quotient and the exact recoding identity. The
[complete module](SplitPrime12211NearestComplete.lean) applies these facts
to the certified scalar representative for all 18 positions. The
[consolidated axiom audit](ProofAudit.lean) and build logs retain exact
verification output; the reported axioms are `propext`,
`Classical.choice`, and `Quot.sound`. Earlier failed and resource-heavy
proof attempts remain as separate logs.

| Result | Lean declaration | Conditions |
| --- | --- | --- |
| Six-candidate norm cap | `all_residues_have_small_candidate` | Every canonical residue 0–6105. |
| Selected digit bound and congruence | `selected_digit_valid` | Canonical residue below 6106. |
| Integral recoding step | `bounded_step` | Every integer-coordinate state. |
| Eighteen-step terminal bound | `canonical_scheme_terminal_bound` | Every scalar in the certified representative lattice. |

The local case-0 interval and table build are diagnostics. A Tier 1
alternating same-scalar panel with A/A calibration is required to rank
latency against the direct, two-bucket, and three-bucket variants. RunPod
rejected the CPU Pod resume with `INSUFFICIENT_BALANCE` on 2026-10-14.

Minimum-norm digit sets for algebraic-base elliptic-curve recoding have
prior art; see [*Symmetric Digit Sets for Elliptic Curve Scalar Multiplication
Without Precomputation*](https://eprint.iacr.org/2013/705). This experiment
specifies and validates the concrete fixed-base `112−τ` point-table format
and its memory and group-operation profile.
