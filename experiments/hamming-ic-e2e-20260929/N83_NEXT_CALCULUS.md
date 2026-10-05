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

## Decision and next gate

1. **First pilot: W3, six summands.** It keeps the smallest measured base and
   the smallest pair-index loop among the methods whose multiset count clears
   the necessary gate. Build a bounded N83 point-decomposition feasibility
   run with planted correctness controls and frozen ordinary public queries.
   The principal risk is the extra two-summand search beyond the pair index;
   the 294.78 ratio gives no algorithm or yield guarantee.
2. **Backup: W3 plus 1,600–2,000 W4 mask orbits, five summands.** Its exact
   base clears the counting gate with one fewer summand. The pair-index loop
   is 6.3–8.4 times W3's, so measure memory and solver cost before building
   a full relation matrix. The 1,000-orbit prefix remains below the counting
   gate for direct ordinary targets.
3. **Hold: W5-style four-summand enlargement.** Its minimum index loop is
   orders of magnitude larger than either measured option. Reconsider only
   with a materially different, bounded-memory index or a new structural
   reduction, not by copying the N53 root table.

These rankings are research priorities, not IC speedup claims. The next
promotion gate is an independently replayed PDP pilot with ordinary-query
status mix, failed attempts, time and memory limits, and planted controls
reported separately. A complete one-target DLP and same-point rho comparison
remain downstream.

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
