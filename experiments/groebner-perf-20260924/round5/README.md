# Algebraic Boolean certificate prototype

This opt-in experiment removes assignment enumeration from **verification**.
It does not replace the round-four solver or verifier. It includes a sparse
native Boolean F4 producer with derivation tracking, alongside the original
Python Buchberger reference. High-degree regularity remains a hard computational
problem, and the frozen dense MQ workloads retain their inconclusive outcomes.

The checker accepts the original equations, proposed reduced basis, and a DAG
whose operations are input reference, XOR, and multiplication by a squarefree
monomial. Nodes may reference only earlier nodes. It independently performs
four checks:

1. Evaluate every derivation and compare its selected outputs with the supplied
   basis. This proves output-ideal inclusion in the input ideal modulo the
   Boolean field equations.
2. Reduce each original input generator to zero using the proposed basis.
   This proves the reverse ideal inclusion.
3. Check the basis is reduced and test all non-coprime basis/basis critical
   pairs. Coprime leading monomials use Buchberger's proven product criterion.
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

Build and run the portable controls with Python 3.10+ and a C++17 compiler:

```sh
python experiments/groebner-perf-20260924/round5/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round5 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round5/audit.py
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

## Native proof producer and independent qualification

`native_f4.cpp` processes batches of critical pairs at the same degree, performs
symbolic preprocessing, and applies sparse Gaussian row reduction. Multiplication
and every row XOR append derivation nodes; the final graph retains only ancestors
of output basis rows. Full Boolean completion and interreduction retain witnesses.
Its monomials use 64-bit masks, so the native bound is 1..64 variables, whereas
the Python reference/checker can accept wider masks. There is no assignment
enumeration or full monomial-universe table in this path. This is an experimental
F4 implementation, with no F5-signature or GPU performance claim. Its matrix flow
follows the established [F4 outline in the msolve paper, section 3.1](https://perso.lip6.fr/Mohab.Safey/Articles/msolve-issac21.pdf).

`native_f4.py` charges input preparation, subprocess launch/transport, proof
parsing, and independent checking. It returns complete/verified only after the
checker succeeds. Work, proof-node, matrix-row, subprocess-time, and verification
limits return inconclusive/timeout. No partial basis is promoted. An untraced
arm exists only to measure instrumentation cost; it is explicitly unverified.
The original 12-variable dense engine and fast bounded evaluation solver remain
unchanged. This sparse path does not automatically replace either one.

`validate_singular.py` compares both producers against **ordinary polynomial
ring Singular**, with explicit `x_i^2+x_i` generators and grevlex order. The
native results match all **141 ideals**. Three default-work-budget attempts
were inconclusive and then passed recorded qualification retries with a larger
declared limit; those failed costs/statuses remain in the receipt. The Python
reference exhausted its declared budget on two of those controls. This is a
correctness qualification, not an equal-budget speedup claim. The local run
used Sage 10.10.rc0 through the installed-runtime integrity gate:

```sh
python scripts/sage_release.py run --sage /path/to/sage-binary -- -python \
  experiments/groebner-perf-20260924/round5/validate_singular.py
```

Portable CI runs optimized and UBSan native builds, 96 additional random
differential systems, 672 adversarial mutations, malformed proof/protocol
controls, and explicit native cases through 64 variables. The Singular receipt
is a local qualification; CI replays retained certificates and audits source
versions but does not claim to rerun Sage/Singular on hosted workers.

## Measurement and limits

`benchmark.py` freezes eight algebra workloads and records traced native,
untraced native, and Python-reference attempts with three measured repetitions
plus a recorded warmup. Input construction and binary compilation are outside
the timed interval; subprocess startup and proof checking are inside it. The
four difficult workloads (a random eight-variable case and planted dense MQ
systems at 12, 16, and 21 variables) exhaust the declared budgets. They remain
rows and do not count as wins. The 21/32/64-variable pair-product controls and
the 64-variable free-variable control verify successfully but are structurally
easy. Parent/child process high-water memory is recorded with units; per-case
and simultaneous total peaks remain unknown.

The checker now applies the product criterion. On identical saved native
proofs, a 15-pair checker-only comparison measured:

| Control | Previous median | Product-criterion median | Paired geometric mean, 95% bootstrap interval |
| --- | ---: | ---: | ---: |
| Pair products, 21 variables | 1.452 ms | 0.280 ms | 5.05x [4.44, 5.52] |
| Pair products, 32 variables | 3.856 ms | 0.570 ms | 6.00x [5.07, 6.82] |
| Pair products, 64 variables | 29.934 ms | 2.098 ms | 10.15x [7.26, 13.55] |
| Shared-variable control, 64 variables | 0.0346 ms | 0.0348 ms | 0.997x [0.991, 1.003] |

These are checker-only speedups, not complete solve or IC speedups. The
unpruned checker is preserved in `baseline/`; both versions accept the same
retained certificates. Full before/after proof-production receipts are retained
separately, including failed attempts. All controls are algebra diagnostics,
with no factor-base yield, target DLP recovery, or rho comparison.

Remaining work includes difficult wide-variable systems within practical proof
budgets, faster native transport, integration with the production F4/F5 paths,
the single-query GPU crossover, and structural algorithm experiments. Do not
enable this path as a default or infer high-regularity performance from these
structured controls. No new F6 algorithm or asymptotic bound is claimed.
