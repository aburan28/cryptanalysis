# Paired ECC2K-130 native-XOR-to-CNF solver gate

This stage experiment tests whether a faithful ordinary-CNF representation
lets Kissat find a six-summand relation on the first frozen Q1420 ordinary
query where the native-XOR CryptoMiniSat `wz_only` circuit reached its cap.
It keeps the exact source and degree-263 descendant formulas, public query,
`B=16,772,828` usable W24 points per curve, and witness-control inputs.
The primary workload ID is `eee7f6ee5f6b`; the transport route is
`IW1E263d1hadee4e69fa3d`. This is a PDP-stage comparison with
`candidate_id: null` until a relation, rank policy, final matrix, and target
descent exist.

The [source manifest](source.json) pins four compressed XCNF inputs, both
fixed-witness z0 unit deltas, the Git input commit, and the Kissat executable
digest. The two fixed-witness controls must return SAT and replay against all
original ordinary clauses and native XORs. Both ordinary cells must retain
their raw status even when capped; a SAT model becomes a verified relation
only after XCNF replay and an independent group-sum check. An `UNKNOWN`
return remains `BOUNDED_UNKNOWN`, not an UNSAT result. An UNSAT answer needs
a separately checked proof before it can be promoted beyond solver status.

Each XCNF native line is the XOR of three signed literals equal to one. For
each assignment of their truth values with even parity, emit one CNF clause
excluding that assignment. The four clauses have exactly the same satisfying
assignments as the original XOR, even when an input literal is negative.
Preserve all ordinary clauses and existing variables; no auxiliary variables
are introduced. Validate the eight truth-table cases and check the source
header count, every literal range, output clause count and SHA-256 before
solver launch. The output CNF is a deterministic reconstruction, not a
separate factor-base policy.

Run order is source z0 control, descendant z0 control, source ordinary Q0,
descendant ordinary Q0. Use pinned Kissat 4.0.4 with `--time=20` for each
control and `--time=120` for each ordinary cell, one process per cell, an
external 150-second wall guard for ordinary cells, and 4 GiB sampled process
RSS guard. Save source/input/CNF hashes, raw stdout and stderr, exit code,
reported status, wall and CPU usage, sampled peak RSS, and independent model
replay. A preflight failure is a preserved `PRODUCER_FAILURE` and must not be
mistaken for a solver search. Native-XOR CryptoMiniSat comparator transcripts
remain the archived Q1420 result; cross-run wall ratios on this unisolated
host are exploratory only.

Short in-memory pilots preceded this protocol: both fixed z0 controls
returned SAT with complete XCNF constraint replay under 20 seconds, while
both ordinary Q0 cells returned `UNKNOWN` under a 30-second Kissat limit.
Those observations selected no policy and are not the frozen 120-second
ordinary outcome. The run generated from this protocol is a same-input
solver-stage result; it cannot establish natural relation yield, useful rank,
one-target online time, or an ECC2K-130 speedup by itself.
