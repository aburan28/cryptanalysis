# Exact equal-B source leaf circuit and first ordinary m6 gate

This experiment turns the two frozen source-curve factor-base policies in
[`ecc2k130-normal4-equalb-m6-20261010`](../ecc2k130-normal4-equalb-m6-20261010/PROTOCOL.md)
into comparable six-summand Boolean point-decomposition formulas. Both have
`B=11,743,888` usable subgroup points. The first ordinary-query gate uses
public query index zero from the committed 16-query prefix; the fixture scalar
is excluded from the solver input. `candidate_id` remains null because the
collection, final relation linear algebra, and target-descent stages have
not been specified.

## Exact source leaf

The source field is `GF(2^131)` modulo `t^131+t^13+t^2+t+1`, and the curve is
`y²+xy=x³+1` with ID `EC1N131Ckb1h136f03e58c98`. Let `w` be the selected
trace-zero field parameter and `u=H(w)`, where
`H(w)=sum_{i=0}^{65} w^(2^(2i))` is the binary halftrace. For each leaf the
native-XOR CNF enforces

```
w*z = 1
u*(x+1) = 1
Tr(z) = 0
```

Here `w` and `u` are fixed linear maps of the selector bits, while `x` and
`z` are 131-bit field variables. These equations are necessary and sufficient
for `x=1+1/H(w)` to lift to a source-curve point: the curve's quadratic lift
criterion is `Tr(x+1/x²)=Tr(1/w)=0`. The inverse equation excludes `w=0`.
Each accepted `x` has two point signs; cofactor-four projection maps them to
the two signed subgroup points of one frozen factor-base class.

The normal4 selector is an exact four-hot vector in the 131-element normal
basis from Q1421. The W24 selector is 24 bits in the Q1420 trace-zero power
basis and is at most the committed last selected mask. The complete W24
census found zero in-base reciprocal partners, so the comparator plus the
rationality equation identifies exactly the first 5,871,944 ascending signed
classes. The complete normal4 census also found zero reciprocal partners.
No stochastic or post-solver mask acceptance filter changes either base.

## Six-summand chain

For public point `Q`, set the first chain input to its x coordinate and
introduce five intermediate x coordinates `T0..T4`. Links zero through four
enforce `S3(left, leaf_i, T_i)=0` using the identity
`S3(a,b,c)=(ac+b(a+c))²+b(ac)+1`; the final constraint is `x(T4)=x(leaf_5)`.
Order the six selectors numerically to remove permutations. A SAT model must
be decoded into rational raw points, lifted through all point signs, checked
against the public group sum, projected by `[4]`, folded to columns, and
independently replayed before it contributes a relation or rank. An x-only
SAT status by itself is a solver diagnostic.

## Frozen pilot and accounting

The checked-Sage control replays all 64 source-W24 and 128 normal4 point
controls from the frozen input receipt, then constructs a six-summand
positive instance per policy from the first six controls ordered by mask.
It evaluates every Boolean root, rejects a changed x bit and a changed
inverse-witness bit, and records the raw group-sum chain. These positive
instances test construction correctness and do not estimate ordinary-query
yield.

Build leaf and m6 formulas for each policy with the source files and inputs
hashed in each receipt. The first ordinary query is `point16` index zero.
Run CryptoMiniSat 5.14.7 at binary SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`
on `w24_source` then `normal4_source`, one thread, native-XOR XCNF,
`--maxtime=120`, an external 150-second wall guard, and a 4 GiB resident
memory guard. Preserve stdout, stderr, exit code, actual search evidence,
wall and peak RSS, SAT model or `BOUNDED_UNKNOWN`, and formula hashes. One
ordinary query per policy is a first feasibility gate, not a relation-yield
estimate; the already frozen 16/256/65,536 prefixes are the next stages.
Local wall ratios remain diagnostic on this unisolated host.

No native-XOR XCNF is passed to a plain CNF solver without an explicit
conversion and independently checked parity semantics. Solver setup, failed
attempts, curve checks, relation validation, and rank all remain separate
measurements. An actual single-target online comparison requires a complete
IC pipeline and the same-point rho reference under the repository contract.
