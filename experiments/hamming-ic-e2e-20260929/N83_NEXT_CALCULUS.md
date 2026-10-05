# N83 next-calculus screen: six W3 summands or five with a sparse W4 extension

The earlier [N83 W3 measurement](N83_W3_GEOMETRY.md) proves that its
four-summand support is at most about 1.10 in a million ordinary subgroup
points. This follow-up screens three ways to change that geometry before
spending a complete solver run: use six summands on the measured W3 base,
admit a small deterministic set of W4 Frobenius orbits and use five summands,
or enlarge a four-summand base enough to pass the same counting gate.
These remain **proposals** with `candidate_id: null`; no N83 PDP, verified
relation, recovered DLP, rho comparison, or speedup has been measured.

The [protocol](n83_next_protocol.json) fixed the W4 prefix and checkpoints in
commit `6965c754` before execution. The exact curve is
`EC1N83Ckb1h2bcb59d56ad6`, in the polynomial basis with modulus
`u^83+u^7+u^4+u^2+1`; the subgroup has
`r=2417851639230796216685689` elements. The W3 base is the previously
replayed 89,474-point set with 539 signed-Frobenius columns. A W4 prefix
means the first distinct cyclic-mask orbits encountered in lexicographic
four-coordinate masks. For each rational x orbit, both signs and every
Frobenius image of its cofactor-four projection enter the base. The run
contains no known factor-base logarithms.

## Exact geometry

The checked-Sage [producer](runs/n83_next_geometry_v1/geometry.json) and
independent [lift_x replay](runs/n83_next_geometry_v1/sage_replay.json) agree
on every checkpoint, the final representative set, and the full projected
point-set SHA-256. The producer used half-trace lifting; the replay used
Sage `lift_x` and independently checked the normal-basis rank. Both saved
the accepted Sage runtime identity before arithmetic.

| Base | Summands | Actual B | Folded columns K | Multisets / r | Pair-state loops `83 K²` |
| --- | ---: | ---: | ---: | ---: | ---: |
| W3 only | 4 | 89,474 | 539 | 0.000001105 | 24,113,243 |
| W3 only | 5 | 89,474 | 539 | 0.01977 | 24,113,243 |
| **W3 only** | **6** | **89,474** | **539** | **294.78** | **24,113,243** |
| W3 + first 1,000 W4 orbits | 5 | 175,130 | 1,055 | 0.568 | 92,381,075 |
| **W3 + first 1,600 W4 orbits** | **5** | **224,764** | **1,354** | **1.977** | **152,165,228** |
| W3 + first 2,000 W4 orbits | 5 | 259,458 | 1,563 | 4.053 | 202,766,427 |
| W3 + first 4,000 W4 orbits | 5 | 423,964 | 2,554 | 47.21 | 541,402,028 |

`B` counts distinct nonidentity subgroup points before sign/Frobenius folding.
The multiset column is exactly `C(B+m-1,m)/r`, rounded for display. When it
is below one, it is an upper bound on the fraction of uniformly selected
subgroup points with any such decomposition. When it is above one, it is
only an average multiset count: collisions may concentrate sums, so neither
ordinary-target coverage nor solver yield follows. `83 K²` counts the
left/right/relative-orientation loops in the existing four-summand root-index
construction if applied to these representatives. It is a work-size proxy,
not a measured N83 index build or a complete five- or six-summand solver.

The first W4 prefix to cross a multiset ratio of one among the frozen
checkpoints is 1,600 orbits. Of those, 815 had rational x; no projected
orbit duplicated the W3 base. Across all 4,000 W4 orbits, 2,015 had
rational x and none duplicated a prior projected orbit. The producer's
whole-process interval was 61.1 seconds with 266.7 MB peak resident memory
on this unisolated Mac; these are exploratory base-construction diagnostics,
not CPU speedup measurements. The exact figures and timings are in the run.

## Four-summand resource gate

On this N83 subgroup, at least **2,760,006** usable base points are needed
even for the four-point multiset count to reach `r`. If every signed-Frobenius
orbit is full, that requires at least **16,627** folded columns, giving at
least **22,945,941,707** left/right/orientation loops in the current
root-index scheme. This is a necessary counting and loop-size gate, not a
proof that any such base covers ordinary targets. A weight-five base is one
possible source of more points, but its actual subgroup-filtered size has
not been measured here. Relative to W3's 24.1 million loops, the minimum
four-summand loop count is about 952 times larger, before storing roots or
paying for target queries. The existing N53 Rust index uses 64-bit field
words; a N83 version also needs its 128-bit path and separate resource
measurement.

## Native W3 pair-root gate

The [frozen W3 probe](n83_w3_pair_root_probe_protocol.json) checks the
necessary N83 S3 pair-root kernel before an index build. Its 16-left and
64-left [runs](runs/n83_w3_pair_root_probe_v1/receipt.json) completed; Sage
independently replayed 64 sampled roots from each as exact group sums. The
64-left kernel used 13.62 seconds of exploratory wall time. That met the
protocol's projected 240-second gate, so the separate [full 539-left
run](runs/n83_w3_pair_root_full_v1/receipt.json) executed all **24,113,243**
pair states under a 300-second external limit. It returned two roots for
every state and [64 sampled roots replayed](runs/n83_w3_pair_root_full_v1/left539_sage_replay.json)
as exact group sums. The full kernel took 197.92 seconds internal wall time,
198.18 seconds external wall time, and 83.84 seconds of child user CPU time
on a contended Mac. These timings are exploratory. The samples all occur at
the start of the enumeration, so the replay does not independently certify
every state. No searchable index or ordinary-target query was built.

## Fixed-offset search gate

The exact [offset-cost screen](runs/n83_next_offset_cost_v1.json) analyzes
one straightforward continuation of the N53 four-sum root index: try fixed,
target-independent one-point offsets for a five-summand query, or two-point
offsets for six summands, and search each residual with the same four-sum
index. For a uniform subgroup target, at most `C(B+3,4)` of `r` residuals
have a four-sum witness. A union bound therefore requires at least
`ceil(r/(2 C(B+3,4)))` distinct fixed offsets before even 50% target
coverage is possible. A failed exhaustive query scans all `83 K²` states.

| Method | Necessary offsets for 50% coverage | States per complete miss | States in preceding misses for a median target |
| --- | ---: | ---: | ---: |
| W3, six summands | 452,684 | 24,113,243 | 10,915,655,180,969 |
| W3 + 1,600 W4, five summands | 11,369 | 152,165,228 | 1,729,814,311,904 |
| W3 + 2,000 W4, five summands | 6,403 | 202,766,427 | 1,298,110,665,654 |
| W3 + 4,000 W4, five summands | 899 | 541,402,028 | 486,179,021,144 |

The existing root query makes two target S3 calls per state on a full miss;
even the 4,000-orbit option would make **972,358,042,288** such calls across
the preceding misses at this 50% counting gate. These are exact counts for
the specified fixed-offset and complete-scan scheme, **not** measured query
times or a lower bound on all possible five- or six-summand algorithms. The
existing N53 query samples one global orientation per state, so its actual
coverage can be lower than the optimistic four-sum support ceiling. The
full N83 root index, its memory, and any target query remain unmeasured.

An earlier [N83 five-summand MITM trial](../pdp-scaling/five-sum-20260928/RESULTS.md)
replayed a planted solution but found no ordinary relation on its 128-point
subset; its full 130,604-point base required 8.53 billion unordered pair
entries, above its memory cap. That is a different base and solver, not a
yield measurement for the W3/W4 hybrid. It is evidence against assuming a
plain quadratic pair table will rescue this screen.

## Decision and next gate

1. **Best geometry to investigate: W3 plus 4,000 W4 mask orbits, five
   summands.** It has a measured 423,964-point base, 2,554 folded columns,
   and a five-sum multiset ratio of 47.21. Its fixed-offset root-index path
   still has prohibitive exploratory work, so the next useful gate is a
   bounded-memory algebraic or structurally different PDP on this *exact*
   base, with planted controls and frozen ordinary public queries. A solver
   that only handles a tiny subset does not promote it.
2. **Smaller five-sum fallback: W3 plus 2,000 W4 orbits.** Its 259,458-point
   base has a lower index state count, but only 4.05 five-point multisets
   per subgroup element on average. Measure ordinary yield; that average
   cannot certify target coverage.
3. **Deprioritize W3 six-summand root-index offsets.** The full pair-root
   kernel works on sampled controls, but the fixed-offset path needs at
   least 452,684 residuals for the 50% counting gate. Revive six summands
   only with an algorithm that avoids that scan. The 294.78 multiset ratio
   alone is not a workable search method.
4. **Hold W5-style four-summand enlargement.** Its minimum root-index loop
   is about 952 times W3's before memory and query costs. A new compact or
   distributed index design would need its own measured resource gate.

These are research priorities with `candidate_id: null`, not IC speedup
claims. The next promotion gate is an independently replayed PDP pilot with
ordinary-query status mix, failed attempts, time and memory limits, and
planted controls reported separately. A complete one-target DLP and
same-point rho comparison remain downstream.

## Reproduce

Run from a checkout containing this experiment. Choose a fresh output
directory and use the repository's checked launcher for every Sage command:

```sh
mkdir -p /Volumes/SSD990/cryptanalysis/experiments/hamming-ic-e2e-20260929/runs/new-n83-next
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /Volumes/SSD990/cryptanalysis/experiments/hamming-ic-e2e-20260929/runs/new-n83-next/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/hamming-ic-e2e-20260929/sage_measure_n83_next_geometry.py /Volumes/SSD990/cryptanalysis/experiments/hamming-ic-e2e-20260929/runs/new-n83-next
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /Volumes/SSD990/cryptanalysis/experiments/hamming-ic-e2e-20260929/runs/new-n83-next/sage_runtime_info_replay.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/hamming-ic-e2e-20260929/sage_replay_n83_next_geometry.py /Volumes/SSD990/cryptanalysis/experiments/hamming-ic-e2e-20260929/runs/new-n83-next
```

Run outputs are immutable; a failed or interrupted run retains its start and
progress records and is never counted as a completed geometry result.
