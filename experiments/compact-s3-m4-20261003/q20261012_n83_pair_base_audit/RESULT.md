# Q1494: exact base audit identifies eight usable N83 first pairs

An exact curve-lift, cofactor-four projection, and signed-Frobenius key
membership audit found **eight usable pairs among the 40 distinct Q1491
first-pair assignments**. The other 32 pairs had at least one leaf x value
without a rational curve lift. The eight usable pairs are exactly those with
a second-link S3 root for both ordinary targets in Q1493.

| Flipped leaf variables | Usable pairs / sampled pairs | First-pair CNF/XOR calls | Calls per usable pair | Base-filter field API entries |
| ---: | ---: | ---: | ---: | ---: |
| 17 | 1/8 | 727,592 | 727,592 | 1,084 |
| 42 | 1/8 | 706,818 | 706,818 | 1,348 |
| 83 | 1/8 | 731,926 | 731,926 | 1,084 |
| 166 | 2/8 | 759,924 | 379,962 | 1,084 |
| 249 | **3/8** | **778,598** | **259,533** | **1,348** |

The 249-flip group used 31.7% fewer first-pair calls per observed usable pair
than the 166-flip group on this frozen seed set. With only eight masks per
setting, the 3/8 versus 2/8 usable counts do not establish a stable density
effect. Both target points share the same reusable pair set, so matching
survival on the targets is a structural check, not an independent seed
replicate. A fresh mask-seed family should compare 166 and 249 flips with
exact base membership as the selection metric.

The [protocol](protocol.json) fixes the 40 Q1491 receipts, the Q1493 paired
root result, and the exact Q1325 factor base. The [freeze](freeze.json) binds
the 186,612 packed orbit keys and all source inputs. The [audit](audit.py)
lifts each x value, projects its curve point into the subgroup, verifies
subgroup membership, and checks its canonical point key against the
enumerated base. The [result](result.json) retains individual leaf outcomes
and separate CountedOnb field API counts for filtering and subgroup replay.
The [validator](validate.py) recomputed all 40 pair classifications.

This strengthens the stage cost boundary: an S3 first pair is usable only
when both leaves pass the actual base policy. The next solver improvement is
to reject nonrational leaves before paying the full first-pair search cost,
then measure target-conditioned completion with a second usable pair. The
fully charged N131 one-target exponent remains unset. Q1494 is a `PDP4sat`
stage proposal on `EC1N83Ckb1h876c2921cb64` with actual B=30,977,592,
folded K=186,612, `isogeny: "none"`, and null IC candidate/run IDs.

    env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_n83_pair_base_audit/validate.py
