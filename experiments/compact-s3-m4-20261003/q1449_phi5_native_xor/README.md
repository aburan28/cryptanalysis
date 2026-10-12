# Q1449: native-XOR solver for the compact phi5 stage

Q1449 keeps Q1448's exact torsion-symmetrized five-input circuit, curves,
factor bases, public targets, and Q1438 workload IDs. It sends the original
XOR equations to CryptoMiniSat 5 in XCNF rather than expanding them into
ordinary CNF. The solver is single-threaded. Every SAT model is replayed
against exact curve arithmetic; an algebraic model that fails relation
checks is blocked by its ordered four leaf x masks and target selector.
The blocking path was frozen but was not entered in these ordinary runs.

This is the existing `PDP4phi5` stage with a different solver variant,
recorded in the [frozen protocol](protocol.json). It remains a Q proposal:
`candidate_id: null`, `isogeny: "none"`, and no complete IC pipeline or
degree-131 work estimate. N53 uses curve
`EC1N53Ckb1hf77aab617904`, actual B=324,042, folded K=3,057, and
workload `6dfaff711b08`; N83 uses `EC1N83Ckb1h876c2921cb64`, actual
B=408,131,750, folded K=2,458,625, and workload `9ce3dd487274`.
The exact factor-base set digests are in the protocol.

The [pinned controls](controls.json) return verified four-point relations
at both degrees. The protocol, source hashes, CryptoMiniSat binary hash,
runtime receipt, XCNF hashes, 60-second nominal solver budget, one-million
conflict cap, 32-model limit, and 75-second outer safeguard were committed
before either ordinary query. The ordinary runner's effective external
subprocess timeout is remaining solver budget plus five seconds. On this
host, CryptoMiniSat did not exit at its internal `--maxtime 60` setting,
and both processes reached that external timeout at about 65 seconds.

| Ordinary field | XCNF variables / CNF clauses / native XOR rows | Formula build | Solver process | Peak child RSS | Verified relations |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 | 62,428 / 201,649 / 2,226 | 0.699 s | 65.025 s, external timeout | 161,955,840 bytes | 0 |
| N83 | 150,707 / 438,667 / 3,486 | 0.602 s | 65.014 s, external timeout | 231,571,456 bytes | 0 |

The native XCNF uses fewer Boolean variables and clauses than Q1448's
expanded CNF, but this configuration did not activate XOR Gaussian
elimination. CryptoMiniSat's logs say it used zero matrices at both
degrees: the N53 53-row multiplication components have 2,809 columns,
and the N83 83-row components have 6,889 columns, above the default
1,000-column limit. Larger connected matrices were also rejected. The
logs' last restart lines report about `414K` N53 and `185K` N83
conflicts, which are partial, rounded progress values; an exact final
operation count was not emitted after external termination. These
unisolated runs are exploratory stage diagnostics, not controlled wall
speedups or complete target solves.

The [independent archive audit](verification.json) regenerates both
initial XCNFs, checks their compressed artifacts and raw outputs, and
replays every returned model (none was returned here). Both ordinary
cells are censored. Natural relation yield, novel rank, cost per useful
row, successful N53-to-N83 solve growth, and complete N131 `2^x` remain
unknown. The challenge gate remains closed.

The next specific test is a separately frozen variant with a bounded
larger Gaussian column limit that actually admits the small field-product
matrices. It should verify matrix activation on controls before ordinary
queries; a faster censored prefix alone would not establish a relation.
