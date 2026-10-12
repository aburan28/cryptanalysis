# Q1431: short S3 root guards and positive-first leaf search

Q1431 reduces the clauses added by the in-search S3 root solver and measures
which leaf decisions expose more exact roots on the frozen N53 and N83
ordinary queries. The strongest representation result is on N83: at 5,000
conflicts, `satpivot` uses **66,377 external literals** for the same 81
pair-root queries that need **1,288,326** with Q1430's full-assignment
guards, a 19.4-fold reduction. Both runs find the same 34 rootless pairs.
Positive-first leaf branching reaches 3,015 root queries, including 1,469
rootless pairs, in a longer bounded N83 run. Every ordinary cell remains
`BOUNDED_UNKNOWN` under its stated cap.

## Method and correctness

For a leaf constrained to normal-basis weight at most `k`, an assigned leaf
with exactly `k` positive bits is determined by those bits: any satisfying
extension must set every other bit to zero. Q1431 therefore guards the root
clauses with only the `k` positive literals for a saturated leaf. It retains
the complete assignment guard for a leaf of smaller weight. `satpivot` also
uses one differing middle-coordinate bit as the choice between two S3 roots;
`satlegacy` keeps Q1430's explicit root selector. The `shared` alternative
introduces one guard variable per nonempty pair-root query, and `pivot`
tests the middle-bit choice with complete leaf guards.

The short-guard rule requires the exact at-most-weight clauses already
present in the frozen formulas. `validate_equivalence.py` adds those clauses
at degree 11 and exhaustively checks all 2,048 possible middle coordinates
for pairs with zero, one, and two S3 roots. All five encodings agree with the
exhaustive field result on six fixed instances. Every archived known-solution
control at N53 and N83 solved with zero conflicts under all five encodings;
independent field replay matched its four leaf x coordinates and both S3
middle roots. The original three S3 links stay in the CNF throughout.

## Frozen ordinary inputs

| Degree | Curve ID | Workload ID | Weight bound | Actual usable `B` | Folded `K` | Input XCNF SHA-256 |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | `74f2979b3e68` | 3 | 24,062 | 227 | `62b5e4a47454c2cb08c716bc4b0eef51f0d1149dce61998e1ef8ddba1f008156` |
| 83 | `EC1N83Ckb1h876c2921cb64` | `bab50a1e5f66` | 5 | 30,977,592 | 186,612 | `ead520f8acf5509e37392ca71a5ee31de382fe1450e7e1ae63c0392cd9c0723b` |

Q1430's `prepare.py` rebuilds and verifies those XCNFs byte for byte before
lowering their native XOR rows. Q1431 changes only the external S3 clauses
and decision policy. The curve, public point, raw target-preimage coset,
factor base, and balanced four-leaf tree remain fixed within each degree.
`isogeny` is `"none"` (`ISO0`). The complete IC candidate and run IDs remain
null for this point-decomposition proposal.

## Matched encoding screen

These are ordinary queries with CaDiCaL's own branching, one thread, a
5,000-conflict cap, and a 60-second solver wall cap. The interval starts at
`solve()` after CNF parsing and oracle construction; CPU seconds cover that
same interval. The host had no isolation receipt, so timing differences are
exploratory. `external_literals` and `external_clauses` count exactly what
the callback submitted to CaDiCaL.

| Degree | Encoding | Conflicts | Root queries | Saturated leaves / leaves seen | External clauses | External literals | Solver CPU s | Peak RSS MiB |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 53 | legacy | 5,001 | 2 | 4/4 | 106 | 11,342 | 1.20 | 189 |
| 53 | pivot | 5,001 | 2 | 4/4 | 106 | 11,342 | 1.19 | 190 |
| 53 | shared | 5,001 | 2 | 4/4 | 320 | 850 | 1.35 | 179 |
| 53 | satpivot | 5,001 | 2 | 4/4 | 106 | 742 | 1.14 | 194 |
| 53 | satlegacy | 5,001 | 2 | 4/4 | 106 | 742 | 1.24 | 191 |
| 83 | legacy | 5,000 | 81 | 161/162 | 7,670 | 1,288,326 | 3.64 | 344 |
| 83 | pivot | 5,002 | 81 | 161/162 | 5,701 | 955,655 | 3.83 | 333 |
| 83 | shared | 5,000 | 81 | 161/162 | 13,550 | 44,053 | 3.55 | 312 |
| 83 | satpivot | 5,000 | 81 | 161/162 | 5,701 | 66,377 | 3.46 | 316 |
| 83 | satlegacy | 5,001 | 81 | 161/162 | 7,670 | 91,884 | 3.40 | 308 |

The clause reduction is exact. At this cap the ordinary search visits the
same 81 N83 pairs in every encoding, and no row produces a model. On the
unguided N83 path, extending `satpivot` to 30,001 conflicts still visits
only those 81 pairs. The next search change therefore targets pair exposure
and final-link pruning rather than another local clause-layout tweak.

## Branch-order screen

`allpos` selects positive bits in order on all four leaves. `alloffset`
starts each leaf one quarter of the basis apart, `allstride` visits bits
with stride 13, and `allspread` combines both changes. Every row below uses
`satpivot`, the same N83 ordinary point, and a 5,000-conflict or 60-second
wall cap, whichever occurs first.

| Policy | End | Conflicts | Root queries | Rootless pairs | Solver CPU s |
| --- | --- | ---: | ---: | ---: | ---: |
| allpos | wall 60 s | 1,843 | 191 | 91 | 7.95 |
| alloffset | wall 60 s | 1,969 | 60 | 23 | 7.96 |
| allstride | wall 60 s | 3,406 | 214 | 97 | 18.50 |
| allspread | wall 60 s | 2,032 | 81 | 44 | 8.42 |

At the common 1,000-conflict cap, the four policies produce two, five, two,
and three root queries respectively; the raw rows are retained. `allpos`
has the highest root queries per conflict in the 60-second screen. Two
separate 120-second N83 runs show how much the contended host varies: one
reaches 377 queries at 2,593 conflicts using 15.93 process CPU seconds;
the other reaches 3,015 queries at 13,415 conflicts using 96.11 process
CPU seconds. Their rootless-pair counts are 183 and 1,469. The N53
counterpart reaches seven queries at 16,464 conflicts before its 120-second
wall cap. An unguided N83 `satpivot` replay reaches 30,001 conflicts and
still sees only its initial 81 pair roots. None of these bounded rows
returns a complete model.

## Matched pair-table reference

The existing pair-table receipts use the same curve, public point, workload
ID, actual base size, and enumerated-set digest as the corresponding Q1431
rows. Their table descriptors, target pair queries, and SAT conflicts are
different work units; the rows below retain those units explicitly.

| Degree | Pair-table receipt | Table descriptors | Target pair queries | Result at cap |
| ---: | --- | ---: | ---: | --- |
| 53 | [Q1301](../runs/n53_ordinary_matched_pair_table.json) | 500,000 | 171,218 | One independently verified four-point relation |
| 83 | [Q1400](../runs/n83_q1400_pair_comparator.json) | 2,000,000 | 2,719,744 | No exact hit under the bounded schedule |

Q1301 records 32.78 seconds of base setup, 41.69 seconds of table work, and
22.34 seconds of target pair queries on its original exploratory host. Q1400
records 0.41 seconds of native table building and 0.63 seconds of target
queries for its capped schedule. These phase times are preserved as stage
measurements; neither receipt supplies a controlled wall ratio against the
Q1431 SAT runs. `verify_pair_reference.py` independently replayed Q1301's
four-point sum and found a weight-three raw preimage under the exact
cofactor-428 map for each projected factor-base point; the replay receipt is
`pair_reference_replay.json`. The N53 pair table supplies a concrete natural
relation baseline that Q1431 has not yet reached. The N83 pair table
establishes a matched bounded comparator on the much larger Q1325 base.

## Work ledger and next gate

The external-literal reduction is a measured solver-operation improvement,
and the branch screen identifies a stronger pair-exposure policy. Neither
number is a cost per useful relation. `measurements.json` keeps natural
relation yield, rank novelty, field operations per completed decomposition,
the fully charged N131 `2^x` projection, and its gap to `2^61` as null.
The frozen N83 base and curve IDs are carried into every row; a completed
ordinary relation must still be independently checked against actual base
points and tested for novel matrix rank before those fields can be filled.

The next experiment should add an exact S3 check for the final link as soon
as both middle coordinates are assigned, using the frozen raw target-x coset
to reject incompatible leaf quartets before a complete SAT model. That is
the remaining compact link in the balanced tree. Compare it with `allpos`
and `satpivot` on the same public N83 point, retain all bounded attempts,
and charge successful natural relations and rank into the complete
single-target work ledger.

## Reproduction

From the repository root, generate the Q1430 CNF and map, then build the
Q1431 solver:

```sh
python3 experiments/compact-s3-m4-20261003/q20261010_insearch_root/prepare.py \
  --degree 83 --mode ordinary --output-prefix /private/tmp/q1431_n83
sh experiments/compact-s3-m4-20261003/q20261010_compact_guard/build.sh \
  /private/tmp/q1431_insearch
```

Call the executable with `CNF MAP S3_MODULE_DIR FIELD_MODULE_DIR BRANCH_POLICY
ROOT_ENCODING WEIGHT_BOUND CONFLICT_CAP WALL_SECONDS`; use weight bound 3
for the frozen N53 input and 5 for N83. `measurements.json` records the
source, binary, input, raw-log, and verification hashes needed to replay the
table. `validate_equivalence.py --binary /private/tmp/q1431_insearch` checks
the root encodings independently at degree 11.

For example, the N83 `satpivot` 5,000-conflict row uses:

```sh
/private/tmp/q1431_insearch /private/tmp/q1431_n83.cnf \
  /private/tmp/q1431_n83.map \
  experiments/compact-s3-m4-20261003 ecc2k130/codegen \
  none satpivot 5 5000 60
```
