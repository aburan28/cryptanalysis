# N83 packed-root K900 fourth-target result

**A 16-byte packed root-table slot lets K900 complete under the 12 GiB sampled
RSS cap, and K900 reduced verified one-target online time by 3.23× against
packed K899 on the fourth frozen public point.** K900 used 149,400 distinct
usable subgroup points before sign/Frobenius folding and 900 relation-matrix
columns. Its target relation took 720,414 root probes and 433.646 ms online;
K899 used 149,234 points, 899 columns, 2,781,133 probes, and 1,401.776 ms.
Both arms reached full rank, verified the four-point relation, and replayed
the recovered scalar. This is a CPU-only secondary control on a shared Mac;
the wall ratios are exploratory and the controlled-speedup fields are null.

| Fourth public point, same packed source and 12 GiB cap | K899 | K900 |
| --- | ---: | ---: |
| Usable subgroup points before folding | 149,234 | 149,400 |
| Effective columns | 899 | 900 |
| Regular index states | 67,080,683 | 67,230,000 |
| Distinct root-table entries | 67,077,932 | 67,227,246 |
| Packed table allocation | 4 GiB | 8 GiB |
| Index build | 87.524 s | 101.177 s |
| Guided rank / attempts / failed attempts | 899 / 899 / 0 | 900 / 900 / 0 |
| Rank stage | 56.686 s | 52.863 s |
| Target relation probes | 2,781,133 | 720,414 |
| Verified target online | 1,401.776 ms | **433.646 ms** |
| Full fresh-process wall | **146.647 s** | 155.452 s |
| Sampled peak RSS | 5,533,270,016 B | 9,608,609,792 B |

The extra orbit crosses the hash-table power-of-two boundary. K899's
67,080,683 regular states request `2²⁸` slots, while K900's 67,230,000
request `2²⁹`; the packed layout halves each slot from the prior 32-byte
`(u128,u64)` representation to one 16-byte `u128`. K900's 8 GiB table fit
inside the frozen 12 GiB process cap alongside its states and other data.
The opt-in layout preserves exact keys, first-inserted witnesses, and the
existing probe order; the [implementation PR](https://github.com/aburan28/crypto/pull/1777)
contains the equivalence tests. The executed source is the clean, pre-run
commit `eeaa10fc08c983d730bd397dd3c6f9eb089c1c5b` and the executed
`KIC_PACKED_ROOT_TABLE=1` flag is in both IC arm receipts.

The [frozen protocol](protocol.json) was committed and pushed before execution
at `0a72e5a10b0b76b6d9992c179e293e1b51bad2ee`. It fixes the fourth public
point, source and binary inputs, K899/K900 arms, rank seed 29, 12 rank threads,
one target thread, a 60-minute IC process cap, 60-second rho cap, and the
12 GiB sampled RSS stop. The fixture scalar is confined to the
[validation sidecar](validation_sidecar.json), outside the worker target
input. The public point, workload ID `cc1a4cc699a9`, and exact binary hashes
are in the [run receipts](runs/), [workload](workload.json), and
[binary manifest](binary_manifest.json). A separate clean-source
[rebuild](build_provenance.json) reproduced both executed binary hashes.

The [independent verifier](verification.json) passes the public input,
binary and raw-output hashes, phase sums, rank, nested base, four-point group
sum, scalar replay, and paired-rho charge checks. The
[full K900 base replay](full_base_replay.json) checked every one of its 149,400
point and label rows, all 900 subgroup representatives, orbit closure, and
distinct orbit keys. K899's repeated base dump is byte-identical to its
previous checked dump. The [factor-base archive](../fb-archive/README.md#n83-a1-compact-orbit-bases)
retains the exact K900 point set by digest. Canonical
[measurement rows](measurements.json) contain five exclusive target-online
phases, cold costs, full curve and candidate UIDs, and null controlled
speedups; [identity replay](verify_identities.py) checks their hashes and
archive linkage. The [hardware receipt](hardware.json) records
`gpu.devices: []` and unavailable CPU placement and co-runner counters as
null.

The tuned strong-rho reference solved the same public point before and after
the IC arms in 2,273.645 and 2,187.335 ms online, with identical walk charges.
IC online starts after target-independent base, index, rank, and factor-log
preparation and includes target query, point decomposition, relation check,
direct descent, and scalar replay. The process-wall row includes preparation.
The paired CPU timings need a Tier 1 or Tier 0 timing receipt and a held-out
point panel to assess host noise and first-witness variation. The next
capacity screen can test K values above 900 while keeping this table layout
and memory cap fixed.

To replay the read-only checks from a checkout with the pinned clean crypto
source available as `N83_CRYPTO_REPO`:

```sh
N83_CRYPTO_REPO=/path/to/crypto-at-eeaa10fc python3 experiments/n83-packed-root-k900-20261013/verify.py
N83_CRYPTO_REPO=/path/to/crypto-at-eeaa10fc python3 experiments/n83-packed-root-k900-20261013/verify_full_bases.py --verify-only
python3 experiments/n83-packed-root-k900-20261013/verify_identities.py
python3 experiments/fb-archive/compact_orbit_base_archive.py --verify-only
```
