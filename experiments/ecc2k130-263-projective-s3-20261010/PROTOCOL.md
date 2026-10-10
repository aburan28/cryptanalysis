# Projective S3 chart for the Q1420 equal-size W24 comparison

The source and native degree-263 descendant W24 bases, each with
`B=16,772,828`, use the same frozen Q1420 public point and four exact raw
target lifts as the parent [native circuit gate](../ecc2k130-263-native-w24-m6-20261010/RESULT.md).
The parent formula constrains every balanced-tree intermediate by a finite
field x coordinate. This gate adds the identity point as an intermediate
state and measures the resulting circuit cost and bounded solver behavior
on those same inputs.

For the normalized binary curve `y²+xy=x³+b`, the third summation
polynomial is `S3(x1,x2,x3)=(x1*x2+x2*x3+x3*x1)²+x1*x2*x3+b`.
Represent a finite point by `(X,Z)=(x,1)` and the identity by `(1,0)`.
The multihomogeneous equation is

```
H3 = (X1*X2*Z3 + X2*X3*Z1 + X3*X1*Z2)^2
     + X1*X2*X3*Z1*Z2*Z3 + b*(Z1*Z2*Z3)^2 = 0.
```

Each intermediate gets one Boolean `Z` and 131 field bits for `X`;
`Z=0` forces `X=1`, so infinity has one encoding. Leaves and the four
target choices have `Z=1`. The same six native leaf equations, base-mask
cutoffs, leaf ordering, S3 tree, and frozen target mux are reused. A
candidate SAT model must still be decoded into actual point signs and
checked against the public group sum; an x-only root is not a verified
relation.

Before building the N131 formula, exhaustively test the projective relation
over `GF(2^5)` and `GF(2^7)` for `b=1` and `b=t` against the full rational
group law, including identity and two-torsion x classes. Test the N131
exceptional branch by taking the first frozen raw W24 leaf twice with
opposite signs, so pair01 is infinity, and the next four archived controls
as finite summands. Checked Sage must produce the group-sum chain, and a
separate Boolean evaluator must accept that witness and reject mutated
intermediate `X` and `Z` bits. Preserve source/input/runtime hashes and
any failed controls.

Build one projective six-summand native-XOR XCNF per source and descendant
policy with a 300-second external wall and 4-GiB RSS construction cap.
Preserve exact formula bytes or lossless archives and receipts. Independently
audit header, clause/XOR counts, input hashes, and the exceptional control.
Only after those gates pass, run CryptoMiniSat in source then descendant
order, one thread, `--maxtime=120`, a 150-second external wall cap, and a
4-GiB RSS guard. Retain raw stdout/stderr, status, exit code, conflicts,
memory, and wall time. Pair each result with its finite-chart parent row
without turning a censored cell into a relation or a speed claim. The host
does not have a CPU-isolation receipt, so any wall ratio is exploratory.
