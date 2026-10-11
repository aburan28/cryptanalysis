# A single-branch quartic encoding for rotated four-atom decomposition

The rotated four-atom resultant has an exact **one-variable existential
quartic encoding** on the trace-zero source used by the N41 and N131
six-pair experiments. It uses a 60-term polynomial `A`, a 16-term
polynomial `B`, and one Artin--Schreier equation. This replaces the
two-root choice in the earlier 114/138-term quartic factorization while
preserving every algebraic resultant root. Exact sparse-GF(2) reduction
proves the identity, and independent integer-field arithmetic replays it
on all three four-atom blocks of the frozen N41 public relation and on
the N131 constructed positive control.

## Exact encoding

Let `a,b` be the two rotated pair seed coordinates, `P,Q` their rotated
pair products, and `z=1/x` the reciprocal output coordinate. Define
`S=a+b` and `Z=z`. In the [reduced polynomial record](norm_result.json),
`A(a,S,Z,P,Q)` has 60 monomials and `B(a,S,Z,P,Q)` has 16. The complete
266-term rotated resultant `H` satisfies the polynomial identity

```text
H(a,b,P,Q,Z) = A² + A B + (Z+S) B²,       S=a+b.
```

When `Tr(Z+S)=0`, the following is equivalent to `H=0`:

```text
there exists w in F_(2^n) with
    w²+w = Z+S,
    A+w B = 0.
```

Indeed the two solutions of the first equation are `w` and `w+1`, and
their quartic values multiply to `H`. The existential `w` selects the
correct conjugate quartic, so the solver needs one quartic equality and
one Artin--Schreier equality rather than a disjunction of two quartics.
Every permitted raw source atom has trace-zero reciprocal coordinate;
the trace homomorphism therefore gives `Tr(a)=Tr(b)=Tr(Z)=0` for any
defined four-atom source sum. Thus the equivalence applies throughout
the declared W6/W15 source, including the first four-atom block whose
two pair seeds differ.

The [derivation](derive_norm.py) starts from the archived universal
factors in variables `(a,v,u,P,Q)`, with `b=a+v²+v` and `z=u²+u`.
Flipping either `v` or `u` exchanges the two factors; flipping both
fixes each factor. Setting `w=u+v`, reducing by `v²+v=S` and then
`w²+w=Z+S` yields `A+wB`. The script independently substitutes
`b=a+S` into the original 266-term resultant and checks all 306
resulting monomials against the norm identity. The degree of `A` in
each of `P,Q` is at most four; the degree of `B` is at most three.

## Exact controls and search boundary

The [integer-field audit](audit_integer.py) uses a separate GF(2)
bit-polynomial implementation. It reconstructs source pair seeds and
products from the frozen N41 public witness masks and rotations, reads
each block's independently audited `z=1/x`, evaluates both sides of the
identity, and extracts
an existential `w`. The public point is
`(1458168294740,1672312028033)` over
`GF(2)[t]/(t^41+t³+1)`; the raw fourfold target lift is index 1.
The originating [seed-partitioned search](../n41_seed_partition_indexless_20261010/RESULT.md)
left masks, signs, seeds, and offset unfixed and independently verified
the twelve-column relation. This audit reuses that frozen witness as a
positive assignment; it is an encoding check, not a new relation search.

| Exact bit-field control | Resultant | Zero quartic branches | Existential witness |
| --- | ---: | ---: | --- |
| N41 free four-atom block, rotations 0/5 | 0 | 1 | checked |
| N41 constrained block, rotations 10/15 | 0 | 1 | checked |
| N41 constrained block, rotations 20/25 | 0 | 1 | checked |
| N131 W15 constructed block, rotations 26/39 | 0 | 1 | checked |
| One-bit `P` perturbation of each row | nonzero | 0 | absent |

The [audit receipt](audit_result.json) contains exact `a,b,P,Q,z`,
`A,B`, both branch values, the selected `w`, and SHA-256 digests of its
inputs. The N131 control uses
`GF(2)[t]/(t^131+t^13+t²+t+1)`; its source has 197,292 usable points
and 16,381 signed-Frobenius columns. All four perturbation controls
preserve the Artin--Schreier right-hand side and fail the resultant.
Both programs run with ordinary Python integer arithmetic; these are
exact correctness results, with no CPU timing comparison.

The encoding removes one Artin--Schreier root variable and the explicit
quartic branch disjunction from a future joint solver. It does not by
itself generate candidate four-atom outputs from the public target. In
fact, a valid source product family always has its actual four-atom
output as a witness to these equations, so the block equations alone
cannot reject that family before the output is coupled to another block
or the public target.
Explicitly expanding the two N131 W15 product families would still visit
`2 × 2^28 = 536,870,912` families before the free-pair join. A 600-second
single-worker gate would require at least 894,785 family visits per second
for that stage alone. The measured earlier N41 factor-and-build diagnostic
was 4.403 milliseconds per family on an unisolated host, so the next
algorithm must keep product families symbolic and couple the three block
equations to the public target before expansion. The N131 public query
remains gated by a complete one-worker, 600-second, 4-GiB source-bound
projection. This is a proposal-stage component with `candidate_id: null`.
