# Q1478: leaf-first WDSat exposes exact S3 root checks on two N83 points

Moving the first 166 leaf bits ahead of the two target selectors and the
middle bits makes complete leaf pairs visible in native-XOR WDSat search.
At a common 32,768-left-branch checkpoint, the current midpoint-first
order exposed **zero** complete leaf-pair snapshots on either ordinary N83
point. The first-leaf-pair order exposed **32,604** snapshots with pair 0
complete and **32,437** with pair 1 complete; pair 1's middle coordinate
still had an unassigned bit in all 32,437. The first nonzero complete-pair
checkpoint was 256 branches on both points. This gives the already
implemented exact S3 oracle a concrete insertion point in the native-XOR
search.

| Ordinary workload | Branch order | Complete pair 0 / pair 1 snapshots | Pair 1 with free middle | CNF calls | XOR calls | Combined calls (`2^x`) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `2eb250a29072` | midpoint first | 0 / 0 | 0 | 9,618,398 | 10,631,934 | 20,250,332 (`2^24.271`) |
| `2eb250a29072` | first leaf pair | 32,604 / 32,437 | 32,437 | 13,950,750 | 13,909,476 | 27,860,226 (`2^24.732`) |
| `394256b9f901` | midpoint first | 0 / 0 | 0 | 6,965,073 | 8,102,342 | 15,067,415 (`2^23.845`) |
| `394256b9f901` | first leaf pair | 32,604 / 32,437 | 32,437 | 13,043,998 | 13,001,555 | 26,045,553 (`2^24.635`) |

The first-leaf-pair order costs **1.376×** and **1.729×** as many combined
CNF/XOR propagation calls on the selected and holdout points, respectively,
at this checkpoint. CNF and XOR calls remain separate internal operations;
their sum is an explicitly labeled diagnostic count, not calibrated field
operations. The `2^x` values in the table describe work already spent by
each capped search. The snapshots may revisit the same leaf pair, so they
are not distinct S3-root queries or relation yield.

## Frozen method and accounting

Both points use curve `EC1N83Ckb1h876c2921cb64`, exact normal-basis
weight-five factor base `B=30,977,592` usable subgroup points, signed-
Frobenius folded `K=186,612` columns, `PDP4sat`, and `isogeny: "none"`.
Q1478 is a point-decomposition stage proposal with null candidate and run
IDs. The [protocol](protocol.json) and [freeze](freeze.json) bind the two
previously frozen ordinary XCNFs, public targets, pinned Q1473 WDSat
source, comparison orders, and caps. The [build script](build.py) changes
only branch priority and adds assignment-state counters before each counted
left branch. A leaf pair is ready when all 166 of its coordinate bits are
assigned. A free middle means at least one of its 83 bits is unassigned.
The original native-XOR formula and solver propagation are retained.

The exact full-lock N83 control returned a model; [validation](validate.py)
independently evaluated that assignment against both the original and
width-four XCNFs. All four ordinary cells reached the 32,768-branch marker
and were terminated after its complete counter record. Their status is
`CHECKPOINT_TERMINATED`. Q1478 adds two attempts and 17.220 exploratory
solver wall seconds to `2eb250a29072`, and two attempts and 15.682 seconds
to `394256b9f901`; previous attempts on each point remain separately
charged in Q1475–Q1477. The full-lock control used 11.337 child CPU
seconds and 171.374 wall seconds on this contended host, illustrating why
the wall values are descriptive. There is no host-isolation receipt.

## Distance to the degree-131 challenge

The four bounded searches did not produce an ordinary relation. Distinct
root-query count, rootless fraction, natural relation yield, novel rank,
complete N83 decomposition cost, and the normalized N131 one-target `2^x`
estimate therefore remain null in [analysis.json](analysis.json). The
separate Q1462 conditional weight-seven full pair-index model is
`2^86.1847` counted pair additions, **25.1847 bits** above an abstract
`2^61` pair-addition reference under its sampled-base and rank assumptions.
That unit and method differ from Q1478's propagation counters.

The next measured step is to capture a bounded sample of **distinct**
complete leaf pairs from this leaf-first order, replay their exact S3 roots
with Q1430's oracle, and count rootless pairs and root-query cost. This
will determine whether the new branch order exposes enough exact pruning
to repay its extra propagation work before adding the oracle to WDSat.
An independently checked ordinary relation and rank contribution remain
the gate for fitting a complete N131 work exponent.

Reproduce the source, build, model, input, and raw-log checks with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n83_leaf_exposure/validate.py
```
