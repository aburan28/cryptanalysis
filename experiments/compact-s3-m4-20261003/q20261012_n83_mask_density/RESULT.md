# Q1491: leaf-mask density sweep samples 40 distinct N83 S3 pairs

A frozen 40-mask sweep exposed 40 distinct first-pair assignments on an
ordinary N83 public point. Exact S3 replay found two middle roots for 16 of
them. The eight masks with 166 of 332 leaf polarities flipped gave the lowest
observed work per two-root pair: **759,924 combined CNF/XOR calls for five
two-root pairs, or 151,985 calls per two-root pair**. On the second ordinary
point, those same eight masks consumed 778,516 calls, or 155,703 per
two-root pair. All 48 attempts terminated at the first-pair marker.

| Flipped leaf variables | Selected attempts | Distinct pairs | Two-root pairs | Selected combined calls | Calls per two-root pair |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 17 | 8 | 8 | 3 | 727,592 | 242,531 |
| 42 | 8 | 8 | 1 | 706,818 | 706,818 |
| 83 | 8 | 8 | 3 | 731,926 | 243,975 |
| **166** | **8** | **8** | **5** | **759,924** | **151,985** |
| 249 | 8 | 8 | 4 | 778,598 | 194,650 |

The frozen rule selected the 166-flip setting by minimizing total selected
calls divided by exact two-root pairs, then ran its eight masks on the
holdout point. All eight holdout first-pair assignments matched the selected
ones, and five had two roots. Q1488's previous nine-mask schedule used
880,988 selected calls for five two-root pairs (176,198 per pair); the new
selected schedule used 13.7% fewer calls per observed two-root pair. The
holdout comparison was 155,703 versus 180,147 calls per observed two-root
pair, 13.6% lower. These are exact counter ratios for the tested schedules,
not isolated CPU wall-speedup measurements.

The [root-work receipt](root_work.json) charges the exact S3 replay for every
sample separately from solver calls. The 166-flip selected and holdout groups
each used 773 CountedOnb public field API entries over eight first pairs,
or 154.6 entries per two-root pair. These entries include input conversion,
the S3 root query, and output conversion. CNF/XOR calls and field API entries
are different units and are not added into a claimed solve exponent.

With eight masks per density, the root fraction is imprecise. The 5/8 result
has a 95% Wilson interval of approximately 0.306–0.863; the 3/8 groups have
intervals of 0.137–0.694. The holdout point repeats the same pair assignments
and therefore does not supply an independent root-rate replicate. A fresh
mask-seed family is needed before attributing the 166-flip ranking to the
density rather than seed variation.

The subsequent [exact base audit](../q20261012_n83_pair_base_audit/RESULT.md)
found that only eight of these 40 first pairs have both leaves in the usable
factor base. The 249-flip group has three usable pairs, while 166 flips has
two. For a usable-pair objective, the measured first-pair costs are 259,533
and 379,962 combined calls per usable pair, respectively. The initial
two-root ranking is therefore superseded for choosing a decomposition
search setting.

## Method and records

The curve is `EC1N83Ckb1h876c2921cb64`. The normal-basis weight-at-most-five
factor base has 30,977,592 actual usable points and 186,612 signed-Frobenius
folded columns. This is a `PDP4sat` stage proposal, Q1491, with null IC
candidate and run IDs and `isogeny: "none"`.

The [protocol](protocol.json) fixes five mask counts, eight seeds per count,
two ordinary workloads, the first-pair stop boundary, caps, and the promotion
rule. The [freeze](freeze.json) hashes the source, exact masks, parent binary
source, and input formulas before measurement. The [driver](sweep.py) extends
the Q1488 WDSat mask switch without changing search decisions inside a mask.
Each [run receipt](runs) retains its input and binary hashes, exact CNF/XOR
counters, first-pair bits, process status, and exploratory wall/CPU time.
The [analysis](analysis.json) replays every pair's exact S3 roots and checks
the holdout identities. The [validator](validate.py) checked 40 selected and
eight holdout attempts. The solver wall sum was 224.496 seconds on an
unisolated host; it is not a controlled speedup ratio.

Two setup errors were preserved: the initial Makefile output-path mismatch in
[pre_driver_failure.json](pre_driver_failure.json), and a later driver-only
assertion about leaf weight in [failed_revision1](failed_revision1). Neither
was a solver failure. The final freeze removed the unsupported weight
assertion and independently replayed the actual leaves and roots.

## Next measurement and challenge distance

Continue each two-root pair with the target-dependent balanced-S3 equations
for the remaining two leaves, charging unsuccessful continuations as well as
successes. A fresh seed batch should compare the 17-, 166-, and 249-flip
settings to check whether root-positive work is stable. This stage has not
yet measured a full four-point decomposition, useful-relation yield, or
novel rank. The fully charged N131 one-target work exponent and gap to
`2^61` remain null. The separate Q1462 conditional weight-seven full
pair-index model is `2^86.1847` counted pair additions, 25.1847 bits above
an abstract `2^61` pair-addition cap in a different unit.

    env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_n83_mask_density/validate.py
    env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_n83_mask_density/root_accounting.py
