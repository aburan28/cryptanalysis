# N83 pair-index feasibility screen

The [exact counting ledger](pair_index_screen.json) uses the immutable
`m=7,d=12` and `m=8,d=11` shifted geometry receipts. `B` is the actual
usable subgroup-point count in each labeled slot before orbit folding.
All arithmetic is integer or high-precision decimal; no solver yield or
runtime is inferred from the counts.

| Geometry | `B` per slot | One distinct-slot pair entries `B²` | Remaining-summand average tuples per uniform target `B^(m-2)/r` | Fixed prefixes necessary for 50% coverage | Full seven/eight-sum average `B^m/r` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seven summands | 4,036 | 16,289,296 | 0.000000442921 | 1,128,870 | 7.21487 |
| Eight summands | 2,018 | 4,072,324 | 0.0000279317 | 17,901 | 113.747 |

For a uniformly chosen subgroup target after fixing one pair, the chance
of **any** decomposition into the remaining factors is at most the
remaining-summand average in this table. A union bound then makes the
listed number of distinct **fixed, target-independent** pair prefixes
necessary for even 50% coverage of a uniformly chosen subgroup target.
This necessary-count bound does not assume independent probes; it does
not apply to adaptive pair selection using the target. Under the additional
independent-occupancy approximation, first success would take about 2.26
million pair probes for seven summands or 35,802 for eight. Those expected
first-success counts are **heuristics**, not measured query counts or lower
bounds for one fixed point. Every failed and timed-out residual solver
attempt would still be charged to the target.

For the eight-summand proposal, a raw 16-byte record for each pair gives
65,157,184 bytes for one pair table before indexing or allocator overhead.
A conventional balanced four-pair join must combine two pair lists of
`B²` entries each. Their unfiltered pair-of-pair space is `B⁴ =
16,583,822,760,976` states, or about 199 TB even if each state used only
a 12-byte compressed group point. Under a uniform `t`-bit filter, the
expected number of surviving full representations is `(B⁸/r)/2^t`.
The largest `t` retaining at least one expected representation is 6.
That leaves about 259,122,230,640 intermediate states and **3.11 TB** of
raw 12-byte point payload, roughly 1,448 times the declared 2 GiB cap.
Streaming may trade memory for time; these conditional figures do not
exclude every possible four-list algorithm. They do reject treating the
65 MB first-pair table as the complete cost of a standard balanced join.

The viable question is narrower: can a public pair prefix make a
six-summand residual decomposition cheap enough that tens of thousands of
failed prefixes are affordable? The [long unpinned planted pilot](long_sat_protocol.json)
first measures the same eight-summand witness-search circuit with a larger
cap. A six-summand residual pilot would then need a pinned-pair planted
control, ordinary public pair probes, all four raw fibers, exact base
membership checks, and per-attempt wall/RSS accounting. Its construction
and result must remain separate from the pair-table storage model.

There is no measured N83 target scalar, factor-log matrix, same-point rho
solve, or online speedup. The exact `sqrt(r)` operation scale in the ledger
is not a rho wall-time baseline. All primary one-target costs remain unknown.
