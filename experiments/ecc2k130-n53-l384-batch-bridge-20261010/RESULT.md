# ECC2K-53 L384 certified-base batch: setup-cost barrier

The frozen 384-point experiment recovered all 384 IC and matched
signed-Frobenius rho scalars. Its charged IC pipeline took 327.208 s and the
same-Q batched rho table took 149.927 s. More decisively for this exact
certified-base stream, fresh training, base materialization and mandatory
rank/log solving alone took 199.233 s. Even a zero-cost point-query and
recovery stage would leave this measured pipeline 49.306 s above rho. The
[source result](https://github.com/aburan28/crypto/actions/runs/36218536407)
classifies the first attempt as `COMPLETE_FIXED_STREAM_NO_CROSSOVER`.

| Stage | Archived wall time (s) |
|:--|--:|
| Fresh-base construction and 512-relation training | 149.004 |
| Certified-base identity materialization | 0.231 |
| Rank and factor-base log solve | 49.999 |
| 384-point IC relation producer | 100.700 |
| 384-scalar IC recovery | 27.275 |
| **Operational IC sum** | **327.208** |
| Same-Q batched rho | 149.927 |
| Separate full group-law audit | 151.137 |

The base was generated fresh by seeded `legacy_rank_fixture_lcg_v1` selection:
400 scanned x values, 23,320 usable points, and 220 signed-Frobenius columns.
The ordered representative-key BLAKE3 digest is
`d859319015ea405fd18aee41b51396ce4edcab64ef66265d8edcdeb5e040eb71`.
Rank reached 220/220 at training relation 461 of 512; 51 later relations
predicted the solved logs. The point producer then yielded 384 verified
relations for 384 previously fixed public Q values. The source run was one
GitHub-hosted Linux attempt with a 2-GiB process-group cap. Its reported
IC/rho operational ratio is 2.182, a same-host batch observation without the
host-isolation receipt required for a controlled CPU timing claim.

The [local replay](REPLAY.json) pins the merged crypto archive at commit
`9be831f4ec75c9a18334a67033333aeeb4b42fad` and four frozen source files
to release commit `de97b428166f59b38a1047b9e60aa99fd0aa0024`. It checks
all frozen source and input hashes, 35 sealed archive files, stage receipts,
fresh-base identity, cost arithmetic and release ancestry. The archived
unmodified Python group-law audit exceeded its 620-second child cap on the
local macOS Python 3.13 runtime. This bridge therefore reruns that exact
audit in memory with a compiled GF(2^53) multiplication kernel; the kernel
matches both independent archived Python field implementations on all 2,809
basis-product pairs and 1,000 seeded field pairs. All 23,320 orbit labels,
512 training witnesses, 384 IC witnesses/logs and 384 rho logs replayed, and
the complete report matched the sealed `audit.json` exactly. The compiler
build is outside every archived measurement interval.

Run the replay with a local checkout containing the pinned crypto commits:

```sh
python3 experiments/ecc2k130-n53-l384-batch-bridge-20261010/replay.py \
  --crypto-repo /Volumes/SSD990/crypto
```

This is a 384-target shared-table workload and uses a different factor base
from the [one-target K220 restart study](../ecc2k130-n53-fixed-base-rank-bridge-20261010/RESULT.md)
(its base digest begins `7af2460c`). Its batch ratio does not answer the
primary one-target online comparison. The next controlled decision is to
freeze one-target same-Q streams across the two base constructions, charge
their full training/rank setup separately, and test base diversification or
rank-policy changes before investing further in point-query-only speedups.
