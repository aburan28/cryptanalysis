# Producer budget attribution

Round96 exposes the packed F4 producer's existing matrix, pair-pruning and
allocation counters, and adds diagnostic scopes that partition its unchanged
logical work budget. The baseline and instrumented producer run through the
same round95 complete-query boundary and independent checker.

All 184 frozen calls passed the native-free audit, including 92 exact paired
traces, unsuccessful attempts, and 40 solved planted PDP calls. Profiles agree
across optimized/UBSan builds and reversed execution order. There is no timing
speedup claim or dispatch change.

- [Protocol and counter interpretation](PROTOCOL.md)
- [Results and next implementation target](RESULTS.md)
- [All 23 profiles](summary.json)
- [Lossless evidence archive](results.tar.gz) and [custody receipt](archive.json)

The observed work distribution differs across fixtures. Nine-variable PDP
controls spend most of the logical budget in packed elimination. Twelve-variable
controls spend more in normal reduction, with substantial ordered-row merging.
These budget shares do not measure CPU time. They support testing bounded
scratch reuse in normal reduction while retaining the complete query and exact
certificate boundary.
