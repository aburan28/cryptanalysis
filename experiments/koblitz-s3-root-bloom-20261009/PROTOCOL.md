# Canonical-root Bloom transfer on the N53 indexed S3 path

## Controlled change

The reference is an exact copy of the shared-inversion source in
`../koblitz-s3-pair-query-20261006-v2/candidate.rs` and is built beside the
new candidate against the same dependency revision. The new binary adds a
Bloom screen between canonical normal-basis root
formation and the exact sharded root-table lookup. The screen stores each
occupied **canonical root-table key once**. Every Bloom positive reaches the
original exact lookup and four-point check. A Bloom negative only skips a
root-table miss. The builder rereads every occupied root-table slot and
asserts membership before any target-dependent work begins.

This is a different placement from the A1 conjugate-x screen: here the
normal-basis conversion and canonical rotation already happen before the
screen. Expanding all roots into raw conjugates would substantially increase
preparation and memory for this index.

## Frozen comparison

- Curve: `EC1N53Ckb1h888961ed110e`, binary Koblitz `a=0, b=1` over
  `F_2[x]/(x^53+x^6+x^2+x+1)`; prime subgroup order
  `21,044,858,204,113`.
- Public point: `[6825828048296061,3029097503049988]` from the existing
  one-target workload `Wc3929365e014`.
- Factor base: 25,864 usable points before orbit folding; 244 folded
  relation columns; relation seed `20260928`; 14 relation/index workers plus
  the main thread; one target per fresh process.
- Five fresh-process pairs, alternating reference/candidate order:
  `AB, BA, AB, BA, AB`. Both use the same target and empty process caches.
- The online interval begins after base and index preparation and includes
  all target-dependent relation attempts, rank work, scalar recovery, and
  point replay. Record filter construction and exhaustive check with index
  preparation outside online. Preserve the five exclusive online phases,
  sampled peak RSS, all raw statuses, and launch order.
- This host has no audited physical CPU isolation receipt. Timing ratios
  remain exploratory; operation and witness equivalence are correctness
  checks. A controlled speed claim requires the isolated CPU service.

## Acceptance gates

1. Release tests pass. Every new target run reports an exact verified scalar.
2. For each pair, the same first target witness, ordered relation witnesses,
   rank, attempt count, target-span stop point, and scalar are obtained.
3. The Bloom build reports its bytes and time separately. The builder checks
   all stored keys, so a negative cannot discard an exact-index hit.
4. Retain the candidate only if its complete online interval or a measured
   lookup-stage diagnostic justifies the extra memory and setup. Otherwise
   report HOLD and keep the exact-table reference as the selected path.
