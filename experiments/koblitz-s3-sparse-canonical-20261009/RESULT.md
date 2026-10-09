# Sparse S3 root canonicalization preserves witnesses and lowers N53 one-target time in the exploratory panel

The candidate replaces the 53-rotation normal-basis canonicalizer at both
S3 index insertion and partner-root lookup with a longest-cyclic-zero-gap
canonicalizer. It retains the exact canonical root key and minimum shift, so
the sharded index, point lifts, and ordered relation witnesses are unchanged.
The source is in [`candidate.rs`](candidate.rs); [`reference.rs`](reference.rs)
is the same-dependency rotation reference. The algorithm came from
`crypto/examples/koblitz_orbit_dlp_slice_ic_fastindex4.rs` at SHA-256
`723a80e87d66dee9b947cff19cf0a555bb4a9d01723a6e5f6bec5abe4b073fb0`.
The sibling dependency's tracked sources match `crypto` revision
`8ab924b935923df9faac25915ed7d9849974de0b`.
This copy guards precomputation levels whose rotation length would exceed
the degree, covering small-degree debug builds as well as N53.

The [frozen protocol](PROTOCOL.md) uses `EC1N53Ckb1h888961ed110e`,
Koblitz `a=0,b=1` over `F_2[x]/(x^53+x^6+x^2+x+1)`, prime subgroup order
`21,044,858,204,113`, and one supplied public point
`[6825828048296061,3029097503049988]`. The base has 25,864 usable
points and 244 folded columns. Five fresh-process pairs alternate order,
with 14 relation/index workers, relation seed `20260928`, and a 30-second
process wall cap. The online interval starts after reusable base and index
preparation and ends after verified scalar replay.

| Measure | 53-rotation reference | Sparse canonicalization |
| --- | ---: | ---: |
| Candidate ID suffix | `h2cc03b85c362` | `he7f690c8fafa` |
| Verified one-target runs | 5 | 5 |
| Median online wall, unisolated host | 1,840.961 ms | 1,369.210 ms |
| Median reusable setup wall, separate | 323.676 ms | 266.095 ms |
| Median paired reference/sparse online ratio, exploratory | — | 1.203 (range 1.133–1.476) |
| Exact root-table entries | 3,154,661 | 3,154,661 |
| First target witness, 238 ordered relation witnesses, rank 237, scalar | Same in every pair | Same in every pair |

All five paired online comparisons favored sparse canonicalization. The
candidate and reference outputs have the same normalized semantic SHA-256
`1f2e6e9f1e6cc61150707c9d4319d5a3726d51dc41a726b9cd82d890b508564f`.
The recovered scalar is `20,263,353,138,066`; the
[checked Sage replay](independent_sage_replay.json) verifies the target
equation, all 238 four-point relation witnesses, matrix rank, and scalar
point replay. The complete rows and timing phases are in
[`runs/panel_rows.jsonl`](runs/panel_rows.jsonl) and
[`validated_result.json`](validated_result.json). Source, binary, dependency,
workload, and protocol hashes were frozen before the paired runs in
[`freeze_receipt.json`](freeze_receipt.json) and the two candidate manifests.

Release tests passed for both binaries. The candidate tests compare exact
`(canonical key, shift)` over every binary word of degrees 1 through 13,
50,000 deterministic N53 words plus edge patterns, and 6,330 roots sampled
across the actual N53 S3 index. The shared-inversion and sharded-index tests
also pass. The [validator](validate.py) checks source and binary bindings in
the frozen workspace. Its [archive mode](REPRODUCE.md) verifies the published
source, raw outputs, all five exclusive online phase sums, semantic equality,
and Sage receipt without the original binary files. Peak RSS was unavailable from the existing
in-process sampler on this host; it remains an explicit `null` in every row.
The separate Cargo target uses about 303 MiB. Free space on `/Volumes/SSD990`
was about 2.3 GiB before this build and 1.7 GiB after the final runs, with
concurrent work also using the volume.

An earlier exploratory screen used the unguarded sparse routine copied from
the sibling example. Its N53 semantics matched, but its fixed precomputation
could calculate `n-k` with `k>=n` at small degrees. The published panel uses
only the corrected, re-frozen source and new runs.

The panel is an unisolated CPU timing diagnostic. Controlled online speedup
remains `null` pending a disjoint supplied-point panel on the repository's
isolated benchmark service, with a peak-memory receipt. The next code
transfer is to apply the small-degree guard to the sibling fastindex
canonicalizer, then test the sparse method on a different S3 root workload.
