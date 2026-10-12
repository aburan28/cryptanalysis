# Q1520: forty complete phase-three N83 complementary scans give zero hits

The five exact-base-usable first pairs from Q1518 phase three were each
continued through all four signed complements on both frozen ordinary N83
public points. **All 40 distinct complements completed a full scan of the
30,977,592-point base and returned zero exact-base hits.** The continuation
completed 26 cells: 24 previously unattempted complements and the two that
had reached Q1518's 30-second wall cap. The earlier timeout receipts remain
part of the attempted-work history.

| Ordinary public workload | Usable first pairs | Distinct complete signed scans | Exact-base hits | Complete-scan batch multiplications, excluding inversion internals |
| --- | ---: | ---: | ---: | ---: |
| Selected `2eb250a29072` | 5 | 20 | 0 | 1,548,879,600 |
| Holdout `394256b9f901` | 5 | 20 | 0 | 1,548,879,600 |
| **Both points** | **10 pair-point cases** | **40** | **0** | **3,097,759,200 = \(2^{31.529}\)** |

The 40 complete-scan count excludes the partial arithmetic performed in the
two original timed-out attempts; their operations are unknown. Q1518's first
pair production adds 195,862 and 198,186 CNF+XOR calls for the selected and
holdout points, respectively, in a different accounting unit. The new 26
cells consumed 74.00 child user CPU seconds and 9.37 child system CPU seconds;
their summed wall time was 639.32 seconds under host contention and is an
exploratory diagnostic. Peak child RSS was 1,283,375,104 bytes. Every new
cell completed within the frozen 15-second soft CPU and 180-second wall caps.

The exact curve is `EC1N83Ckb1h876c2921cb64`. The cofactor-four normal-basis
weight-at-most-five subgroup base has **B=30,977,592** actual usable points,
**K=186,612** signed-Frobenius columns, and enumerated-set digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The stage proposal is `Q1520`, `PDP4hybrid`, with null candidate and run IDs
and `isogeny: "none"`. The [frozen protocol](protocol.json) pins the Q1518
inputs, Q1512 binary, base, Bloom settings, and caps. [Individual receipts](runs),
the [result](result.json), and the [analysis](analysis.json) preserve raw
outputs, failed attempts, CPU/wall and memory readings, and complete-scan
operation counts. [Independent replay](validate.py) reconstructs every new
complement from its first pair and public target, verifies the group-law
identity, checks raw output hashes, and reconciles all 40 unique scan keys
with Q1518's 14 original completions and two original timeouts.

These 40 deterministic, correlated complements produced **zero relation
rows and zero rank increments**. Their cost per verified relation is
censored; they do not supply a natural-yield rate for arbitrary first-pair
policies. Phase three reduced SAT calls per usable first pair by about
0.89 bits relative to phase two, but its higher usable-pair count increased
the number of full scans in this fixed eight-pair panel from 24 to 40, with
zero hits in both panels. Further mask tuning alone has no measured
relation-yield benefit here.

The N131 full-scan route still has Q1506's specified independent-uniform
first-pair relation-supply model of \(2^{123.289}\) batch multiplication calls,
**62.289 bits above an abstract \(2^{61}\) call reference**. This model is
separate from a complete charged solve estimate. Q1520's zero-row N83 panel
does not determine relation yield, final matrix work, target descent, or a
complete N131 exponent; those fields remain null. The next algorithmic gate
is a target-conditioned or indexed second-pair query that avoids a full
B-point scan, paired with ordinary N83 first pairs and novel-rank accounting.

Recheck the frozen 40-complement reconciliation with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1520_phase3_scan_completion/validate.py
```
