# N83 packed-root capacity result: K1271 fits, K900 leads the fifth point

**The 16-byte packed root index completed K1271 with 210,986 usable subgroup
points under the frozen 12 GiB sampled RSS cap.** K1271 reached full rank and
verified the fifth public target in 14.773 ms online. The nested K900 base
reached that same target in 2.591 ms; K1200 took 553.244 ms. All three used
the same public point, source, packed-table flag, rank seed, and resource cap.
On this point K900 had both the shortest online interval and the lowest
fresh-process wall. These are CPU-only secondary controls on a shared Mac;
the wall ratios are exploratory and controlled-speedup fields are null.

| Fifth public point, packed root index | K900 | K1200 | K1271 |
| --- | ---: | ---: | ---: |
| Usable subgroup points before folding | 149,400 | 199,200 | 210,986 |
| Effective columns | 900 | 1200 | 1271 |
| Regular index states | 67,230,000 | 119,520,000 | 134,081,603 |
| Distinct root-table entries | 67,227,246 | 119,516,232 | 134,077,589 |
| Packed root-table allocation | 8 GiB | 8 GiB | 8 GiB |
| Index build | 83.392 s | 138.793 s | 191.198 s |
| Guided rank / attempts / failed attempts | 900 / 900 / 0 | 1200 / 1200 / 0 | 1271 / 1271 / 0 |
| Rank stage | 51.462 s | 37.179 s | 32.287 s |
| Target relation probes | **2,067** | 1,236,887 | 22,534 |
| Verified target online | **2.591 ms** | 553.244 ms | 14.773 ms |
| Full fresh-process wall | **136.209 s** | 177.493 s | 224.924 s |
| Sampled peak RSS | 9,825,828,864 B | 11,523,981,312 B | 10,753,507,328 B |

All three use curve `EC1N83Ckb1a1haacb69ee9f37` and workload
`e1d0c16645bc`. Their exact candidate IDs are:

- K900: `IC1N83Ckb1a1fb149400PDP4rootRCguidedLAgaussTDdirectISO0h8ae9814bc811`
- K1200: `IC1N83Ckb1a1fb199200PDP4rootRCguidedLAgaussTDdirectISO0hc689421aee74`
- K1271: `IC1N83Ckb1a1fb210986PDP4rootRCguidedLAgaussTDdirectISO0hf6a65bdc8ab8`

K1271 is the largest integer whose **source-level maximum** of `83*K²`
regular states asks for at most `2²⁹` slots with the current four-slots-per-
state allocation rule. K1272's maximum crosses to the next table width.
K1271's measured state count reached its maximum; the source-reported table
layout is `packed_u128`, 16 bytes per slot, with 8 GiB allocated in each arm.
The sampled RSS order does not imply that K1271 intrinsically uses less
memory than K1200. The numerical capacity step is checked in Lean 4:

| Capacity result | Lean declaration | Scope |
| --- | --- | --- |
| K1271 request fits `2²⁹` slots | `N83PackedRootCapacity.k1271_requested_slots_fit` | `states ≤ 83*1271²` |
| K1272 maximal request exceeds `2²⁹` | `N83PackedRootCapacity.k1272_maximum_crosses_boundary` | numeric maximum only |
| `2²⁹` packed slots use 8 GiB | `N83PackedRootCapacity.packed_table_bytes_at_boundary` | 16-byte slots |

[`CapacityBound.lean`](CapacityBound.lean) and its [proof receipt](proof_check.json)
retain the Lean 4 v4.34.1 command, output, source hash, and `#print axioms`
audit. All three declarations have no axioms beyond Lean core; the Rust
loop-to-bound bridge remains a source inspection and measured-state check.

The [protocol](protocol.json) was committed and pushed before execution at
`f8852bfd1b680d3d7ec90b0e22e071e0c51b768b`. It fixes the fifth public
point, source commit `4794b94c945fce142292ef69ae48e5f88d267f44`, arm
order, rank seed 29, 12 rank threads, one target thread, 60-minute IC cap,
60-second rho cap, and 12 GiB sampled RSS stop. The public point is in
[`target.jsonl`](target.jsonl); its fixture scalar stays in the
[validation sidecar](validation_sidecar.json), outside the worker input.
The [binary manifest](binary_manifest.json), [raw runs](runs/), and independent
[clean-source rebuild](build_provenance.json) retain executable identities.

The [one-target verifier](verification.json) checks input and output hashes,
the recorded packed layout, complete rank, nested point sets, four-point
group sums, scalar replay, online phase sums, and rho charge equivalence.
The [all-point base replay](full_base_replay.json) checks the K1200 and K1271
point/label dumps, subgroup representatives, complete signed-Frobenius
orbits, and distinct orbit keys; K900's repeated dump matches its prior
checked copy. The [exact factor-base archive](../fb-archive/README.md#n83-a1-compact-orbit-bases)
retains both new point sets. [Canonical measurement rows](measurements.json)
retain curve and candidate UIDs, five exclusive target-online phases, cold
process costs, and null controlled speedups; [identity replay](verify_identities.py)
checks their bindings. The [hardware audit](hardware.json) records
`gpu.devices: []`, unpinned placement, and unavailable dynamic counters as
null.

The tuned strong-rho reference solved the same point before and after the IC
arms in 1,472.452 and 1,485.597 ms online. IC online starts after reusable
base, index, rank, and factor-log preparation, then charges target query,
point decomposition, relation check, direct descent, and scalar replay.
The full-process row includes preparation. K900's target online interval
changed from 433.646 ms on the fourth point to 2.591 ms here. A frozen
held-out point panel is the next experiment for estimating this strong
first-witness variation and comparing base sizes across the same inputs.

Read-only replay from a checkout with the pinned clean crypto source:

```sh
N83_CRYPTO_REPO=/path/to/crypto-at-4794b94c python3 experiments/n83-packed-root-capacity-20261013/verify.py
N83_CRYPTO_REPO=/path/to/crypto-at-4794b94c python3 experiments/n83-packed-root-capacity-20261013/verify_full_bases.py --verify-only
python3 experiments/n83-packed-root-capacity-20261013/verify_identities.py
python3 experiments/fb-archive/compact_orbit_base_archive.py --verify-only
(cd experiments/n83-packed-root-capacity-20261013 && lean CapacityBound.lean)
```
