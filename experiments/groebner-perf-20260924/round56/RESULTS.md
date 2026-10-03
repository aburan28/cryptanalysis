# Observations and scope

These results compare the same 23 frozen round13 inputs with a 20-million-unit
producer budget, 500,000 proof nodes, 4,096 rows, batch 64, 20 million independent
checker work units and two million retained terms. They are deterministic charged
producer-work observations, not elapsed-time speedups. Work units include the
new criterion and selection bookkeeping. Failed attempts remain inconclusive.

| Frozen control | Prior | Chains only | Filtering only | Chains + filtering |
| --- | ---: | ---: | ---: | ---: |
| PDP 6 variables, seeds 1/2/4/5, each | 646,360 | 337,137 | 482,100 | 240,064 |
| PDP 6 variables, seed 3 | 164,676 | 109,754 | 115,130 | 72,594 |
| Pair products, 21 variables | 5,830 | 6,470 | 4,965 | 5,605 |
| Pair products, 32 variables | 12,965 | 14,472 | 10,960 | 12,467 |
| Pair products, 64 variables | 47,245 | 51,344 | 39,920 | 44,019 |
| Free variables, 64 variables | 223 | 235 | 198 | 210 |
| Random 8-variable budget control | budget exhausted | budget exhausted | 16,756,492 | 8,725,777 |

All successful bases agree and pass both independent checkers. The combination
uses 2.69 times less charged producer work in the four first-row controls and
2.27 times less in seed 3. Identical work counts in multiple fixtures are not
independent performance replications. The newly solved random control is a
coverage improvement within this budget; the failed baseline provides no
verified wall-time speedup denominator.

All five 9-variable PDP controls, all five 12-variable PDP controls, and the
three planted dense-MQ controls remain inconclusive at the same budget. Filtering
does not eliminate high-degree growth. More matrix batches before exhaustion are
not a solved-instance performance claim.

The exact-trace phase audit attributes 87.99–91.26% of charged producer work in
the prior 12-variable controls to normalization/installation of matrix output
rows. These are work fractions, not sampled CPU-time fractions. Chain probes
alone barely change those cases. Deferring tails alone passes correctness but
regresses on every solved control; for example, the 64-variable pair-product
control rises from 47,245 to 189,533 units. The negative variants are retained.

The next performance gate is a frozen paired comparison of complete queries,
including independent certification and curve replay, on a qualifying host.
Library loading and reusable ring layouts stay outside that interval. Failed
attempts, ordering, load, source/binary bindings and paired uncertainty must be
retained. No wall-time, worldwide-ranking, F5, F6-asymptotic or full IC speedup is
claimed by this PR.

## Retained local evidence

The frozen run on macOS ARM64 passed all ten unit groups, six direct probe
controls and 672 recorded algebra/query rows: 260 verified and 412 inconclusive.
The portable audit replayed 11 distinct successful proofs and checked 326
source/generated/binary bindings. Repeated equivalent certificates were replayed
once, while every result row was still checked for membership in the frozen
case/variant grid, status, counters and expected sanitizer parity.

`results/index.json.gz` hashes the retained screens, complete-query controls,
independent audit, build receipts, exact source snapshot and unit logs. Round55's
results include the exclusive phase profile and direct probe controls. Rebuilt
native binaries are retained externally with the local run and in CI artifacts;
they are not committed or reused as another platform's validation.
