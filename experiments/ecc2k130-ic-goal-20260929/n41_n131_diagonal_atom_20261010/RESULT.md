# Reciprocal-coordinate diagonal atoms and a sparse S3 circuit

An eight-atom factor-base construction on the frozen N41 public point has
**512 distinct subgroup-usable points and 26 folded columns**, and an exact
4+4 index produced a relation using eight distinct columns. Expressing each
raw atom by its reciprocal x-coordinate removes the leaf inversion circuits.
Multiplying the two six-bit source masks directly at the four leaf links
reduced the saved Boolean formula from 11,795 to **9,399 AND gates** on the
same curve, public point, slot geometry, and eight-atom relation. Both
formulas passed full-assignment and group controls. Their unpinned
CryptoMiniSat searches reached the frozen 115-second solver-parent cap;
the gate reduction has not yet produced a faster ordinary relation search.

## Exact construction

Work on `E/F_{2^n}: y²+xy=x³+1`, with `n` odd. Let `w=u²+u` be a valid
source element, `P` a raw source point with `x(P)=1+1/u`, and `φ` the
coordinate-squaring Frobenius. The diagonal atom
`D(w)=P+φ(P)` has `x(D)=1/w`; hence its reciprocal coordinate
`a=1/x(D)` is exactly the linear source element `w`.

For nonzero x-coordinates `x_i=1/a_i`, the cleared third summation
polynomial is

`S3(x_1,x_2,x_3)=0  <=>  (a_1+a_2+a_3)² + a_1a_2a_3 + (a_1a_2a_3)² = 0`.

This supplies a balanced S3 tree with six-bit linear leaves at N41.
Writing `z=a_1a_2a_3` and taking the absolute field trace shows
`Tr(a_3)=Tr(a_1)+Tr(a_2)`, because `Tr(z²+z)=0`. Every source `w=u²+u`
has trace zero, so all reciprocal intermediates in this chart have trace
zero. The four raw lifts of the public N41 subgroup point have reciprocal
traces `[0,1,0,1]`; the explicit trace variant excludes the two odd-trace
lifts. The S3 equation specifies possible x-coordinate sums. The saved
controls and independent replay check the necessary signs and complete
elliptic-curve group equations.

On the prime subgroup, each diagonal atom is `α(P)` with `α=1+φ`.
The Frobenius eigenvalue `λ` satisfies `λ²+λ+2=0 (mod r)`, so `1+λ`
is nonzero and `α` is invertible. This preserves source factor-base size
and folded columns. The change is in the point-decomposition encoding.
The independent replay found `λ=256851699273 (mod 549756390943)` and
verified both the diagonal relation to the public `Q` and its inverse image
under `α` as a relation in the original source base.

## Frozen N41 gate

The field is `GF(2^41)` with modulus `t^41+t³+1`; the curve is
`y²+xy=x³+1`, the subgroup order is `549756390943`, and the public point
is `(1458168294740,1672312028033)`. Eight W6 rotations
`[0,5,10,15,20,25,30,35]` each have 64 signed atom states. The exact
union has `B=512` usable subgroup points and `K=26` signed/Frobenius
columns. The source has 32 rational masks per slot. The
[geometry screen](screen.json) checked all 32 raw reciprocal identities,
all 64 source subgroup atom states, and 256 point-addition/S3 incidences.

The [indexed join receipt](join_result.json) records one public-target
relation with eight distinct columns. Reusable 4+4 index setup took
16.131690083 seconds and peaked at 407,519,232 bytes RSS; the
target-dependent lookup took 0.916010500 seconds after setup. Five exact
sum hits occurred before the accepted row, four with repeated folded
columns. The [independent Python replay](verification.json) checks every
selected atom, all column distinctions, the subgroup sum, and the
Frobenius eigenvalue. These times are stage diagnostics from an unisolated
host; the index search and precomputation are separate from the SAT gate.

| Public-point XCNF variant | Variables | CNF clauses | Native XOR rows | AND gates | Full assignment | Unpinned solver stage |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Reciprocal leaves, generic field product | 20,489 | 37,229 | 8,396 | 11,795 | PASS | `CENSORED_TIME`, 115.079 s |
| Sparse six-bit leaf products | 16,586 | 30,041 | 6,889 | 9,399 | PASS | `CENSORED_TIME`, 115.081 s |
| Sparse products plus explicit trace | 16,586 | 30,049 | 6,889 | 9,399 | PASS | `CENSORED_TIME`, 115.105 s |

All three runs used one CryptoMiniSat 5.14.7 worker, native-XOR XCNF,
the same public subgroup point, a 115-second solver-parent wall cap, and
a 4-GiB combined-RSS ceiling. Their saved logs show active search and
empty stderr. Each formula has a full satisfying assignment from the
independently group-verified indexed witness. The solver-stage clocks begin
after the target-dependent formula is built, so these rows are formula and
solver diagnostics, not complete online IC measurements. The
[audit](audit.json) binds the frozen source, input, executable, formulas,
controls, terminal logs, and checked Sage runtime receipt. The proposal
retains `candidate_id: null` until relation collection, final linear
algebra, target descent, and scalar replay are specified and measured.

## Next method gate

The sparse circuit saves 2,396 AND gates, 3,903 variables, and 7,188 CNF
clauses, but the remaining difficulty is finding the compatible upper-tree
states. A concrete next experiment is to pair two diagonal atoms from the
same rotated source space. For a fixed seed sum, their product lies in a
small field subspace; the existing [exact bucket-norm method](../n41_w6_subspace_norm_20261010/RESULT.md)
shows how to reject a whole right-pair bucket against a specified residual.
Adapt that norm to the reciprocal atom coordinates, then propagate the
public target through several pair-output buckets jointly. At N41, require
an ordinary public-point row under a frozen cap and compare it with this
indexed relation and the same-target source-base controls. At N131, the
W14 source has 8,220 rational masks and 8,160 folded columns; ten atom
slots are the first unrestricted count with substantial support
(`16440^10/r ≈ 2119`, a uniform-group heuristic). Keep the five
same-rotation pair policy's actual base count and resource costs explicit
before attempting the published point.
