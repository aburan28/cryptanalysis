# Algebraic Boolean certificate prototype

This next-stage prototype removes assignment enumeration from **verification**.
It does not yet replace the round-four solver or verifier. Its producer is a
simple sparse Buchberger reference with a work limit, not a fast F4/F5 engine.
High-degree regularity remains a hard computational problem.

The checker accepts the original equations, proposed reduced basis, and a DAG
whose operations are input reference, XOR, and multiplication by a squarefree
monomial. Nodes may reference only earlier nodes. It independently performs
four checks:

1. Evaluate every derivation and compare its selected outputs with the supplied
   basis. This proves output-ideal inclusion in the input ideal modulo the
   Boolean field equations.
2. Reduce each original input generator to zero using the proposed basis.
   This proves the reverse ideal inclusion.
3. Check the basis is reduced and test all basis/basis critical pairs.
4. Test the critical pairs with the implicit equations `x_i^2+x_i`. These
   cannot be omitted: the singleton `xy+1` is not a Boolean Groebner basis.

Let `H_i=x_i^2+x_i`. If `x_i` divides the leading monomial `L` of `g`, then
the ordinary-ring S-polynomial is `x_i*g + (L/x_i)*H_i`. Reducing by all field
equations yields the squarefree representation of `x_i*g`, which the checker
reduces by the candidate basis. If `x_i` does not divide `L`, the leading terms
are coprime and the product criterion applies. Pairs among field equations
also reduce to zero. Thus successful pair checks establish the Buchberger
criterion for the basis together with the field equations. Multiplication in
the DAG is also interpreted modulo those field equations.

This follows established Boolean Groebner methods, not a novel F6 algorithm.
[Hinkelmann and Arnold, section 2.2](https://arxiv.org/html/1010.2669v1#S2.SS2)
discuss the required field pairs and give `xy+z` as an example where ignoring
them is wrong. The checker uses the explicit ordinary-ring identity above;
it does not assume intermediate ordinary polynomials are already multilinear.
Membership witnesses are also an established approach; see the transformation
matrix functionality in the [Singular manual, liftstd](https://www.singular.uni-kl.de/index.php/singular.pdf).

`algebraic_certificate.py` imports no solver code. Its set-based arithmetic
is separate from the producer's sorted-tuple parity arithmetic. The verifier
has work and retained-term limits; exhaustion returns **inconclusive**, never
verified and never a refutation. A valid certificate reports ideal equality
and reduced Groebner completion, but no root count or root list. Neither the
producer nor the verifier allocates a `2^nvars` array. The current variable
parser bound is 4096; certificate size and work can still be exponential.

Run the current regression controls with:

```sh
python experiments/groebner-perf-20260924/round5/test_algebraic.py -v
```

Controls include 140 small random systems compared against the existing
independent truth-table/dimension oracle; 128-variable nonlinear pair-product
constraints involving every variable; ideals with unconstrained variables;
unit and zero ideals; missing field/basis pairs; missing ideal inclusion;
corrupted derivations; and inconclusive verifier budgets. The 128-variable
control is structurally easy and does not establish high-regularity performance.

One seven-variable random fixture exhausted the reference producer's initial
2,000,000-operation budget and completed with a larger declared limit. Zero
pair derivations are now discarded and unused final DAG nodes are pruned;
this controls proof size but does not make proof production asymptotically
cheap. That fixture remains in the deterministic regression stream.

Remaining admission work: stronger independent ordinary-ring CAS comparisons,
negative-certificate fuzzing, proof generation in the actual native solver,
proof generation/serialization/check timing and memory on difficult inputs,
and CI. Do not enable this path as a default or claim the scalable-verifier
goal fully complete from these structured controls alone.
