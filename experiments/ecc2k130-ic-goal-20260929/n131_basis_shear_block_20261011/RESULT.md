# Exact N131 W15 block sizes the basis-aware sheared quartic transfer

One **four-atom arithmetic block** on the exact N131 challenge
field accepts the archived W15 witness and emits **216,341 AND gates,
349,088 variables, 649,285 CNF clauses, and 132,425 native-XOR rows**.
Its 47 quartic field-multiplication calls include **45 generic dense
products and two sparse products**. The entire earlier direct N131 W15
six-pair control used 77,021 AND gates. This exact construction result
directs the next method step away from merely replicating the quartic
arithmetic across three N131 blocks: source-basis sparsity that helped
at N41 largely disappears at degree 131.

The curve is `EC1N131Ckb1heb5f1998f20b`, `y²+xy=x³+1` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`. The [worker](worker.py) builds two W15
source pairs at rotations `26,39` using four free 15-bit masks, two free
131-bit field vectors for output `Z` and branch witness `w`, the exact
`T=S+Z`-sheared quartic `A+wB=0`, and the Artin--Schreier relation
`w²+w=S+Z`. Its 29-diagonal pair products retain their rotated source
bases. The archived masks `[5576,8382,3,13685]`, output, and branch
witness are used **only in the assignment check after construction**;
the formula leaves those wires free. That complete assignment satisfies
every emitted CNF and native-XOR row, and its decoded `a,S,P,Q,A,B`
matches the independently archived N131 arithmetic control.

This component deliberately omits factor-base support clauses, distinct
folded-column constraints, the nonzero-output guard, the other eight source
masks, and public-target joins. Its size is therefore an arithmetic-block measurement, not a
complete N131 relation-query formula or a bound on solver work. The
[protocol](protocol.json) froze all executed source and input hashes,
one worker, a 120-second parent wall cap, and 4 GiB RSS before execution.
The [run receipt](run_result.json) records successful exit in 2.341 seconds
including process launch, with 241,909,760 bytes sampled peak RSS. The
[worker receipt](worker_result.json) separates 1.315 seconds of arithmetic
construction from 0.740 seconds of full assignment and constraint checks.
Those local wall times are exploratory; the exact circuit counts and
assignment result are deterministic. The [audit](audit_result.json)
checks source hashes, parent cap, logs, archived witness values, and the
77,021-gate direct-circuit reference.

The immediately useful N131 path remains a target-conditioned partial-output
or seed-family rejection step, followed by a complete unpinned ordinary
relation query under the one-worker, 600-second, 4-GiB cap. Relation yield,
useful rank, factor logs, fresh-target scalar recovery, and paired one-target
rho timing remain later full-pipeline gates; `candidate_id` is `null`.

Reproduce this non-Sage component with `python3.12 -B run.py freeze`,
`python3.12 -B run.py execute`, and `python3.12 -B verify.py` from this
directory.
