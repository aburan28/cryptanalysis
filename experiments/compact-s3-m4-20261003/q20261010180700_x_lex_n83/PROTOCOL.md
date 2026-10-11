# Q20261010180700: sorted-leaf N83 ordinary x-S3 screen

Use the exact Q1408 ordinary public point, N83 Koblitz curve, and fully
enumerated normal-x weight≤5 factor base (`B=30,977,592`, `K=186,612`).
Append `leaf[0] <= leaf[1] <= leaf[2] <= leaf[3]` to the archived balanced
four-leaf XCNF. Ordering uses the 83-bit normal-basis coordinate integer.
Every four-summand relation has a sorted representative because group
addition commutes and each balanced S3 link is symmetric in its leaves.

Freeze all input/source/binary hashes before formula construction. Validate
the comparator on every 3-bit pair, then append only its clauses/XOR rows;
preserve the original XCNF bytes below the updated header. Run one
CryptoMiniSat thread with seed zero, a 100,000-conflict cap, and a 300-second
external wall cap. Record child CPU, wall, RSS, streams, and solver status.
For a SAT model, verify the complete XCNF, exact projected factor base,
selected target lift, and signed full-point group relation. The ordinary
query has its existing `Wbab50a1e5f66` workload ID; this stage has a Q ID
and null IC candidate/run IDs. Timings on a shared host are exploratory.

Commands: `python3 experiment.py freeze`, `python3 experiment.py build`,
`python3 experiment.py solve`, `python3 audit.py`. Outputs refuse overwrite.
