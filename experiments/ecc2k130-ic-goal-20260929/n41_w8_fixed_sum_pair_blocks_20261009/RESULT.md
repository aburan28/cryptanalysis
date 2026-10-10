# Fixed-sum pair blocks give an exact ordinary N41 public-point relation

**A six-block target-conditioned 3+3 join found and independently replayed a
12-summand relation on the frozen N41 public point.** Each block uses the
same exact seed-sum linearization
`A(z)[A(a)^2+A(s)A(a)]=(s+z)^2`, where `A(t)=t^2+t`, and a 40-pair usable
mask domain. The native join built 3,750,144 distinct-column-compatible
left triples, then found a six-block witness after 931,150 target-dependent
right probes. Checked Sage independently reconstructed all 12 subgroup
leaves and confirmed their sum and 12 distinct folded columns. The
[native result](six_block_join/result.json),
[source lock](six_block_join/protocol.json), and
[Sage replay](six_block_join/audit.json) bind the observation.

## Exact geometry and target

The curve is `EC1N41Ckb1h7d5e80d3c4d0`, with
`GF(2^41)=GF(2)[t]/(t^41+t^3+1)`, `y^2+xy=x^3+1`, and subgroup order
`r=549756390943`. The public target is
`Q=(1458168294740,1672312028033)`. The frozen W8 source has 125 usable
mask codes per rotation. Fixing seed-sum code `56` leaves exactly 40
unordered usable mask pairs, 80 active mask codes, 160 signed subgroup
pair states per block, and a rank-seven linear product map. The
[geometry record](geometry.json) enumerates these states and checks the
S3 identity, subgroup projection, and first seven Frobenius rotations.
The seven-rotation restricted factor base has **B=1,120** actual usable
subgroup points and **K=77** folded columns; the six-block join uses the
first six rotations, giving **B=960** and the same 77 possible folded
columns. The witness uses 12 different columns.

The method is proposal `Q20261009174000`, with `candidate_id: null` and
`run_id: null`: the recorded stage produces a target relation, while a
complete IC candidate also specifies independent relation collection,
factor-base log solving, and final scalar recovery. Its measured
target-dependent join interval is therefore a point-decomposition stage
measurement, not a complete one-target IC online time.

## Frozen experiments

| Execution | Terminal status | Charged stage wall | Peak RSS | Exact outcome |
| --- | --- | ---: | ---: | --- |
| [Seven-block pinned SAT control](control/result.json) | `FOUND_VERIFIED_RELATION` | 0.313 s | 38.8 MB combined | XCNF model and seven-pair group replay passed |
| [Seven-block unpinned public SAT query](public/result.json) | `ONLINE_TIME_CAP` | 120.094 s | 171.2 MB combined | Search began; no terminal SAT model before cap |
| [Six-block exact public join](six_block_join/result.json) | `FOUND_VERIFIED_RELATION` | 1.522 s left-table build; 0.650 s target search | 351.6 MB native peak | Witness indices `[63,21,27,40,102,133]`; independent Sage replay passed |

The six-block native total was 2.172 seconds, and the guarded command took
2.834 seconds including process launch and input loading. Its left table
had 3,750,128 unique group sums; the right search saw two group hits, one
rejected for a repeated folded column and one accepted after full group
replay. The target-dependent interval starts after the reusable left
table is ready and includes right-triple generation, target residual
lookup, column checking, and native witness replay. The separate Sage
verification runs outside that interval. The experiment used one worker
and caps of 600 seconds and 4 GiB. Wall times on this host are exploratory
because there is no host-isolation receipt; exact group equalities and
state counts do not depend on CPU timing isolation.

The first seven-block control attempt was preserved as
[`PRODUCER_FAILURE`](producer_failure_v1.json): its solver seed exceeded
CryptoMiniSat's accepted integer range and search did not start. The
[v2 protocol](protocol.json) bound a valid seed before the two SAT runs in
the table. The [parent Sage audit](audit.json) passed 28 sampled pair-state
replays and checked both v2 terminal receipts. The six-block join has its
own frozen [input](six_block_join/input.txt), [input receipt](six_block_join/input_receipt.json),
[run receipt](six_block_join/run_receipt.json), and
[checked-Sage runtime](six_block_join/sage_runtime_info.json).

## N131 promotion gate

The [source-bound projection](six_block_join/n131_projection.json)
recounts the audited d13 usable-code set. Its largest fixed-sum bucket is
seed-sum code `1830`, with 1,102 unordered usable pairs and 4,408 signed
pair states per block. A direct three-block table has
`4408^3=85,649,485,312` states. Even storing only two 131-bit point
coordinates at 17 bytes each needs **2,912,082,500,608 bytes**, or more
than 678 times the 4-GiB limit, before descriptors, hash slots, and
allocator overhead. A compatible target-conditioned method must reject
at least **678 of every 679** three-block families before materializing
that direct table, or use a different representation with a proved
resource bound. This is a storage bound for the exact direct join, not a
lower bound on all point-decomposition algorithms.

The next experiment is an exact cross-block constraint that combines the
seed-sum linear maps with the public target before expanding a third pair
block. It should measure how many complete families it eliminates on the
same N41 public point, preserve every genuine six-block witness found
here, and give a source-bound whole-search N131 operation and memory
projection before an N131 ordinary query. The fixed-sum linearization
reduces each block to one free seed, while the complete N41 join gives a
ground-truth witness against which such an early gate can be tested.
