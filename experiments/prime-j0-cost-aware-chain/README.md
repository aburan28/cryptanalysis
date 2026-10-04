# Cost-aware Eisenstein representative search: frozen protocol

## Question and scope

For scalar multiplication on `y²=x³+b` over prime fields with a usable
order-three automorphism, can choosing the scalar's Eisenstein-lattice
representative by the **actual width-4 τ evaluation schedule** reduce group
operations compared with choosing the representative of smallest coordinate
`L1` norm? The supplied Xu–Yu–Han–Lu paper develops width-4 τ-NAF and its
tripling schedule. This experiment keeps that digit set and schedule fixed;
the proposed change is the representative-selection objective. Related
GLV lattice reduction and double-base chains already exist, so academic
novelty is **not** claimed by this protocol.

The source text supplied by the user has SHA-256
`8d20aca6b52c9b6d541e858bc97fe050528f4169c7283c8e2988042b2813d28e`.
The existing local τ implementation used as a reference has SHA-256
`128003abecae34fd715e7e5c82020ac79fd8ef2b4a42d1ee5f1be03c8bc410c3`
for `src/ec_tau.c`. That implementation is not yet on `main`; this
standalone prototype does not change or depend on its build.

## Exact candidate

Let `ω²+ω+1=0`, `τ=1−ω`, and let `λω` be the eigenvalue of `ω` modulo subgroup
order `r`. A scalar `k` may be represented by any `η=a+bτ` with
`a+b(1−λω) ≡ k (mod r)`. The current implementation obtains a short lattice
basis, rounds the coefficients of `(k,0)`, searches the 25 offsets
`du,dv ∈ [-2,2]`, and chooses the minimum `|x|+|y|` in the `1,ω` basis.

The candidate searches **exactly those same 25 representatives**. It
recodes each with the existing width-4 τ digit table and chooses the one
with the minimum predicted prepared-evaluation cost:

`10 × tripling_count + 16 × mixed_add_count + 1 × unit_rotation_count`.

These weights are multiplication equivalents with `S=M`: 10 for the cited
tripling, 16 for a point addition, and one for a nontrivial `ω` coordinate
rotation. They are frozen modeling assumptions, not measured time. Ties go
to the baseline `L1` choice. Both arms use identical precomputed seed points
and the same width-4 digit table. The candidate evaluates 25 recodings
instead of one, so its scalar-recoding overhead may outweigh any saved
curve operations, especially for the 64-bit pilot curves.

## Frozen diagnostic panel

After this protocol and `run.py` are committed and the PR is opened, run
`python3 experiments/prime-j0-cost-aware-chain/run.py panel` once with:

- subgroup orders `51131959441`, `157632877033`, and `42111239174233`;
- both primitive cube roots modulo each order, found from seeds `2,3,...`,
  each satisfying `λω²+λω+1 ≡ 0 (mod r)`; the same scalar list is used
  for both roots;
- six boundary scalars `0,1,2,3,r−2,r−1` plus 10,000 scalars per order from
  Python `random.Random(20261004)`, consumed in the displayed order;
- 25 offsets per scalar, the exact digit table in `run.py`, and the weights
  above.

Retain the complete diagnostic summary in `panel.json`: better/tie/worse
counts, mean predicted cost for each arm, median and total saved weight,
source hash, and any failure. The selection criterion for further work is a
positive mean predicted saving for both roots on at least two orders and zero correctness
failures. This is a gate for a C implementation, **not** a CPU speedup claim.
Do not interpret a cost-model win as a wall-time win.

## Independent correctness and next gate

`run.py selftest` compares both recodings with ordinary point multiplication
on `F_97` j=0 controls of subgroup orders 13 and 103, including all scalars
in each subgroup and 1,000 extra seeded scalars. Every representative is
also checked for congruence modulo `r`, and every digit expansion is
reconstructed exactly in `Z[τ]`. The panel performs those algebraic checks
on every scalar and retains failures rather than counting them as wins.

If the diagnostic gate passes, implement the selection in the C scalar
path, verify its exact point output against the existing scalar API on the
registered curves, and compare full scalar multiplication including
recoding and preparation. Any CPU wall-time claim must use the
[isolated benchmark service](../../docs/ISOLATED_BENCHMARKS.md) or an
equivalent host-level receipt with paired inputs, failures, and source
hashes. A measured comparison belongs in a follow-up PR.
