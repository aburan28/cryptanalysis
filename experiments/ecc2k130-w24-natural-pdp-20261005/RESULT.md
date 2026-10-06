# Source W24/m6 native-XOR SAT gate: planted search unresolved

The first exact-base six-summand SAT attempt stopped at its predeclared
planted control. It did **not** search the frozen natural target, so it says
nothing empirical about natural W24 decomposition yield. The planted
formula is satisfiable by construction in the curve group, but
CryptoMiniSat returned `INDETERMINATE` at 100,002 conflicts under the
100,000-conflict/30-second control bound. This is a solver-stage failure,
not an UNSAT certificate or evidence of zero relations.

The [protocol](PROTOCOL.md) and [configuration](CONFIG.json) were pushed in
[PR #332](https://github.com/aburan28/cryptanalysis/pull/332) before the
control run. It uses the exact source W24 prefix from the parent
four-policy gate: 8,386,414 signed columns and `B=16,772,828` actual usable
subgroup points. Its sole intended natural target is the predeclared public
point in workload `eee7f6ee5f6b`. The mask/rationality circuit, four
`[4]` fibers, and five S3 links were implemented without reading the known
target scalar. The control uses the first six published source control masks
and pins their mask bits and raw-target fiber, leaving inverse witnesses and
the four S3 intermediate values for SAT to determine.

| Stage | Result | Evidence |
| --- | --- | --- |
| Small-field XCNF gate check | PASS | Seven correct/incorrect product pairs, including Karatsuba cases, and seven prefix-bound cases. |
| Planted formula profile | 91,861 variables; 50,208 AND gates; 40,197 XOR rows; 152,281 CNF clauses; 3,863,572 XCNF bytes | [Profile receipt](runs/v1-planted-profile/receipt.json); its XCNF is byte-identical to the solver input. |
| Planted SAT search | `INDETERMINATE`, exit 15, 100,002 conflicts, no model | [Run receipt](runs/v1-planted/receipt.json) and [losslessly compressed raw solver output](runs/v1-planted/solver.stdout.txt.gz). |
| Independent checked Sage replay | Valid curve, base masks, four torsion fibers and planted raw sum; no SAT model to replay | [Sage replay](runs/v1-planted/sage_replay.json), with [runtime receipt](runs/v1-planted/runtime-info.json). |
| Frozen ordinary target | NOT RUN | The protocol requires a verified planted SAT model first. |

The formula build took 0.473 seconds and the monitored solver process took
31.387 seconds on an unisolated ARM64 macOS host. CryptoMiniSat reported
23.87 seconds of its own search time and 100,002 conflicts. The observed
solver RSS poll peak was 74,268,672 bytes; the child-process peak was
109,838,336 bytes. These are exploratory stage costs only. The exact
[losslessly compressed XCNF input](runs/v1-planted/system.xcnf.gz) is retained with raw SHA-256
`2e2748a557e1ca7a1773ee14fedc910410db7bf2c1dda2ab076ae9c248fba877`.
The profile and actual run generated identical XCNF bytes. All measured
attempts, including this failure, remain in the receipt.

From the repository root, `python3
experiments/ecc2k130-w24-natural-pdp-20261005/selftest.py` checks the small
Boolean circuits. To independently replay the archived control, copy
`runs/v1-planted` to a fresh directory, remove only the copied
`sage_replay.json`, then run `./sage -python
experiments/ecc2k130-w24-natural-pdp-20261005/replay_sage.py --run-dir
/absolute/path/to/fresh-copy`. The replay checks the decompressed XCNF and
solver-log hashes without rewriting the archives. Every Sage invocation
uses the repository's checked launcher.

The first resource-limit preflight failed before formula construction:
macOS rejected lowering `RLIMIT_AS` to 4 GiB with `ValueError: current limit
exceeds maximum limit`. Before the planted SAT run, the implementation and
protocol were amended to check builder RSS during circuit construction and
poll solver RSS every 500 ms, killing the child above 4 GiB. The successful
monitor and its observed peak are in the run receipt. No CPU isolation or
performance-ratio claim follows from this host.

The next controlled diagnostic is to pin the known inverse and intermediate
values in a separate planted-only formula. A fast verified SAT answer would
show that the XCNF admits the known curve witness while leaving the
unconstrained search problem open. A failure would point to a circuit or
encoding defect. Neither outcome can be substituted for natural-query PDP
yield, useful relation rank, a recovered logarithm, or paired rho time.
Those values, and `candidate_id`, remain `null`.

The follow-up [planted-witness localization](DIAGNOSTIC_RESULT.md) produced
a Sage-verified SAT model with both witness classes pinned. Pinning only
inverses or only intermediates did not solve within the strict budget, so
neither class alone explains the original search failure.
