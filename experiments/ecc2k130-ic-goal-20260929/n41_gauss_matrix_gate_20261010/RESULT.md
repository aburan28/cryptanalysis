# Enlarged Gaussian matrices do not pass the N41 positive control

Allowing CryptoMiniSat to use all five native-XOR Gaussian matrices in the
archived N41 output-fixed public-point circuit produced **no model within
the matched 20-second cap**. The baseline accepted one matrix and the tuned
run accepted five; both ended with `CENSORED_TIME` after active search.
The unpinned public query stayed behind the frozen positive-control gate.
This result selects stronger nonlinear pair-domain propagation over a
matrix-size-only change for the N131 coupled six-pair circuit.

The [protocol](protocol.json) fixes the same projected XCNF, solver binary,
one worker, cap, target point, source hashes, and run order for both controls.
It uses `EC1N41Ckb1h7d5e80d3c4d0`, the public point
`Q=(1458168294740,1672312028033)`, and the W5 five-pair source with
`B=170` usable points and `K=14` folded columns. The formula is the
previously checked output-fixed projection of a known satisfiable
public-point assignment. The baseline retains the archived
`--threads=1 --xor=0 --printsol=1 --random=20261010` flags; the tuned
arm adds `--maxmatrixrows=2000 --maxmatrixcols=5000
--autodisablegauss=0 --gaussusefulcutoff=0`. Each solver received its
own `--maxtime=18` guard inside a 20-second parent cap and 4-GiB RSS cap.

| Frozen output-fixed control | Baseline | Enlarged Gaussian matrices |
| --- | ---: | ---: |
| Matrices accepted at initial search | 1 | **5** |
| Raw oversized-column messages | 16 | 0 |
| Logged search restarts | 860 | 601 |
| Parent wall | 20.066615 s | 20.060439 s |
| Sampled solver RSS peak | 32,964,608 B | 78,446,592 B |
| Status / model lines | `CENSORED_TIME` / 0 | `CENSORED_TIME` / 0 |

The [independent log and receipt audit](audit.json) checks the formula,
binary and protocol hashes, exact caps, raw statuses, and matrix counts.
The frozen runner's `too_large_matrix_messages` field missed
CryptoMiniSat's word `columns`; the audit counts that wording directly
from the retained [baseline](baseline_all_fixed/solver.stdout.txt) and
[tuned](gauss_all_fixed/solver.stdout.txt) logs. Both logs show active
search and no SAT or UNSAT line. The timings are exploratory on an
unisolated host; this gate compares status and accepted matrix counts,
not a controlled CPU speed ratio. `candidate_id` remains `null`.

The [N131 coupled formula](../n131_w14_coupled_sixpair_sat_20261010/RESULT.md)
has native-XOR components far larger than the five N41 matrices. This
N41 positive-control result supplies no basis to spend a 600-second
published-point query merely by raising its Gaussian size limits. A
successor should propagate finite pair-image or seed-sum constraints
jointly with the target while several pair blocks remain free, measure
whole-family rejection on the unpinned N41 point, and then give a
source-bound 4-GiB/600-second N131 projection before the public query.
