# N83 rectangle width-14 base: exact two-bit translation screen

The [8,532-column rectangle base](../n83-geometric-rectangle14-20261012/README.md)
is a strict maximum over every **distinct two-high-bit translation of
its fixed affine width-14 plane**. The best distinct translate, bits
**(50,69)**, has only **8,421 eligible rational `x` lifts**. Every
folded subgroup orbit column requires a distinct eligible lift, so
none of the distinct two-bit translations can match the baseline
8,532 columns. Two of the 2,485 translations, bits (37,68) and
(73,82), are basis directions and reproduce the same plane. This is
an exact local result for the fixed basis directions, not a search of
all width-14 affine subspaces.

The [protocol](protocol.json) pins the rectangle basis, prior key
receipt, normal-basis bridge, curve source hashes, and all
`binom(71,2)=2,485` bit pairs. The [screen](screen.json) retains every
eligible lift count, zero-`x` exception, and same-plane flag. The next
largest distinct lift bounds are 8,395 at bits (40,62) and 8,393 at
bits (16,38). The [best key file](best_keys.bin) retains the baseline
key bytes because no competing translation reached its column count.

Four translations contain `x=0`: the original rectangle edge offsets
(37,73), (37,82), (68,73), and (68,82). The curve has the rational
point `(0,1)` at that coordinate, and cofactor-four projection sends it
to the identity. The `1/x` trace test is undefined there. The corrected
screen records each zero coordinate separately and excludes it from
the **eligible nonzero lift** bound used for factor-base columns. The
first implementation stopped at the first such row; its
[source](screen_attempt1.py), [protocol](protocol_attempt1.json), and
[failure receipt](failure_attempt1.txt) are preserved.

The checked [Sage runtime identity](sage_runtime_info.json) was saved
before the screen. The [independent Sage replay](independent_sage_replay.json)
recomputes all 40,714,240 candidate-coordinate rationality tests with
per-element inverses, checks the four zero cases and two equivalent
planes, and matches every row. The [read-only verifier](verify.py)
audits those results and frozen source/input hashes:

```sh
python3 experiments/n83-geometric-rectangle14-two-bit-translates-20261012/verify.py
```

The conditional counting implication is checked in
[TranslateBound.lean](TranslateBound.lean) with the pinned
[Lean toolchain](lean-toolchain); the [axiom audit](lean-build.txt)
reports no axioms. The finite-field census and curve-orbit
cardinality bridge are independently replayed computations; their
formalization is partial. Screen wall time is an exploratory
shared-host diagnostic. The geometry alone does not set a complete
IC candidate ID or an online speed ratio.

The next factor-base selection should measure natural relation yield
and novel rank at fixed useful-column count, including point
decomposition, final linear algebra, and one-target descent. Those
stages decide whether a geometric increase helps the complete
pipeline.
