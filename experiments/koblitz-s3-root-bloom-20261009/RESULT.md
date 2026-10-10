# A 4 MiB canonical-root Bloom screen removes 99.254% of exact S3 table probes

The new N53 `PDP4root` candidate inserts the 3,154,661 occupied canonical
normal-basis S3 root keys into a 4,194,304-byte Bloom filter during index
preparation. After a partner root is solved and canonicalized, a negative
filter test skips the large sharded exact-table probe; every positive still
uses the unchanged exact lookup and four-point group check. The filter build
checks every occupied key before target-dependent work. Its implementation is
[`candidate.rs`](candidate.rs), copied from the previously validated
shared-inversion source except for this screen and its setup accounting.
The [review and replay instructions](REPRODUCE.md) include the factor-base
data needed to check the archived Sage result from this PR checkout.

The [source-bound protocol](PROTOCOL.md) pairs it with the exact-table
[`reference.rs`](reference.rs) on workload `Wc3929365e014`: Koblitz
`a=0,b=1` over `F_2[x]/(x^53+x^6+x^2+x+1)`, subgroup order
`21,044,858,204,113`, 25,864 usable base points, 244 folded columns, and
public target `[6825828048296061,3029097503049988]`. Each process has one
target and 14 relation/index workers plus the main thread. The online clock
starts after the base and S3 index are built and ends after the scalar is
recovered and replayed; all failed relation queries and matrix work are
charged to that target. The filter's build and exhaustive check are reusable
preparation outside this interval.

| Candidate | Exact-table reference | Canonical-root Bloom |
| --- | ---: | ---: |
| ID suffix | `hbc2ce1eff239` | `haa51cdc803e6` |
| Stored S3 root keys | 3,154,661 | 3,154,661 |
| Bloom allocation | 0 | 4,194,304 bytes |
| Verified one-target paired runs | 5 | 5 |
| Median online wall, unisolated host | 1,185.712 ms | 1,172.234 ms |
| Median paired reference/Bloom ratio, exploratory | — | 1.155 (range 0.917–1.304) |
| Median filter build and exhaustive check | — | 108.662 ms, outside online |
| Recovered scalar and first witness | `20263353138066` | identical in every pair |

The Bloom candidate had the lower online wall in four of five alternating
pairs. The original panel's internal `ps` call was denied in this sandbox, so
those rows retain `peak_rss_bytes: null`. A separate [capped peak-memory
probe](MEMORY_PROTOCOL.md), using fresh interpreters and per-child resource
usage on macOS, returned median peaks of 542,081,024 bytes for the reference
and 558,514,176 bytes for Bloom. Its three paired Bloom-minus-reference
deltas were 4,767,744, 4,128,768, and 17,989,632 bytes; the median paired
delta was 4,767,744 bytes. These peaks include the complete process, index,
and allocator. The five timing pairs had no predeclared wall cap but all ten
processes completed; a new controlled panel needs a cap fixed in advance.

A separately built [instrumented scanner](diagnostic/src/main.rs) counted
15,420,110 canonical-root probes on the same target. Bloom negatives skipped
15,305,120 exact-table probes (**99.254%**). The remaining 114,990 probes
comprised 114,751 positive tests that missed in the exact table and 239 exact
root hits; the false-positive rate among exact misses was 0.744%. This count
comes from an instrumented binary with atomic counters and is an operation
diagnostic, not one of the five timed candidate binaries. The filter runs
**after** S3 solving and 53-rotation canonicalization, so this table-probe
reduction does not represent the same fraction of total online work.

Release tests passed for both binaries, including an exhaustive N13
candidate-x comparison between filtered and exact lookups. All ten N53 raw
outputs have the same normalized semantic digest: first target witness,
ordered relation witnesses, 238 completed relation attempts, rank 237,
target-span stop, and scalar. The [independent checked Sage
replay](independent_sage_replay.json) verifies the target equation, all 238
four-point relations, matrix rank and scalar point replay. The
[validator](validate.py) binds the source and binary hashes, all ten raw
outputs, memory receipts, diagnostic counters, and five exclusive online
phase sums. Exact source identities, candidate manifests, raw rows, and
summary are in [`freeze_receipt.json`](freeze_receipt.json),
[`runs/panel_rows.jsonl`](runs/panel_rows.jsonl), and
[`validated_result.json`](validated_result.json).

## Transfer map

| Path | Decision |
| --- | --- |
| A1 three-summand pair-index target scan | The separate local 24-target conjugate-x Bloom replay validates raw-conjugate rejection before 52 field squarings. Its direct aligned loader retains the verified scan while reducing transient load memory. Bind any transfer to its exact index and recheck witness order. That experiment is outside this PR. |
| N53 indexed four-summand S3 root lookup | This candidate screens the **canonical** root key after normal-basis conversion, adding 4 MiB instead of expanding all 53 raw conjugates. Retain as an opt-in candidate for a disjoint one-target panel and isolated CPU run. |
| N83 indexed S3 root lookup | An N83/K600 run has 29,878,182 distinct root keys; a canonical-key filter would require its own measured memory and hit-rate design. The existing N83 orbit-query work already has a different Bloom screen on canonical 83-bit keys. |
| Boolean F4/F5 | [`solve.py`](../pdp-scaling/solve.py) and the sibling `crypto/src/cryptanalysis/koblitz_groebner.rs` reduce polynomial rows and signatures. They do not perform this S3 root-table lookup inside the matrix kernel, so this filter has no direct insertion point there. |

The next promotion experiment is a disjoint public-point panel with the same
candidate manifests, explicit per-run timeout, complete one-target phase and
peak-memory receipts, and the repository's isolated CPU service. Keep the
exact-table path selected until that gate resolves the complete online cost.
