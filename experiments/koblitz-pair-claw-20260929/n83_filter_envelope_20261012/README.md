# N83 pair-claw M32 filter allocation under an 8 GiB cap

For the verified **23,859-orbit, 3,960,594-point** N83 base, **15 bits per
table key is the largest setting whose M32 Bloom allocation can fit below an
8 GiB process-memory cap**. The native block formula allocates
8,053,129,216 bytes at 15 bits per key, leaving 536,805,376 bytes for the
expanded base and other live data. At 16 bits, the filter alone allocates
8,590,000,128 bytes, exceeding 8 GiB by 65,536 bytes. These figures are
exact allocations from the current C++ source; a full M32/R29 run is still
needed to establish the complete process peak under that cap.

The [allocation frontier](allocation_frontier.json) covers 8–20 bits per
key and binds the [base receipt](../n83_base_size_search_20261012/minimal_base.json),
source, and [protocol](protocol.json). The source computes
`64 * (ceil(M * bits_per_key / 512) + 1024)` bytes for its cache-line
blocks. It releases that filter before constructing the exact replay table.

| Bits/key | M32 filter bytes | Cap margin before base | M20/R18 filter positives | Exact replay |
| ---: | ---: | ---: | ---: | --- |
| 14 | 7,516,258,304 | 1,073,676,288 | 45,957 | completed |
| 15 | 8,053,129,216 | 536,805,376 | 29,214 | completed |
| 16 | 8,590,000,128 | −65,536 | 19,091 | completed |
| 20 | 10,737,483,776 | −2,147,549,184 | 3,970 | completed |

The [eight stage cells](stage_runs.json) use the same frozen public point,
23,859-orbit base, M20 table, R18 query range, ten hashes, four workers,
and source-generated native code. Each bits/key value ran twice in an
opposed order. All cells completed exact replay, with zero exact hits in
this bounded range. At 15 bits the positive count was 7.36 times the
20-bit count. The positives are deterministic for this source and input;
local wall times varied substantially and are exploratory diagnostics.

The stage RSS at 15 bits ranged from 162,955,264 to 164,069,376 bytes,
including its 2,031,616-byte M20 filter. Substituting the exact M32 filter
allocation gives a rough pre-replay peak projection below 8 GiB with about
375 MB margin. This projection does not include all full-shape allocation
effects or certify a capped host run. The filter-positive rate also changes
replay and spill work; the [stage receipt](stage_runs.json) retains every
phase and positive count rather than converting this small cell into a
full-target timing estimate.

The next full-shape check is one M32/R29 shard on a newly frozen public
point with the minimum base, its disjoint query offset, 15 bits per key,
explicit spill capacity, and a hard 8 GiB memory limit. Retain all phase,
RSS, timeout, and verification receipts. Use a qualified Tier 1 RunPod or
Tier 0 isolated host before promoting a CPU timing comparison; the
single-target online result requires all charged target-dependent attempts
and a paired same-point rho solve.

Reproduce the local allocation and stage records with:

```sh
python3 experiments/koblitz-pair-claw-20260929/n83_filter_envelope_20261012/run.py
```
