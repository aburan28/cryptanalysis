# Packed-row candidate: local validation

The candidate passes all 15 test groups, all 4,368 direct matrix controls and the
92-record frozen query preflight. Bases, proof graphs, Boolean completion and
integer producer/checker traces match the reference. The query panel contains
20 verified complete PDP queries, 20 verified algebra controls and 52 retained
work-budget failures. Independent replay checks seven distinct query proofs,
the solved curve controls, direct matrix proof/row-space equality, and 182
source/resource/generated/binary bindings. Eight shared libraries and six native
control executables were built locally, including UBSan variants.

| Input | Result | Largest packed row | Matrix XORs | Word XORs | Peak live coefficient payload |
| --- | --- | ---: | ---: | ---: | ---: |
| PDP 6, seeds 1, 2, 4, 5 (each) | Verified complete query | 1 word | 4,074 | 4,074 | 58 words |
| PDP 6, seed 3 | Verified complete query | 1 word | 1,096 | 1,096 | 56 words |
| Random 8-variable control | Verified algebraic basis | 4 words | 101,512 | 230,200 | 752 words |
| Dense MQ, 21 variables | Work-budget failure | 25 words | 3,192 | 77,232 | 10,125 words |

Every matrix XOR still emits the same proof witness. Packing removes the
term-by-term symmetric-difference merge from eligible rows; a one-word row still
requires pivot bookkeeping, work accounting, a popcount and witness handling.
The word counts are diagnostics, not instruction counts or timing speedups. The
failed dense case is not a solve. The largest live packed coefficient payload
in the frozen panel was 10,125 words (81,000 bytes), not total peak process memory.

The frozen local timing attempt admitted zero queries. One-minute load was
68.7939 against the unchanged 14-CPU threshold; two admissions were rejected and
31 trials remained unrun. The machine was a physical Apple M4 Pro running macOS
26.6 and Python 3.13.1. No local complete-query speedup or 2x claim is made, and
no automatic dispatch change is justified by this result.

Two setup failures are retained. A clean child checkout revealed that the
round 61 frozen plan had been excluded by a broad JSON ignore rule; its exact
measured bytes were then committed as 7f0caf09 before continuing. The partially
generated round 62 build consequently had no plan and stopped before tests. A
subsequent test-discovery attempt found that prepending the leased-input module's
directory to sys.path shadowed this round's test_panel module. Appending that
lookup path fixes discovery; all final checks pass. The failures and source
snapshots are retained with the final evidence.

The compact artifacts in `results/` preserve the plan, measurements, native
control records, independent audits and final source snapshot. The full external
archive retains rebuilt native binaries. Packaging checks require every bound
source, including the plan, to be tracked before publication.
