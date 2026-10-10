# Exact four-lift ECC2K-130 equal-B m6 solver gate

The source curve has order `4r`, with `r=680564733841876926932320129493409985129`.
The frozen ordinary query `Q` is in the order-`r` subgroup. The already
checked Sage receipt in the parent experiment certifies an order-four point
`T=(1,1)` and the four distinct raw points `Q+jT`, `j=0,1,2,3`, all with
the same `[4]` projection. This experiment puts their four x coordinates
in **one** target-first six-summand formula. It compares the frozen source
W24 and normal-weight-four factor bases at the same actual useful size
`B=11,743,888` points, retaining the first fixed-lift attempt from the
parent as a separate diagnostic.

## Frozen inputs and exact policy

The source field is `GF(2^131)` modulo `t^131+t^13+t^2+t+1`, and the source
curve is `EC1N131Ckb1h136f03e58c98`, `y²+xy=x³+1`. Use public query zero
from the parent 16-query prefix. The four target x values are read only from
the parent's checked `torsion_lifts.json`; reject any mismatch with the
public-point receipt or duplicate x. The old leaf and five-link S3 source
program is imported unchanged. Its exact membership equations and mask
limits remain those of the parent; no post-solver membership filter may
weaken them. Keep `candidate_id: null` until the full collection, matrix,
and target-descent policies are defined.

Let selector bits `s0,s1` choose lift `j=s0+2*s1`. For each target x bit,
encode the four-entry truth table as

`x_j = x_0 XOR s0*(x_0 XOR x_1) XOR s1*(x_0 XOR x_2) XOR
       (s0 AND s1)*(x_0 XOR x_1 XOR x_2 XOR x_3)`.

All constants are bitwise field encodings, and every nonconstant operation
is emitted to the native-XOR CNF. The target first-link input is this mux
output. Six exact leaves and the five S3 links are otherwise the same as
the parent. Selectors are ordered numerically to remove leaf permutations.

## Preregistered controls and first ordinary attempt

Before running the ordinary query, independently reconstruct its four
raw lifts in checked Sage, compare their coordinates to the parent receipt,
and check each `[4]` projection. Test the isolated target mux with
CryptoMiniSat 5.14.7: for each of its four selector choices, the expected
131-bit x must be SAT and the same selection with one x bit flipped must
be UNSAT. The parent experiment's 192 Sage source-point controls, two
planted full m6 chains, and four native-XOR leaf controls remain source
construction prerequisites.

Build one all-lift XCNF for `w24_source` and one for `normal4_source` on
the **same** public query. Run W24 then normal4 in sequence with one
CryptoMiniSat thread, `--maxtime=120`, an external 150-second wall guard,
and a 4 GiB RSS guard. Preserve formulas, exact source/input/binary hashes,
stdout, stderr, exit status, search progress, wall and RSS, including any
failed launches. A SAT model must be independently replayed against exact
factor-base masks, source points, signs, the selected raw target lift,
`[4]` relation, and row coefficients before a relation or rank is recorded.
If the solver reaches a cap without an answer, record `BOUNDED_UNKNOWN`;
it is censored, not an UNSAT result. The local host is unisolated, so times
are resource-capped diagnostics, not a controlled speedup ratio.

The all-lift mux is a distinct PDP implementation, not four independently
charged attempts. The parent fixed-lift result supplies only the `j=0`
control. A later four-attempt serial comparison must charge all four
attempts to one query under the same frozen total resource envelope.
Advance to held-out query prefixes only after a verified ordinary relation
or a justified solver-policy change. Stage outcomes alone do not establish
a one-target IC-versus-rho result.

## Post-run scope clarification

The S3 chain uses finite x coordinates at all five intermediate nodes.
An ordered decomposition with an intermediate point at infinity is outside
this formula's chart, even though its final projected group sum may be
valid. This clarification was added after the R1 solver attempts; neither
attempt returned a solution or an UNSAT certificate. A complete PDP policy
must cover or separately account for the exceptional intermediate branches.
