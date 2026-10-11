# Q20261010183500: ordinary N53 x-weight-four balanced S3

Measure one ordinary query on Q1410's public point and workload
`W74f2979b3e68`, changing only the factor-base bound from normal-x
weight≤3 to weight≤4. Q20261010182800 provides the exact projected
weight-four base: `B=324,042`, `K=3,057`, and a packed-key digest. Build
the same balanced three-S3 tree with four free leaves and two free
intermediate x coordinates; do not expand S5. Check a rebuilt weight-three
formula against Q1410's archived raw XCNF before constructing weight four.

Freeze source, exact base, public point, target preimage coset, solver
binary, seed, conflict limit, and wall cap before execution. Use one
CryptoMiniSat thread, seed zero, at most 1,000,000 conflicts, and an
external 1,200-second wall cap. Verify any SAT model against serialized
native-XOR XCNF, four nonzero weight≤4 leaves, the exact factor base, and
the signed full-point relation. Record solver CPU/wall/RSS, formula shape,
stream digests, and model status. A conflict or wall limit without a model
is `BOUNDED_UNKNOWN`. Shared-host wall timings are exploratory.

This is a Q-stage point-decomposition measurement with null IC candidate
and run IDs, `ISO0`, and no inferred natural yield from capped attempts.
Commands: `python3 experiment.py freeze`, `python3 experiment.py prepare`,
`python3 experiment.py solve`, `python3 audit.py`. Outputs refuse overwrite.
