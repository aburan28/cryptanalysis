# One active Gaussian XOR matrix on the frozen N83 width-18 formula

CryptoMiniSat's default settings rejected all six recovered XOR
components in the width-18 S3 formula: the smallest was about 3,868
rows by 4,034 columns, above its default 2,000-row and 1,000-column
matrix limits. Raising those limits to 4,096 and admitting one matrix
activates Gaussian elimination on the **identical archived XCNF**.
The [preflight output](preflight.stdout.txt) and each tuned pilot arm
report one active matrix. The [locked relation control](karatsuba_control.json)
returns SAT and passes group replay with this solver setting.

The [Q62 protocol](protocol.json) freezes the exact width-18 base,
`df4396f4d8fc` public workload, one CryptoMiniSat thread,
300,000-conflict cap, 120-second wall cap per arm and 4 GiB sampled
RSS stop. The base has **B = 21,714,958 usable subgroup points before
folding** and **K = 130,813 signed-Frobenius columns**. Only the solver
matrix thresholds change.

| ABBA arm | Solver | Seconds to conflict cap | Reported conflicts | Sampled peak RSS |
| ---: | --- | ---: | ---: | ---: |
| 0 | Default | 49.631 | 300,002 | 83,968,000 B |
| 1 | One matrix | 33.502 | 300,001 | 94,486,528 B |
| 2 | One matrix | 39.526 | 300,001 | 94,568,448 B |
| 3 | Default | 39.245 | 300,002 | 85,491,712 B |

All arms returned capped `INDETERMINATE`; the wrapper records exit
code 15 as `solver_failure`, and the [pilot](pilot_result.json) remains
`bounded_unknown`. The tuned arms were faster than the first default
arm, but the final default arm matched the second tuned arm. Local CPU
timings remain exploratory because host isolation was unverified. The
[full attempt](../n83-geometric-m5-gauss-ordinary18-20261012/README.md)
tests the same setting at five million conflicts.

[Independent Sage replay](sage_relation_replay.json) checks the locked
group relation through a separate polynomial field. The checked Sage
launcher saved [runtime identity](sage_runtime_info.json) before the
pilot. The raw XCNF is reconstructed from the Q54 compressed archive;
the pilot verifies its raw SHA-256 before every solver arm. Run the
read-only audit from the repository root:

```sh
python3 experiments/n83-geometric-m5-gauss18-20261012/verify.py
```
