# Bounded quotient-map membership experiment

Round105 replaces repeated generator division with a fresh, bounded monomial
normal-form map inside the independent checker. The matrix and F4 producers,
owned/list proof formats, buffer-transfer derivation replay, reducedness,
critical-pair checks and independent equation/curve replay remain unchanged.
The candidate is opt-in; no production dispatch or GPU routing changes.

The previous frozen nine-variable controls have 31 equations, 3,029–3,726
monomial occurrences and 244 distinct input monomials. Their standard-monomial
space has dimension six. An untimed independent model agreed with ordinary
hash-set division on every Boolean singleton and original generator for all
eight certified cases, retaining five inconclusive cases. These observations
motivated the experiment and are not new timing claims.

The candidate runs only for at most 12 variables, at least twice as many input
terms as Boolean monomials, and at most 64 standard monomials. It represents
each reduced monomial as a 64-bit vector, constructs entries in increasing
monomial order, and XORs the vectors for each original equation. A strict
order check guards every dependency. A separate map payload cap is checked
before allocation. Sparse workloads, large rings, excessive dimension and
insufficient map space use the existing hash remainder; any attempted planning
work remains charged. All basis-dependent values are rebuilt inside the query.

The complete query includes fresh coefficients, production, map construction,
independent certification, proof ownership, extraction, equation/curve replay
and teardown. Reusable ring setup and artifact serialization/storage remain
separate. The F4 pair returns lists; the matrix pair returns owned binary proofs.
No paired comparison changes its output API. See [PROTOCOL.md](PROTOCOL.md).

This is a bounded engineering application of established quotient-algebra
techniques. See Faugère and Mou, [Sparse FGLM algorithms](https://arxiv.org/abs/1304.1238)
for related sparse multiplication-matrix methods. This implementation is not
an FGLM order conversion and establishes no new F6 or general asymptotic bound.
The map still scales exponentially with variable count and has an explicit cap.

Run the committed source with Python 3.13:

```sh
python3 experiments/groebner-perf-20260924/round105/run_validation.py --output /absolute/new/evidence --diagnostics
```

The runner freezes source custody, uses the shared heavy-work lock, rebuilds
optimized and UBSan libraries, and runs correctness/corruption controls before
the frozen diagnostic panel. All failures, inconclusive attempts and fallbacks
remain rows. These planted controls do not estimate natural relation yield or
complete an IC/rho comparison. Qualified/aggregate/IC online speedups remain
null without the required isolated CPU receipt.
