# Q1477: one-step selector lookahead has identical root work on both N83 points

An in-process probe of both signs of target-preimage selector 2140 made
**exactly two CNF calls, two XOR calls, one CNF assignment, and one XOR
assignment per sign** on each of two ordinary N83 points. Both signs were
consistent; the breakpoint/undo check restored the original assignment
counts and selector state after each probe.
The selected point had favored the 2140 flip at `2^18` branches; the unseen
holdout had favored phase 0. Thus a one-step root propagation or assignment
score supplies no preference on the two points with opposite deeper
rankings.

| Input | Root literal -2140 | Root literal +2140 | Cheaper polarity at 2^18 branches |
| --- | --- | --- | --- |
| Native-XOR satisfiable control | 2 CNF / 2 XOR calls; 1 / 1 assignments | same | control only |
| Ordinary selected point `2eb250a29072` | same | same | flip 2140 |
| Ordinary holdout `394256b9f901` | same | same | phase 0 |

The exact curve is `EC1N83Ckb1h876c2921cb64`, actual usable factor base
`B=30,977,592`, folded columns `K=186,612`, stage `PDP4sat`, and
`isogeny: "none"`. Q1477 is a stage proposal with null candidate and run
IDs. The [protocol](protocol.json) and [freeze](freeze.json) bind the two
previously frozen ordinary width-four XCNFs, exact workload IDs, the
Q1473-pinned WDSat source and satisfiable control, and the root-probe patch.
The [build receipt](build_receipt.json) records the patched C source and
binary hashes. The patch evaluates both signs with WDSat's existing
breakpoint/undo mechanism and checks the original CNF and XOR assignment
counts and selector state after each rollback. It exits before DFS.

The three runs returned `ROOT_PROBES_RESTORED`; the [validator](validate.py)
reconstructed the exact C patch, checked binary/input/output hashes and
both probe rows, and verified the rollback and exit markers. The ordinary
runs used 0.270 and 0.259 solver user CPU seconds and 6.537 and 5.988
exploratory wall seconds, respectively. Cumulative child peak RSS reached
896,876,544 bytes (855.328 MiB). Host wall and CPU times have no isolation
receipt. The root call and assignment counts are exact diagnostic work,
with the probe's own calls charged in the instrumented final counters.

The [analysis](analysis.json) records a null root preference for both
predeclared scores: fewer CNF/XOR calls and more CNF/XOR assignments.
Neither input entered deeper solver search in Q1477, so completed ordinary
decomposition work, natural relation yield, normalized N131 one-target
work, and the comparable gap to `2^61` remain null. The separate Q1462
conditional N131 weight-seven pair-index model remains `2^86.1847`
counted pair additions, 25.1847 bits above an abstract `2^61`
pair-addition reference in its different unit.

This result redirects method work to the existing exact balanced-\(S_3\)
root oracle: when leaf x coordinates become fixed, compute and constrain
the possible pair-intermediate roots without expanding the full Boolean
root circuit or building the complete quotient-pair table. The first gates
are the archived N53/N83 `free_mids` controls, followed by ordinary N53
and N83 relations with independent group and rank replay. Further static
selector tuning needs a precommitted target panel and a charged
distribution-level result.

Revalidate locally with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n83_root_lookahead/validate.py
```
