# N83 costed candidate screen, 2026-10-05

The exact source curve is `EC1N83Ckb1h2bcb59d56ad6`, with subgroup order
`r=2417851639230796216685689` and cofactor four. These are **base geometry
and conditional storage** measurements, not complete IC runs. All five
target-online phase costs, the cold pipeline total, ordinary-query PDP yield,
final relation rank, and a same-point rho reference remain `null` in the
[machine ledger](cost_screen.json). Thus every online speedup is unknown.
The checked Sage runtime receipts, producer logs, exact geometry, and
losslessly packed representative sets are in [`runs/`](runs/). Run
[`pack_representatives.py`](pack_representatives.py) to verify the unpacked
SHA-256 of every set against its original immutable geometry receipt; the
`.json.gz` payloads use deterministic gzip headers. Timing on this ordinary macOS
host is exploratory and cannot support a controlled speed claim.

| Base and arity | Factor coordinates | Actual usable `B` per slot | Folded `K` | Exact tuple count / `r` | One explicit distinct-slot pair table, raw payload | Frozen geometry gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Full W3/W4, five sum | 415 | 1,936,390 | 11,665 | 93,832.98 unordered multisets | Different root-index design; 11,293,994,675 pair-state loops in prior geometry | Exact geometry; planted SAT bounded unknown |
| Shifted `m=6,d=14` | 84 | 16,174 | 4,062 | 7.404 ordered tuples | 4,185,572,416 bytes for 261,598,276 pairs | Exact geometry in 69.6 s |
| Shifted `m=5,d=17` | 85 | 131,652 | 32,767 | 16.357 ordered tuples | 311,980,483,872 bytes for 17,332,249,104 pairs | **Over 900 s cap**: 1,053.8 s; retained as a failed resource gate |
| Shifted `m=7,d=12` | 84 | 4,036 | 1,018 | 7.215 ordered tuples | 260,628,736 bytes for 16,289,296 pairs | Exact geometry in 21.3 s |
| Shifted `m=8,d=11` | 88 | 2,018 | 501 | 113.747 ordered tuples | 65,157,184 bytes for 4,072,324 pairs | Exact geometry in 12.5 s |

The tuple models differ: W3/W4 is a common Frobenius-invariant base counted
as unordered multisets; shifted slots are labeled Frobenius images counted
as ordered tuples. These ratios cannot be read as target coverage, solver
yield, or an IC speedup. The pair-table sizes assume every pair record stores
a compressed sum point and two fixed-width indices with no container
overhead. They are conditional design sizes, not actual peak memory or a
general lower bound on other solvers. In particular, a SAT/polynomial solver
may avoid a pair table. The 2 GiB geometry-process cap is separate from a
future solver's resource envelope.

The five-summand run completed its arithmetic and orbit enumeration but
exceeded its frozen 900-second process cap. The original producer checked
the cap during x enumeration only; the [corrected producer](sage_measure_shifted_geometry.py)
checks orbit folding too. The machine ledger labels the original exact result
`EXACT_GEOMETRY_OVER_FROZEN_WALL_LIMIT`; it is not promoted as a within-cap
measurement. The result remains useful for rejecting a naive explicit
pair-index design on storage grounds.

The signed-Frobenius quotient has a verified group-theoretic coefficient:
for the one-step squaring map `F` on this subgroup,
`F(P)=[254512724090651164922414]P`. The scalar has order 83 modulo `r`.
The [certificate](runs/frobenius_scalar_v2/frobenius_scalar.json) checks the
base-field Frobenius polynomial, both candidate roots, the selected root on
`G`, and `lambda^83=1`. The first certificate attempt used the extension-field
Frobenius polynomial and failed; its [log](runs/frobenius_scalar_v1/producer.log)
is retained. This coefficient permits orbit-related factor logs to share a
column, but it supplies no factor logs by itself.

## Decision under the declared cost model

- If a solver materializes even one explicit distinct-slot pair table under
  a 2 GiB raw-payload ceiling, `m=5,d=17` and `m=6,d=14` fail that design
  gate. `m=7,d=12` and `m=8,d=11` pass the **raw-payload** screen; actual
  implementation memory still has to be measured, including multiple
  tables, indexing, and I/O.
- `m=7,d=12` and `m=8,d=11` are unresolved alternatives. The former has
  fewer summands and 84 factor coordinates; the latter has 501 rather than
  1,018 folded columns and one-quarter as many candidates per distinct-slot
  pair table. The latter also has one more summand and 88 coordinates.
- The W3/W4 five-sum circuit has a checked planted witness but returned
  `BOUNDED_UNKNOWN` at its 45-second SAT cap with factor x values hidden.
  Giving the circuit three intermediate x rows made the planted branch solve
  in 0.198 seconds. This isolates witness discovery as a live cost risk; it
  does not estimate ordinary-query yield.

The next equal-cap pilot should instantiate exact seven- and eight-sum
formulations on the same frozen ordinary subgroup targets. For each query,
attempt all four raw target fibers under multiplication by four; retain
SAT/verified, UNSAT, timeout, OOM, and false-lift outcomes and all target
independent encoding costs. First require planted-witness replay and
small-field false-lift controls. The pilot should compare full PDP costs and
memory, not solver core time alone. Only a survivor with verified ordinary
relation yield and a rank path should be wired through factor-log solving,
one unseen target descent, scalar replay, and same-point rho timing under an
isolated-host receipt.

The shifted-subspace design follows the Frobenius-related base approach in
[Galbraith, Granger, Merz and Petit, *On Index Calculus Algorithms for
Subfield Curves*](https://sacworkshop.org/SAC20/files/preproceedings/18-IndexCalculus.pdf).
The prior W3/W4 SAT control and its limits are documented in
[`N83_W34_SAT_GATE.md`](../hamming-ic-e2e-20260929/N83_W34_SAT_GATE.md).
