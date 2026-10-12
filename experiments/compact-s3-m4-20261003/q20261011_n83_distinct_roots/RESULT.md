# Q1479: 32,437 root-ready N83 snapshots contain one distinct leaf pair

The Q1478 first-leaf-pair search reaches an S3-root-checkable state often,
but its first 32,768 branches revisit **one distinct pair of leaf x
coordinates** on each of two ordinary N83 public points. The 32,437
snapshots with pair 1 complete and its middle coordinate still free consist
of one first occurrence and **32,436 repeats**. The pair is identical on
both points, with leaf weights one and one. Its exact S3 equation has two
middle-coordinate roots, so this prefix offers **zero rootless-pair
rejections**. One charged root query uses 142 `CountedOnb` public field
method entries, including coordinate conversion and the oracle's internal
checks.

| Workload ID | Root-ready pair-1 snapshots | Distinct captured pairs | Repeats | Exact roots | Counted field API entries | Search status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2eb250a29072` | 32,437 | 1 | 32,436 | 2 | 142 | `CHECKPOINT_TERMINATED` at 32,768 branches |
| `394256b9f901` | 32,437 | 1 | 32,436 | 2 | 142 | `CHECKPOINT_TERMINATED` at 32,768 branches |

The [sample rule](protocol.json) captured the first 256 distinct complete
pair-1 coordinate bitstrings while its middle row retained an unassigned
bit. Neither point reached that sample cap; the unique count of one is exact
over the declared prefix, not a truncated estimate. The [captured bits and
roots](root_samples.json) and [analysis](analysis.json) retain each outcome
and operation vector. Every Q1479 branch-ready and CNF/XOR propagation
checkpoint equals its Q1478 counterpart exactly, confirming that logging
did not change the measured solver path. The same pair on both points is
consistent with the shared formula structure and branch order before
target-specific constraints affect this prefix.

## Exact instance and replay

Both ordinary inputs use curve `EC1N83Ckb1h876c2921cb64`, actual usable
normal-basis weight-five factor base `B=30,977,592`, signed-Frobenius
folded `K=186,612` columns, `PDP4sat`, and `isogeny: "none"`. Q1479 is a
point-decomposition stage proposal with null candidate and run IDs. The
[freeze](freeze.json) binds the two public points, XCNFs, Q1478 instrumented
source, exact field/oracle implementations, and sample cap before the run.
The [source patch](build.py) records pair bits only when all 166 leaf bits
are assigned and the corresponding midpoint has an unassigned bit. It
deduplicates by the complete bitstring and stops capturing after the common
branch checkpoint.

[Validation](validate.py) reconstructs the C patch, checks the binary,
inputs, raw logs, sample sequence, Q1478 checkpoint equality, and the
quadratic root count. It re-evaluates every returned root in the S3
polynomial. The two new bounded attempts add 14.089 exploratory solver
wall seconds and 1.473 child user CPU seconds across the two public points;
the host has no isolation receipt. Both attempts are charged to their
respective points. Q1478's full-lock control already checked that the
parent solver's assignment satisfies the original and transformed XCNFs.

## Work distance and next parameter

This prefix's repeated pair gives little diversity for an exact root
callback. The two roots can constrain the free midpoint, but Q1479 does
not measure whether that constraint adds pruning beyond native-XOR
propagation. Natural relation yield, rank novelty, complete N83
decomposition cost, and normalized N131 one-target work remain null. The
separate Q1462 conditional weight-seven pair-index model is `2^86.1847`
counted pair additions, 25.1847 bits above an abstract `2^61`
pair-addition cap under its sampled-base and rank assumptions; it uses a
different operation unit.

The next branch-parameter sweep should vary first-branch polarity or leaf
bit order at a **fixed propagation-call budget**, then count distinct
root-queryable pairs, rootless pairs, and their charged exact-root work on
both public points. A policy that only increases repeated snapshots will
not pay for the extra propagation measured by Q1478. After choosing a
policy on one point, its ranking needs an unseen-point check before a
longer ordinary relation search.

Reproduce the source, input, counter, and root checks with:

```sh
env TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261011_n83_distinct_roots/validate.py
```
