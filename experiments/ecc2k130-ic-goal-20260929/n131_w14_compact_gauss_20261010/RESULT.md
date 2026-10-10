# Five Gaussian matrices on the exact compact N131 public-point formula

CryptoMiniSat admitted five Gaussian matrices from the frozen compact
ECC2K-130 formula, but the ordinary public-point query reached its
**596-second solver cap** with status `CENSORED_TIME`. The combined sampled
peak RSS was **656,621,568 bytes** under the 4-GiB cap. The solver logged no
SAT or UNSAT status and no model. The [terminal audit](terminal_audit.json)
checks the exact input formula, source and log hashes, target point, matrix
admission, resource bounds, and retained terminal status. This settles the
specific moderate-component Gaussian gate: admitting these matrices did not
clear the first N131 decomposition gate under the frozen budget.

## Frozen comparison

The [protocol](protocol.json) was frozen before a 60-second preflight and
the full run. Both use the same unpinned published subgroup point on
`EC1N131Ckb1heb5f1998f20b`, one worker, and the exact archived compact
XCNF from the [zero-matrix run](../n131_w14_compact_columns_20261010/RESULT.md).
Its decompressed SHA-256 is
`01ff129bda5bc03722bfe97fa4f09b71145ca336a7e2c91779312d9f73446eac`:
119,952 variables, 333,529 CNF clauses, 43,195 native-XOR rows, and
18,684,062 bytes. The factor-base geometry remains **B = 98,640** usable
points and **K = 8,160** folded columns. This is a point-decomposition
solver-setting experiment; the complete IC `candidate_id` remains `null`.

The Gaussian run adds `--maxmatrixrows=3500 --maxmatrixcols=10000` to the
baseline CryptoMiniSat flags. Its log records five matrices admitted from
the moderate XOR components; the larger 24,687-row component was excluded.
The full run reuses the formula whose measured construction time was
2.212 seconds. Charging that construction to this query gives **598.263
seconds** of construction plus active search, within the frozen 600-second
bound. The 60-second preflight is a separate method-selection diagnostic,
not part of the full query.

| Same public point and XCNF | Zero matrices | Five matrices |
| --- | ---: | ---: |
| Solver status | `CENSORED_TIME` | `CENSORED_TIME` |
| Active solver wall, seconds | 596.799 | 596.051 |
| Formula construction plus solver wall, seconds | 599.011 | 598.263 |
| Sampled peak combined RSS, bytes | 676,347,904 | 656,621,568 |
| Sampled solver CPU, seconds | 434.795 | 487.814 |
| Last logged conflicts | approximately 2.297 million | approximately 453 thousand |
| Verified public relations / useful rank | 0 / 0 | 0 / 0 |

The Gaussian [preflight receipt](preflight/result.json) records
`CENSORED_TIME`, five matrices, 60.097 seconds solver wall, and 429,047,808
bytes sampled peak RSS. The [full receipt](full/result.json) and
[raw solver log](full/solver.stdout.txt) retain the 596.051-second cap and
five matrix-admission observations. CryptoMiniSat reported Gaussian
usefulness of 3.2075% over 530 calls and disabled elimination in subsequent
rounds. Different host contention and internal solver trajectories make the
conflict and CPU differences exploratory diagnostics, not a controlled
speedup comparison. Both runs preserve their censored status; no time-to-
relation estimate follows from the cap.

## Next algorithmic gate

The [same-seed four-atom inverse](../n131_w14_coupled_fouratom_inverse_20261010/RESULT.md)
checks one *proposed* partial output in 7.496–9.722 seconds on N131 in its
recorded controls. A useful next method must generate proposed outputs from
the public target's joint partial-sum constraint before applying that
inverse. First freeze an unpinned N41 public-point control and record every
generated output, inverse call, branch replay, verified relation, novel
rank, wall time, and RSS. Its successful group replay is the gate for a
source-bound N131 projection and a new 600-second / 4-GiB public query.
