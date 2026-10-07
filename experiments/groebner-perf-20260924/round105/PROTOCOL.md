# Per-query normal-form contract

For each candidate basis G, let LM(G) use the independently decoded Boolean
monomial order (degree first, smaller mask first at equal degree). The map
processes all squarefree monomials in the reverse order. A standard monomial
gets a distinct unit vector. Otherwise choose the first dividing basis lead,
form the Boolean product of that basis row with the quotient monomial, cancel
its leading monomial, and XOR the already available vectors of its remaining
terms. Require the product lead to be the current monomial and every dependency
to be strictly lower. Thus each entry R(m) satisfies m - R(m) in the ideal
of G, by induction. A zero XOR for an original generator proves membership.

This implication is valid without trusting that G is complete. Forward proof
replay, reducedness, all applicable basis critical pairs and implicit Boolean
field pairs are still checked. An incomplete basis or forged derivation cannot
be accepted merely because its own generators map to zero. No producer roots,
ranks, cache contents or claimed completion flags are trusted.

## Applicability and budgets

- API mode 0 disables the map, mode 1 uses the density guard, and mode 2 bypasses
  only the density guard for correctness controls. Modes above 2 are rejected.
- Rings larger than 12 variables always use the sparse checker path. A map may
  have at most 64 standard monomials; seeing a 65th abandons the map and runs
  ordinary membership. No shift by 64 is performed.
- Mode 1 requires at least 2 * 2^n decoded input terms. MQ12 is deliberately a
  sparse-input fallback control: full-universe construction there would do
  much unnecessary work relative to its original membership phase.
- Check the map payload limit before allocating 8 * 2^n bytes. The limit covers
  the value vector only. Vector/allocator metadata, the existing input/basis
  sets and temporary hash products are outside this scope. Full process peak
  RSS remains separately recorded. A byte-cap fallback retains the original
  checker, and does not silently enlarge the map budget.
- Charge input-size planning, value initialization and degree/mask scanning,
  reducer searches, Boolean products, leading-term checks, vector accumulation
  and generator lookup work. The initial scan reservation is conservative and
  not an executed-instruction count. Work-budget exhaustion is inconclusive.
- NormalStats.work covers the attempted map method, including failed or
  abandoned construction. Ordinary fallback work is charged by the unchanged
  checker. The complete checker work includes both, with no budget reset.
- The existing proof-value byte and live-term caps retain their separate
  meanings. Automatic fallback does not disable proof or resource checks.

## Frozen comparison

The 13-case input fixture, producer limits, timeout, one warmup and four rotated
observations are inherited unchanged from round104. Compare f4-reuse against
f4-quotient, and matrix-reuse against matrix-quotient. Both members of each pair
use the same output API and derivation-buffer transfer. Generator reduction
steps and checker work may differ because this is a new membership algorithm;
they are checked against a native-free operation model. Producer traces and
proofs must agree when the two arms certify the same result. Retain every
unsuccessful attempt and all fallback costs; do not rerun selected timing cells.

The map is fresh for the current query's basis. No data dependent on another
target is reused. Construction and allocation are inside the original
algebra-and-certificate interval. Separate setup, proof serialization and
optional binary-to-list decoding retain their prior timing boundaries. No
GPU, generic F4/F5 leadership, unknown-target IC result or asymptotic speedup
is established by this experiment.
