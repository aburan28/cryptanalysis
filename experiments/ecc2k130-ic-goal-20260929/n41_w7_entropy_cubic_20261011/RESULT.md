# N41 four-window cubic source-width experiment

The exact N41 transported-point circuit accepted full eight-slot assignments at source widths 7, 8, and 9. Independent binary-field enumeration confirms 504, 1000, and 2072 distinct subgroup-usable factor-base points across the four signed Frobenius windows. The three public-point searches all reached their solver cap with active search; widening this source alone therefore did not produce a relation within the tested 120-second solver budget.

## Method and frozen input

The fixed public point was `(1458168294740, 1672312028033)` on `EC1N41Ckb1h023d9a38bbf7`; the transported point was `(920359962848, 755404565011)`. Each width used the same eight-slot halftrace-cubic circuit and rotations `0,0,10,10,20,20,30,30`. The source scans enumerated rational masks for each width. The controls fixed an exact known eight-slot assignment, whereas the public-point queries left source masks unpinned. Each query used one CryptoMiniSat worker, a 120-second solver limit, a 125-second parent limit, and a 4-GiB RSS cap. The local checked Sage runtime receipt was saved before each source scan. The source and input hashes, precise phase times, logs, and resource observations are in each width's `protocol.json` and `query/query_result.json`.

| Width | Rational masks per window | Actual factor-base points `B` | Folded columns | Distinct-column pairs per window | Control | Public query | Solver time | Peak combined RSS |
| ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: |
| 7 | 63 | 504 | 57 | 7,784 | Full assignment passed | `BOUNDED_UNKNOWN` | 125.154 s | 111,771,648 B |
| 8 | 125 | 1,000 | 117 | 30,952 | Full assignment passed | `BOUNDED_UNKNOWN` | 125.169 s | 263,946,240 B |
| 9 | 259 | 2,072 | 251 | 133,596 | Full assignment passed | `BOUNDED_UNKNOWN` | 125.193 s | 94,388,224 B |

The source-width increase multiplies the raw four-pair group-wide count `pair_count^4/r` from about 6.68 thousand to 1.67 million to 579 million for subgroup order `r=549756390943`. These are combinatorial means before fixed-target conditioning, shared-column constraints, or SAT search costs; they are not measured relation yields. The solver logs show 955, 1,571, and 721 active restart lines, respectively. The bounded statuses provide no satisfiability decision.

`geometry_audit.py` independently performs GF(2^41) arithmetic, checks each projected point against the curve, applies the four Frobenius rotations and signs, and counts the union. Its `geometry_audit.json` reports zero cross-window duplicates at all three widths. `audit.py` binds that count to frozen geometry and query receipts, checks complete positive assignments, solver start and capped status, log hashes, and recorded phase and RSS bounds. Run `python3 -B experiments/ecc2k130-ic-goal-20260929/n41_w7_entropy_cubic_20261011/geometry_audit.py` followed by the analogous `audit.py` command to replay these checks. This experiment has `candidate_id: null`, since its relation and recovery stages are not a complete IC pipeline.

## Next experiment

Prioritize a target-coupled constraint that rejects incompatible partial-sum families before enumerating their pairs. Keep this width sweep as the support and cost control: on the same fixed N41 public point, test whether a new exact constraint changes the solver's accepted relation count and search work under the same worker, time, and memory limits. Any returned relation must be replayed from eight subgroup points with distinct folded columns before promoting it to the N131 public-point gate.
