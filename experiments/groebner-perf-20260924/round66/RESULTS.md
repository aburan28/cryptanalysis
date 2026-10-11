# Constant-identity kernel: exploratory result

The prepared-witness kernel passes 6,480 controls in each of the optimized and
UBSan builds. It preserves acceptance, the first failing coefficient feature
and exact avoided-parity accounting for every case. The same allocation is
reused with fresh witnesses and changed symmetry masks between controls.

A separate panel reconstructs the coefficient table from the original packed
ANF and checks the constant witness prefix from round65's independently audited
proof. All 270 optimized and 270 UBSan kernel records pass. There are 30
observations per arm/case, with all six arm orders repeated five times.
Fresh witness preparation is charged. Table reconstruction, initial allocation,
the remaining certificate and curve checks are outside this kernel interval.
This panel performs no symmetry skips, so it is not the round65 complete query.

| Frozen fixture | Original median (ms) | Prepared built-in parity (ms) | Prepared XOR-fold parity (ms) |
| --- | ---: | ---: | ---: |
| n31-m3-ell6-seed101 | 0.0323 | 0.0153 | 0.0271 |
| n31-m3-ell8-seed201 | 0.8711 | 0.4044 | 0.7248 |
| n31-m3-ell9-seed201 | 4.3383 | 2.0136 | 3.5791 |

These ordinary-host kernel timings are exploratory. There is no host-isolation
receipt, no full-query comparison and no promotion to production. Aggregate
speedup remains unknown. The built-in-parity variant is the next integration
candidate; the full query must retain the same identities, rejection behavior,
proof/equation checks, allocation bounds and charged timing interval.

`results/` retains every record, ordered plan, source/binary receipt, frozen
kernel inputs and the earlier setup failure. The failed v2 attempt misread the
ANF schema and was rejected by integer serialization before timing began; it
has zero measured rows. The corrected source is recorded in the final report.
All bound executable sources match committed Git blobs. No archived binary
must be reused on a different platform; rebuild with `build.py`.

To replay correctness, build and run `build/test-constant` and
`build/test-constant-ubsan`. For the frozen kernel panel, decompress a retained
`.bin.gz` input and pass its path to `build/bench-constant` and
`build/bench-constant-ubsan`. Input SHA-256 values are in `plan.json.gz`.
`run_diagnostic.py` regenerates those inputs when given the full round65
`correctness.json.gz` artifact. The report retains raw per-observation times;
its medians are not controlled CPU speedup claims or IC/rho results.
