# One exact m6 circuit searches all four ECC2K-130 target lifts

The equal-size source W24 and normal-weight-four policies now each have a
single native-XOR m6 formula whose two-bit target mux covers all four raw
preimages of the frozen projected ordinary query within the finite-intermediate
S3 chart. Checked Sage reproduced
the four points and their common `[4]` projection; eight pinned
CryptoMiniSat controls accepted the expected mux outputs and rejected a
one-bit change for every choice. Both ordinary-query attempts reached
substantial search and returned `BOUNDED_UNKNOWN` at the internal time
limit. The exact W24 prefix orbit audit also fixes its potential relation
column count at **5,869,878**, compared with **44,824** for normal4 at the
same actual `B=11,743,888` factor-base points.

## Frozen query and implementation

The [protocol](PROTOCOL.md) fixes public ordinary query index zero from the
[equal-B input gate](../ecc2k130-normal4-equalb-m6-20261010/RESULT.md),
source curve `EC1N131Ckb1h136f03e58c98`, one worker, a 150-second external
wall guard, 4 GiB RSS guard, and CryptoMiniSat 5.14.7 with native XORs and
`--maxtime=120`. The four x coordinates come from the parent
[order-four torsion receipt](../ecc2k130-equalb-m6-leaf-circuit-20261010/runs/R1/torsion_lifts.json):
`Q+j(1,1)` for `j=0..3`. This is one ordinary public query with four raw
lifts, not four target workloads. Its fixture scalar is absent from both
formulas. The parent leaf membership and five-link S3 program are imported
unchanged; only the first-link target input becomes the exact two-bit mux.
The [Sage replay](runs/R1/sage_lifts.json) returned
`PASS_INDEPENDENT_FOUR_RAW_LIFTS`. The
[mux controls](runs/R1/mux_controls/receipt.json) returned four SAT and four
UNSAT results under the pinned solver binary SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`.

| Equal-B source policy | XCNF vars | Ordinary clauses | Native XORs | Raw formula SHA-256 |
| --- | ---: | ---: | ---: | --- |
| W24 | 337,239 | 340,321 | 222,301 | `f951e3bfb569b27f371fadb4f59ec8f73bbb278ed2777cd1bc65a1f540b5abee` |
| Normal4 | 537,713 | 600,119 | 301,862 | `ec56ac8b7b91fc99d4cd62214b545bde52197981ad3cc64ec8a4f7f0759f1c46` |

Each all-lift formula has 8,291 more variables, 13,899 more ordinary clauses,
and 3,656 more native XORs than its [fixed-lift parent](../ecc2k130-equalb-m6-leaf-circuit-20261010/RESULT.md).
The variable target removes first-link constant folding, so this increase
includes first-link arithmetic, not just mux gates. Deterministic gzip
archives retain the byte-identical raw [W24](runs/R1/w24_m6_four_lift.xcnf.gz)
and [normal4](runs/R1/normal4_m6_four_lift.xcnf.gz) XCNFs; the
[archive receipts](runs/R1/w24_m6_four_lift.archive.json) bind their raw
and compressed hashes.

## Ordinary-query search and column geometry

| Policy | Solver status | Formula build s | Solver wall s | Build + solver s | Peak observed solver RSS | Search conflicts | Restarts | Verified relations | Novel rank |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| W24 | `BOUNDED_UNKNOWN` | 4.944 | 148.760 | 153.703 | 321,503,232 B | 535,298 | 1,014 | 0 | unknown |
| Normal4 | `BOUNDED_UNKNOWN` | 9.368 | 132.012 | 141.380 | 433,111,040 B | 618,336 | 1,175 | 0 | unknown |

Both solver processes returned exit code 15 and `s INDETERMINATE` after
search under the internal `--maxtime` limit; the external guard did not
trigger. The [W24](runs/R1/w24_m6_four_lift_pilot.json) and
[normal4](runs/R1/normal4_m6_four_lift_pilot.json) receipts retain the exact
command, source/binary/formula hashes, stdout, stderr, wall and RSS. The
independent [W24](runs/R1/w24_m6_four_lift_audit.json) and
[normal4](runs/R1/normal4_m6_four_lift_audit.json) audits checked those
hashes, status lines, limits, positive conflict and restart counts, and
actual search progress. These are censored solver outcomes on an unisolated
host; they provide no measured natural relation-yield rate or paired CPU
speed ratio. The earlier fixed-`j=0` attempts were also `BOUNDED_UNKNOWN`
at their cap; they did not charge or search the other three lifts.
The build intervals start inside the target-dependent formula builder. The
build-plus-solver sums are stage diagnostics for this query, not complete
single-target online times: the four raw lifts were prepared before these
intervals, and query generation, any transport, relation checking, matrix
work, target descent, and recovery are not charged here. A later full
pipeline run must charge target-dependent lift generation and every failed
attempt to the same query before comparing one-target online intervals.

The [prefix-column receipt](runs/R1/columns.json) restricts the previously
verified full W24 Frobenius component map to this frozen prefix. All 4,104
nontrivial full-base masks occur before the new cutoff `11,740,931`, in
2,038 nontrivial components. Exactly 2,066 of 5,871,944 sign-only source
columns are saved, leaving **5,869,878 potential columns**. Normal4's
frozen 44,824 rational Frobenius orbits give **44,824 potential columns**
for the same `B`; W24 has `130.9539086203819...` times as many. These
counts price only possible log variables. Actual relation-matrix columns,
rank, sparse LA memory, and the cost of recognizing transported orbits
require their own pipeline receipts. The independently checked parent map
found zero reciprocal overlaps, and the new receipt binds its map,
verifier, input prefix, and source hashes.

## Decision and next experiment

The next solver comparison should prioritize normal4's much smaller
potential matrix while treating its larger SAT formula and censored search
as real obstacles. A target-first or balanced-S3 variant should be frozen
against this same four-lift query, keep the exact normal4 base and a W24
control, and pass a planted signed point-chain replay before ordinary
search. The first useful promotion gate is a verified ordinary relation
and novel row per **charged query**; the 16/256-query prefix and final
matrix follow only if that gate produces enough uncensored results. A
complete PDP must also handle the finite-chain exceptional branches noted
in the protocol. The source-to-descendant transported policies share
group-sum membership, but their map, recognition, and coordinate-solver
costs remain separate; no native-descendant PDP ran here.

`candidate_id` remains `null`. The one-target online IC interval, complete
factor-log matrix, target descent, and same-point rho interval are not
defined by this solver gate. The R1 [manifest](runs/R1/manifest.json)
verifies all committed source, frozen inputs, controls, formulas, and raw
search receipts.

Reproduce the stage from a full checkout with the checked repository Sage
launcher and fresh output paths. The `--evidence-root` override for
`compute_columns.py` is only needed in a sparse checkout that omits the
already committed full-orbit artifacts.

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /tmp/equalb-four-lift-runtime.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/ecc2k130-equalb-four-lift-pdp-20261010/verify_lifts_sage.py --runtime-info /tmp/equalb-four-lift-runtime.json --out /tmp/equalb-four-lift-sage.json
python3 experiments/ecc2k130-equalb-four-lift-pdp-20261010/compute_columns.py --out /tmp/equalb-four-lift-columns.json
python3 experiments/ecc2k130-equalb-four-lift-pdp-20261010/archive_formulas.py --run-dir experiments/ecc2k130-equalb-four-lift-pdp-20261010/runs/R1 --verify
python3 experiments/ecc2k130-equalb-four-lift-pdp-20261010/manifest.py --verify
```
