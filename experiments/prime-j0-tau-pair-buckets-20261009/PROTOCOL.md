# Two-bucket tau-orbit fixed-base scalar candidate

The three-bucket atlas in PR #566 compresses thirteen radix-1021 point rows
by allowing digit images under `1`, `tau`, and `tau^2`. This experiment limits
each stored seed to `1` and `tau`. It keeps only two projective accumulation
buckets and evaluates their sum as `B0 + tau(B1)`: at most one tau map and one
projective bucket merge per scalar. This is a public-scalar, fixed-generator
experiment on secp256k1.

## Frozen mathematics and atlas construction

Use the same exact subgroup lattice, `R=1021`, thirteen integer-radix
windows, and digit-length bound `D=840` as PR #566. The six-unit quotient of
residues modulo `R` has one zero node and `(R^2-1)/6` nonzero nodes. Tau
permutes these nodes because `gcd(R,3)=1`. At each node `v`, compute the
four-corner shortest representative `s(v)` with
`N(a+b*tau)=a^2+3ab+3b^2`. A stored seed at `v` may cover its own node and,
only if `3*N(s(v)) <= D^2`, the following tau node. Solve each directed cycle
for the minimum number of length-one/length-two segments. Use the same three
possible cut positions and deterministic ties as the three-bucket screen.

The digit for a residue is an exact unit image of `tau^e*s(v)` with
`e in {0,1}`. Independently check all `R^2` residue classes for a unique
code, exact congruence, and norm at most `D^2`. The thirteen-window
termination certificate is unchanged:

`sqrt(n/3)/R^13 + D*(1-R^-13)/(R-1) < 1`.

Check it by the exact integer inequality
`n < 3*(R^13 - D*(R^13-1)/(R-1))^2` with a positive right-hand root.
Retain the cycle lengths, segment counts, atlas digest, scalar-input digest,
and all failed checks. The point payload includes every row, the encoded
residue/seed map, and native metadata. It must be below **90 MiB**. The
initial resource estimate of 93,777 seeds per row and 92,320,400 bytes is
exploratory; the frozen screen and native retained-byte readout decide the
result.

## Correctness and full-operation gate

Replay the seven boundary and 512 seeded scalars in
`experiments/prime-j0-radix943-word-20261009/inputs.json` for exact
coefficient reconstruction. Check the 129 independent fixture points and
128 fresh points against binary double-and-add in the native evaluator.
Verify every stored point slot independently of the table builder, and
preserve raw commands and outputs. Compare reference U14, the three-bucket
candidate, and this two-bucket candidate on the same exact inputs. The
primary paired benchmark is U14 versus this candidate; the three-bucket
comparison diagnoses the effect of removing the exponent-two bucket.

The same-binary benchmark timer includes scalar reduction, lattice
selection, signed-limb recoding, lookup, unit actions, mixed additions,
the projective bucket merge, the tau map, affine conversion, and expected
point verification. Table construction and process launch are separate
preparation costs. Generate a frozen paired manifest only after correctness
and resource gates pass. Promote a CPU wall-time ratio only on a host
passing `docs/ISOLATED_BENCHMARKS.md`, retaining failures and noise gates.
Prior-art review must address endomorphism digit orbits and bucketed fixed
base multiplication before academic novelty is asserted.
