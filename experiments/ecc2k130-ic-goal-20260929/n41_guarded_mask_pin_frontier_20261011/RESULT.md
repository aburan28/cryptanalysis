# Source-mask pin frontier of the guarded W9 public-point circuit

**The guarded N41 W9 solver reaches its cap even when all eight source masks are fixed to an exact valid decomposition.** Five 20-second solver-limit cases with 8, 6, 4, 2, and 1 known masks fixed all reached their 25-second parent stop with active search. A separate all-eight-mask case under the full 120-second solver and 125-second parent limit also remained `BOUNDED_UNKNOWN`, with 788 active restart lines. The full-formula assignment control for those masks passes, so these runs isolate a hard pair/middle-coordinate search inside this SAT representation; choosing the source masks is not its only cost.

## Frozen instance and pin policy

The comparator is the committed [guarded W9 circuit](../n41_branchfree_s3_20261011/RESULT.md) on `EC1N41Ckb1h023d9a38bbf7`, public point `(1458168294740,1672312028033)`, transported point `(920359962848,755404565011)`, actual factor-base size **B=2,072**, and 251 folded columns. All four raw public-target preimages remain enabled. The first `k` of the eight nine-bit source masks are fixed to the archived independently checked witness; all remaining masks, four pair-output coordinates, two middle coordinates, and two target flags stay free. The earlier four-branch assignment check passes every clause and native XOR row at the witness setting. These pins make the cases satisfiable controls, not ordinary public-point searches.

The [short protocol](protocol.json) froze the exact formula source, solver binary, target, witness masks, `k∈{8,6,4,2,1}`, one worker, 4-GiB combined RSS, a 20-second CryptoMiniSat limit, and a 25-second parent stop before running. It constructs the same guarded query formula once, adds only the appropriate mask unit clauses for each case, and records the serialized formula hash, logs, phases, and memory. Construction took 0.647 seconds outside all five solver intervals; the complete five-case local wall was 126.171 seconds.

| Fixed source masks | Pinned bits | Solver interval | Active restart lines | Peak combined RSS | Status |
| ---: | ---: | ---: | ---: | ---: | --- |
| 8 | 72 | 25.088 s | 382 | 60,669,952 B | `BOUNDED_UNKNOWN` |
| 6 | 54 | 25.128 s | 412 | 64,356,352 B | `BOUNDED_UNKNOWN` |
| 4 | 36 | 25.113 s | 194 | 68,239,360 B | `BOUNDED_UNKNOWN` |
| 2 | 18 | 25.109 s | 185 | 68,960,256 B | `BOUNDED_UNKNOWN` |
| 1 | 9 | 25.063 s | 155 | 90,390,528 B | `BOUNDED_UNKNOWN` |

The [matched-cap protocol](long_pin8_protocol.json) independently froze the eight-mask positive case with `--maxtime=120` and a 125-second parent stop. Its [receipt](long_pin8_result.json) reports `BOUNDED_UNKNOWN` at 125.182 solver seconds, 788 restart lines, and a memory peak below the 4-GiB cap. This is the direct comparison to the unpinned guarded public-query cap, which also ended bounded after 125.057 solver seconds. All timings are exploratory local diagnostics on an unisolated host; a cap is censored solver evidence, not a satisfiability decision.

The [terminal audit](audit.json) binds both frozen protocols to the executed source and solver, confirms each pin count and clause total, checks exact target equality with the guarded query, validates phase and RSS bounds, and rehashes every compressed stdout/stderr log. All six logs show active solver restarts without a terminal SAT or UNSAT line. This is a component study with `candidate_id: null`.

## Method decision

Analytic root elimination must replace the free intermediate S3 variables before more source-mask branching can help this representation. The existing [exact fixed-mask predicate](../N41_W6_S8_FIXED_MASK_TARGET_RESULT.md) shows how to solve those roots once masks are specified; the missing operation remains a target-conditioned way to select or eliminate many still-free source-mask families together. The next experiment should put an exact root or resultant operator behind a family-level constraint and charge every failed family, then run an unpinned N41 relation gate before any N131 promotion.
