# N83 witness-preserving canonical prefix

The previously verified N83 four-point relation is retained by the first
**33,766 sorted signed-Frobenius orbits** of the frozen 48,194-orbit known-log
base. This prefix has **5,605,156 actual usable subgroup points**, 2,395,048
fewer than the parent. Independent Sage replay read only the reduced
[key/log file](witness_prefix_keys_and_logs.bin), checked all four point logs
and their sum, and recovered the archived scalar on the same public target.

The construction is retrospective: the relation determined the prefix size.
It is a replay and implementation control for a smaller base, while a newly
frozen target is needed to compare candidate success rates or online times.

## Exact prefix and capacity

The native producer expands each 32-byte canonical key/log record into 166
points in file order. The archived relation has expanded point indices
`[3534140, 5605002, 475624, 704149]`, corresponding to zero-based orbit
indices `[21290, 33765, 2865, 4241]`. Thus the smallest **sorted file
prefix** retaining this witness has `K=max(orbit index)+1=33,766`. Removing
its final orbit excludes point index 5,605,002.

| Base | Orbits `K` | Actual points `B` | `83K(K-1)` pair ranks | M32 + 80 R29 margin |
| --- | ---: | ---: | ---: | ---: |
| Minimum schedule capacity, different seeded base | 23,859 | 3,960,594 | 47,245,925,826 | 1,285,570 |
| Witness-preserving sorted prefix | **33,766** | **5,605,156** | 94,629,046,170 | 47,384,405,914 |
| Archived parent | 48,194 | 8,000,204 | 192,776,915,686 | 145,532,275,430 |

The witness-preserving prefix removes **14,428 orbits (29.94%)** from the
archived parent. It is separate from the 23,859-orbit minimum-capacity
seeded base: those are different subsets of the parent canonical key set.
The existing exact table/query schedule has ample pair-rank domain on this
prefix, but its affine offsets and native work must be regenerated for a new
run. A known witness on the archived point does not predict one on an unseen
point.

## Frozen sources and verification

The [protocol](protocol.json) binds the terminal evidence archive, shard-46
relation, original 48,194-orbit receipt and key/log file, and expected
expanded indices by SHA-256. [derive.py](derive.py) takes the exact byte
prefix, checks sorted unique canonical keys, and records the set, log, and
capacity digests in [prefix.json](prefix.json). It refuses to overwrite
evidence. The [checked Sage runtime receipt](sage_runtime_info.json) was saved
before [independent replay](independent_sage_replay.json), which reports
`PASS`. Sage used an irreducible polynomial field representation, checked the
subgroup generator and target, reconstructed four points and known logs from
the prefix alone, matched the archived relation points, and checked both the
four-point sum and scalar replay.

In a fresh directory at the repository root:

```sh
python3 experiments/koblitz-pair-claw-20260929/n83_witness_prefix_20261012/derive.py
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/koblitz-pair-claw-20260929/n83_witness_prefix_20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-pair-claw-20260929/n83_witness_prefix_20261012/verify_sage.py
```

The next e2e gate remains a precommitted known-log base, one unseen public
target, full target-dependent attempts with measured RSS and failures, and a
same-point rho reference on the same resource tier. The 23,859-orbit base
from the capacity search and this 33,766-orbit control can be compared under
that protocol without selecting either base after seeing the new target.
