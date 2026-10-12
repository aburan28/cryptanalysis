# Q1493: paired N83 targets retain the same eight first-pair candidates

All 40 frozen Q1491 first-pair assignments were continued against the four
raw preimages of each of two ordinary N83 targets. Exactly eight pairs had
a second-link S3 root on each target, with the **same eight pair identities**.
Across the five leaf-mask counts, the survivors were 1, 1, 1, 2, and 3 out
of eight first pairs at 17, 42, 83, 166, and 249 flips, respectively.

| Flipped leaf variables | Usable root paths per target: pairs | First-pair CNF/XOR calls per surviving pair | Target-root field API entries per surviving pair |
| ---: | ---: | ---: | ---: |
| 17 | 1/8 | 727,592 | 1,472 |
| 42 | 1/8 | 706,818 | 1,136 |
| 83 | 1/8 | 731,926 | 1,472 |
| 166 | 2/8 | 379,962 | 1,388 |
| 249 | **3/8** | **259,533** | **1,059** |

The first-pair search cost is target independent for this frozen pair set;
the target-root field API entries are charged separately. The two target
root queries produced the same group counts and per-group field API entries.
The [protocol](protocol.json) fixes the full 40-pair set, both ordinary
workloads, and the accounting boundary. The [freeze](freeze.json) binds all
40 pair receipts and both raw-preimage manifests. The [result](result.json)
records every second-link root, including rootless branches. The
[validator](validate.py) checked all 80 pair-target rows against the exact
S3 polynomial.

Q1494 then verified that the eight survivors are precisely the eight pairs
whose two leaves belong to the enumerated usable factor base. This is a
matched stage filter. It does not determine how often a usable second leaf
pair completes a four-point decomposition; that continuation is the next
measurement. The field and base are `EC1N83Ckb1h876c2921cb64`, actual
B=30,977,592, folded K=186,612, `PDP4sat`, `isogeny: "none"`; Q1493 has null
candidate and run IDs.

    env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_n83_paired_target_roots/validate.py
