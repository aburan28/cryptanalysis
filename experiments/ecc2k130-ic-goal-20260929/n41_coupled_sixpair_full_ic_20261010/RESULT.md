# A complete six-pair IC pipeline at N41

The coupled six-pair method now builds **26 verified factor-base logarithms**
from **26 rank-novel twelve-point relations** and recovers the logarithm of
an independently generated fresh subgroup point. Checked-Sage replay
confirms the relations, rank, every factor logarithm, fresh twelve-point
witness, and scalar `172371579945` by multiplication. This makes the two
shared seed-sum constraints an end-to-end IC method on the exact N41 control
curve. On that fresh point and a one-worker resource envelope, the warm IC
worker took `0.044740209` s online and signed-Frobenius rho took
`0.048941209` s online. The observed rho/IC ratio is `1.093897639`.
These single-run wall times are exploratory because this host has no
isolation receipt; the separate archived-point control has a different
search cost and is reported below.

## Exact method and identity

The canonical [candidate manifest](candidate_manifest.json) identifies
`IC1N41Ckb1fb384PDP12mitmRCsampleLAgaussTDdirectISO0hc329b35895b1`.
The [fresh one-target workload](fresh/canonical_workload.json) has ID
`a90ab6b621fe`; the complete run ID is the candidate ID followed by
`Wa90ab6b621feR1`. The archived-point control has a distinct
[workload identity](canonical_workload.json), `0d0eefaf4621`.
The canonical curve ID is `EC1N41Ckb1h023d9a38bbf7`. Older frozen stage
inputs used `EC1N41Ckb1h7d5e80d3c4d0` for the same exact curve; the
candidate manifest records this alias without changing the stage receipts.

The field is `GF(2^41)` with polynomial `t^41+t^3+1`; the curve is
`y^2+xy=x^3+1`, with order `4 * 549756390943`. The generator is
`(2056947637384,1635505394702)`, and the fresh point is
`(1544641481148,1238630537263)` in the prime-order subgroup. The six
W6 rotations are `0,5,10,15,20,25`. Their **384 distinct usable points**
fold to **26 signed-Frobenius columns** using eigenvalue `256851699273`.

Each rotation produces two-point sums with distinct columns. The first two
pair lists form a reusable four-point hash index of 3,167,136 entries. The
last four lists form two same-seed four-point domains of 51,840 states each.
The target query samples their product, subtracts the resulting eight-point
sum from the public target, and looks up the complementary four-point sum.
It checks all twelve columns and the exact group sum before combining the
prepared factor-base logarithms. The [warm worker](online_worker.cpp) reads
the public point only after constructing its index and loading the logs.

## Relation preparation and one-target result

The [frozen setup protocol](protocol.json) fixes 128 distinct SHA-256-derived
known-scalar points and stops at rank 26. The collector reached that rank in
the first 26 queries. All 26 producer witnesses passed the independent
[Sage audit](sage_audit.json), which also checked that each recovered
factor-base log multiplied by the generator equals its representative.
The observed relation yield was `26/26` and every row increased rank.
For the relation-yield count, the exact two-sided 95% binomial interval under
independent identical-query sampling is approximately `[0.868,1]`; the
frozen seeded stream and rank-dependent stop rule limit its use as a general
yield estimate.

| Preparation stage | Recorded result |
| --- | ---: |
| Actual base points / folded columns | 384 / 26 |
| Setup queries / verified relations / novel rows | 26 / 26 / 26 |
| Final rank / verified factor logs | 26 / 26 |
| Collection process wall, including repeated native setup | 87.873723 s |
| Sum of native setup intervals over setup queries | 49.697756 s |
| Sum of native query intervals over setup queries | 32.233678 s |
| Fresh run index setup, excluded from online interval | 1.199546 s |
| Fresh run peak RSS | 193,167,360 B |

The [fresh protocol](fresh/protocol.json) fixes one independently generated
point, one worker, 20 million accepted probes, 20 s native online cap, and
4 GiB RSS cap before target search. Its scalar, used only to construct the
fixture outside both clocks, was withheld from the IC and rho inputs. The
[native IC receipt](fresh/ic_native.json) records 59,042 accepted probes,
one group match, and an exact twelve-point witness. The
[fresh Sage audit](fresh/sage_audit.json) independently recovered the
same scalar from the witness and prepared logs, then reproduced the point.
That extra Sage relation and scalar check took `0.004063500` s outside the
native online interval; Sage process launch and field construction were
excluded from this supplementary check.

| Independent fresh target | IC | Same-point rho |
| --- | ---: | ---: |
| Target point | `(1544641481148,1238630537263)` | same |
| Verified scalar | `172371579945` | `172371579945` |
| Online wall | **0.044740209 s** | **0.048941209 s** |
| Search steps | 59,042 accepted probes | 59,996 walk steps |
| Peak RSS | 193,167,360 B | 8,470,528 B |
| Independent Sage scalar replay | PASS | PASS |

The five mutually exclusive IC online phases, in milliseconds, were target
query `0.010750`, target PDP `44.716375`, relation check `0.003209`,
target descent/log combination `0.000500`, and scalar recovery check
`0.009375`. They sum exactly to `44.740209` ms. Rho used one worker, 16
signed-Frobenius jumps, exact canonical-point collision matching, and no
distinguished-point table. Its target-dependent jump setup was `0.287333`
ms, walk and collision work `48.645251` ms, and scalar check `0.008625` ms;
those sum to `48.941209` ms. The [rho native receipt](fresh/rho_native.json)
and [independent Sage audit](fresh/sage_audit.json) bind it to the same point.
The [fresh paired record](fresh/paired_comparison.json) retains the candidate and
workload identities, caps, failures, five phase values, and source hashes.
The cold total and operation-count ratio remain `null` because every cold
phase was not separately priced. An isolated-host timing result remains a
separate gate for a promoted CPU speedup statement.

The exact native curve helper and rho source are retained as local snapshots.
The [rebuild and replay receipt](build_replay.json) rebuilt IC and rho from
those snapshots, reproduced both frozen IC witnesses, and recovered the
same fresh rho scalar and walk-step count. The rebuilt warm worker and rho
binaries matched their measured binaries byte for byte; the rebuilt setup
collector produced the identical archived witness. The offline
[integrity checker](verify_receipts.py) recomputes the candidate and workload
IDs, source hashes, base digest, phase sums, and paired receipt links.

The earlier archived public point supplied a separate reproducibility
control. It took 730,852 accepted probes and `0.862369917` s IC online;
same-point rho took `0.093749000` s. Both recovered scalar `12172994855`
with independent Sage replay. The [archived-point pair](paired_comparison.json)
has its own workload ID and remains a separate one-target run. Its
[supplementary Sage replay](supplemental_replay.json) took `0.169766` s
outside its native online interval. The wide difference in observed probe
counts and timings motivates an independent yield distribution study before
estimating expected online cost.

## Consequence for the N131 challenge

The N41 test establishes that the two seed equalities preserve enough
ordinary relations to solve the 26-column log system and that native target
recovery works from a previously unseen point. The direct four-point index
does not transfer within the N131 4 GiB bound: the [N131 coupled formula
study](../n131_w14_coupled_sixpair_sat_20261010/RESULT.md) bounds its explicit
index above that memory limit by a factor of at least 4,399. The native
[N131 four-atom inverse](../n131_w14_coupled_fouratom_inverse_20261010/RESULT.md)
can test one proposed partial output in 7.496–9.722 s with under 2 MiB RSS.
The next algorithmic gate is to generate those partial outputs from the
*public target constraint* without enumerating the index. Test that generator
on the unpinned N41 point, counting all proposals, inverse calls, group
replays, verified relations, rank increments, wall time, and RSS. Then use
the frozen N131 point and its 600 s / 4 GiB bound for the first full-width
query. This gate directly measures whether the inverse can replace the
memory-heavy index at a useful relation rate.
