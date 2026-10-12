# N83 residual-search gate

This is a stage screen on curve `EC1N83Ckb1h2bcb59d56ad6`. The complete
index-calculus pipeline is still unspecified, so every proposal and receipt
has `candidate_id: null`. No result below is a single-target IC solve or a
speedup measurement.

## Prior gates covered

The [shifted S3 gate](../n83-costed-candidate-screen-20261005/SHIFTED_SAT_GATE.md)
already performed the requested planted group replay, exhaustive small-field
false-lift checks, and equal-cap ordinary-query attempts on all four raw
fibers for both `m=7,d=12` and `m=8,d=11`. Pinned planted models passed an
independent Sage replay. The nonvacuous small-field grid over `2^4` had zero
false and zero missed target-x pairs; the `2^3` grid was vacuous. All eight
ordinary fibers and all eight unpinned planted fibers reached the 45-second
outer wall cap without a verified relation. The four fibers within each
geometry belong to one target, not four independent queries.

## Frozen longer controls

| Control | Hidden summands | Public help | Circuit (variables / CNF clauses / XOR rows) | Bound and result | Sampled process-tree CPU / peak RSS |
| --- | ---: | --- | --- | --- | --- |
| [Original planted raw fiber](runs/m8_planted_f0_600s_v1/receipt.json) | 8 | Target only | 171,204 / 496,634 / 5,267 | 720.083 s outer wall, `BOUNDED_UNKNOWN` | 360.54 s / 209.1 MB |
| [Residual-six, short](runs/planted_pair01_six_sat_v1/receipt.json) | 6 | Correct first pair exposed | 115,769 / 335,179 / 3,783 | 45.052 s outer wall, `BOUNDED_UNKNOWN` | 13.02 s / 134.0 MB |
| [Residual-six, long](runs/planted_pair01_six_sat_480s_v1/receipt.json) | 6 | Same correct first pair | Same exact XCNF SHA-256 as short run | 480.067 s outer wall, `BOUNDED_UNKNOWN` | 427.12 s / 297.4 MB |

The original longer run regenerated the *exact* unpinned XCNF from the
45-second panel (SHA-256 `def88edb2549c46589cab6f66c0c93d6390385fc62e08fa1e0c39d4c56511cbb`).
The residual-six pair came from the private planted witness, then was
published in the [public fixture](runs/planted_pair01_fixture_v1/public_input.json).
The other six factor masks stayed hidden from the solver. Both residual-six
runs used XCNF SHA-256
`b1169b818682d5a69d66fb33bd402ce0912a9b20dd2ce709b0c5ef0e72f46765`.
The long run allowed 360 seconds internally, three million conflicts, 480
seconds externally, one solver thread, and 2 GiB process-tree RSS. Its outer
guard killed the process before a SAT model or UNSAT proof. The receipt keeps
that failure; it is not a negative existence result. Deterministic gzip copies
of the three raw solver stdout streams are archived beside their receipts;
decompression reproduces each receipt's stdout SHA-256.

The private remaining witness is independently checked by the
[installed-Sage replay](runs/planted_pair01_fixture_v1/sage_replay.json),
which used the repository's checked Sage launcher and archived its
[`--runtime-info`](runs/planted_pair01_fixture_v1/sage_replay_runtime_info.json).
It verified all six exact slot masks, factor-base orbit memberships,
nonidentity partial sums, five S3 links, the raw residual sum, and the
cofactor-four original target. The fixture is therefore known solvable;
the two residual-six failures are bounded witness-search failures.

These jobs ran on a contended host without an isolation receipt. Their wall
and CPU values are exploratory resource diagnostics. The original eight-sum
run and the residual-six runs use different circuits and limits, so their
times are not a solver speed ratio.

## Cost decision

The [exact pair-index screen](PAIR_INDEX_SCREEN.md) uses the measured
`m=8,d=11` base of 2,018 usable subgroup points per slot and 501 folded
columns. One distinct-slot pair list has 4,072,324 logical entries, or
65.2 MB at an optimistic 16-byte raw payload. Fixing one projected pair
leaves a six-sum support probability at most `B^6/r = 0.0000279317` for a
uniform subgroup target. By a union bound, a **fixed target-independent**
list needs at least 17,901 distinct pair prefixes to cover even half of
uniform targets. This is a necessary count for that search policy, not a
measured cost per probe or a bound on adaptive target-dependent selection.

For a conventional balanced four-pair join, the unfiltered `B^4`
pair-of-pair space is 16.58 trillion states. A uniform six-bit filter keeps
at least one *expected* full representation but still leaves an expected
259.1 billion intermediate states, or 3.11 TB of 12-byte raw point payload.
This conditional storage model exceeds the declared 2 GiB cap; it is not a
lower bound on all possible algorithms.

The current S3 SAT formulation fails to recover even the known-solvable
six-summand residual with the correct pair supplied and a longer cap. It
therefore does not justify building the pair table or launching thousands of
ordinary residual probes under the same solver and envelope. A meaningful
next solver design must change the six-sum witness search itself. The
[prior N83 next-calculus screen](../hamming-ic-e2e-20260929/N83_NEXT_CALCULUS.md)
identifies the W3 plus 4,000 W4-orbit five-summand geometry as a separate
algebraic-PDP investigation; its target support and query cost still require
measurement. Further time-cap increases for the present S3 SAT circuit
would consume resources without passing the planted promotion gate.

No ordinary pair-prefix relation yield, rank, factor logs, single unseen
target DLP, same-point rho solve, or verified online speedup was measured.
All five primary online IC phase costs, rho online time, and speedup remain
`null`. A later complete candidate must account for every failed target
attempt, matrix and log preparation separately, all five exclusive online
phases, scalar replay, and a paired isolated-host rho run.
