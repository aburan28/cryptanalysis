# Q1426: fixing the raw target lift shortens capped SAT calls

Q1426 removed the large target-preimage selector from Q1425's ordinary
four-leaf formula by fixing one raw lift per cell. On the exact N53
ordinary target, four witness-independent selected lifts took 2.25–3.40
seconds each at the configured first-call limits, compared with 13.04
seconds for Q1425's all-lift formula. On the exact N83 ordinary target,
all four lifts took 4.28–5.03 seconds each, compared with 29.68 seconds
for Q1425's all-lift formula. These are exploratory capped-call timings:
every call returned `BOUNDED_UNKNOWN` before a first SAT model, so the
reduction is **not** a lower cost per relation or a solve speedup.

The one-lift encoding passed a known-solution control at both degrees.
That control pins only the four known raw leaf coordinates and inserts
both exact pair-root lemmas; its selector is fixed by the one-lift
formula. The accepted four-point relations replay on the exact bases.
The [control receipt](control_check.json) and [archive verifier](verification.json)
are committed with the eight ordinary-cell receipts.

## Frozen input and measured cells

Q1426 is an `ISO0` proposal with null candidate and run IDs. The
underlying curves and bases are unchanged from Q1425: N53 curve
`EC1N53Ckb1hf77aab617904`, Q1301 W≤3, B=24,062 usable subgroup
points and K=227 folded columns; N83 curve
`EC1N83Ckb1h876c2921cb64`, Q1325 W≤5, B=30,977,592 and K=186,612.
Exact set digests, targets, selected lift coordinates, source/library
hashes, and resource limits are in [`freeze.json`](freeze.json).

| Degree | Lift index / total lifts | PDP wall s | SAT wall s | Peak RSS MiB | First SAT model | Status |
| --- | --- | ---: | ---: | ---: | --- | --- |
| N53 | 112 / 428 | 2.253 | 2.186 | 91.3 | no | `BOUNDED_UNKNOWN` |
| N53 | 417 / 428 | 2.689 | 2.604 | 68.6 | no | `BOUNDED_UNKNOWN` |
| N53 | 357 / 428 | 3.400 | 3.324 | 97.0 | no | `BOUNDED_UNKNOWN` |
| N53 | 282 / 428 | 3.359 | 3.264 | 96.7 | no | `BOUNDED_UNKNOWN` |
| N83 | 0 / 4 | 4.846 | 4.652 | 172.2 | no | `BOUNDED_UNKNOWN` |
| N83 | 1 / 4 | 5.028 | 4.827 | 140.1 | no | `BOUNDED_UNKNOWN` |
| N83 | 2 / 4 | 4.925 | 4.747 | 156.2 | no | `BOUNDED_UNKNOWN` |
| N83 | 3 / 4 | 4.280 | 3.983 | 162.2 | no | `BOUNDED_UNKNOWN` |

Each cell ran one SAT call. The configured limits were 100,000 conflicts
and 25 CPU seconds per call, within a 90-second wall envelope. The
CryptoMiniSat C API reports `BOUNDED_UNKNOWN` without its conflict count
or exact stopping reason. The eight traces contain no SAT model and
therefore no root-oracle call. Natural relation yield, cost per useful
row, and rank novelty remain unknown. N83 covers every raw lift, but a
bounded result for every lift is not a proof of nonexistence. N53 covers
four of 428 lifts and is a sliced diagnostic, not a complete one-target
query.

At N53 the one-lift formula has 26,784 CNF clauses, versus 49,498 in
Q1425's all-lift ordinary formula. At N83 the counts are 65,678 versus
65,926. Both retain 8,427 and 20,667 AND gates respectively, and all
four leaves remain variable. The stage clock includes formula building,
loading, SAT, root work, relation checking, and other overhead; each
receipt preserves these exclusive charges. The host has no CPU-isolation
receipt, so wall-time ratios are exploratory.

## Distance to the \(2^{61}\) complete-solve target

The Q1426 N131 cold and one-target-online work exponents are null. The
change reduces selector cost on these frozen ordinary queries but does
not reach a decomposition or measure a relation rate. The separate
[Q1422 fixed explicit-index analysis](https://github.com/aburan28/cryptanalysis/pull/625)
gives an exact-base floor of \(2^{88.356}\) logical index actions and a
globally relaxed floor of \(2^{78.552}\) actions for that index family,
respectively 27.356 and 17.552 bits above \(2^{61}\). Those action
floors do not bound this SAT/root hybrid or supply its missing complete
work estimate.

The next solver experiment should impose useful exact S3 information
*before* the first SAT model. A candidate is a pair-root propagator at
partial leaf-pair assignments or an assumption scheduler that reuses
learned clauses. It must still handle all target lifts, report ordinary
relation yield and novel rank, and charge every failed branch.

The archived [`pilot_v1`](pilot_v1/README.md) source failed before a
solver call because of a Python module-name collision. V2 was frozen
before the correctness control and ordinary measurements.
