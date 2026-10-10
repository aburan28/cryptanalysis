# Unpinned N41 public relation from a seed-partitioned join

A one-worker seed-partitioned join found and independently replayed a
**12-distinct-column relation** on the frozen N41 public point, with all six
pair masks, signs, block seeds, and cross-block offset unfixed. It used no
materialized free-four-point index. The native target-dependent interval was
**1.212417 seconds**, with **180,584,448 bytes** peak process RSS. The exact
W15 source census also proves that this direct seed-bucket join would test
**519,275,924,305,959,936** right-block combinations in its first bucket,
before free-pair probes; that work count redirects the N131 method toward
a compressed algebraic join.

## Input and algorithm

The field is `GF(2)[t]/(t^41+t³+1)` on `y²+xy=x³+1`. The subgroup order is
`549756390943`; the frozen public point is
`Q=(1458168294740,1672312028033)`. The W6 six-pair source has
`B=384` usable points and `K=26` folded columns. Its pair rotations are
`0,5,10,15,20,25`; pairs at rotations `10,15` share one mask-XOR seed,
pairs at `20,25` share another, and the two seeds differ by one of the
predeclared offsets `0..7`.

The [native implementation](native.cpp) builds each slot's 1,956 signed
pair states and the two 51,840-state constrained four-atom lists as
target-independent setup. For each first-block seed in increasing order,
it hashes only the compatible second-block sums into one bucket. It then
streams pairs from the first two free slots, queries the public-target
residual, checks twelve distinct source columns, and replays the full
group sum. The [protocol](protocol.json) froze the source, binary,
previously held public input, one worker, 120-second online cap,
130-second parent cap, and 4-GiB RSS cap before the query. The native
[receipt](receipt.json) retains all phases, counters, stdout, stderr,
exit status, and content hashes.

| N41 public-point stage | Recorded result |
| --- | ---: |
| First seed bucket / verified cross-block offset | `1` / `3` |
| Right combinations tested / inserted | 5,332,992 / 2,643,968 |
| Free four-point states probed before hit | 395,533 |
| Materialized free-four-point index entries | 0 |
| Target-independent setup | 0.020790 s |
| Target-dependent bucket build / free probe | 0.892536 s / 0.229786 s |
| Target-dependent total / parent wall | 1.212417 s / 1.910740 s |
| Peak process RSS | 180,584,448 B |

The [independent checked-Sage replay](replay_result.json) rebuilt all
source points from the archived geometry, checked their masks and
Frobenius rotations, verified the 12 distinct signed-Frobenius columns,
summed the projected and raw points to `Q`, and checked every normalized
pair equation and the cross-block seed identity. Its output offset is
`3`. The query used no archived relation masks, signs, free-pair output,
or seed as an input. The CPU times are exploratory measurements on an
unisolated host; they do not establish a controlled wall-time ratio to
the earlier indexed N41 search.

## Exact W15 work gate

For the same algorithm on the W15 source, the first seed bucket contains
**270,865,312** distinct-column four-atom A states. Compatible B seeds
`1..7` contain **1,917,100,128** four-atom states in total. The
[source-bound projection](projection.json) derives these counts from the
frozen W15 support and signed-seed census, including within-block column
filtering. The native loop must visit their Cartesian product,
`519,275,924,305,959,936` combinations, before it begins the free-pair
probe stage. The 600-second cap would require more than
`865,459,873,843,266` such combinations per second in the first bucket
alone. This is an exact operation-count bound for this implementation;
it is not a measured N131 wall time. The [terminal audit](terminal_audit.json)
binds the native, replay, and projection sources and results.

The next algorithm must keep the public target, free pairs, and both
constrained block product spaces symbolic or compressed while rejecting
incompatible families. The unpinned N41 relation above supplies a frozen
control for that replacement. Promotion to the N131 public query still
requires a source-bound one-worker projection within 600 seconds and
4 GiB, followed by independent relation replay. `candidate_id` remains
`null` until the complete IC pipeline is specified.
