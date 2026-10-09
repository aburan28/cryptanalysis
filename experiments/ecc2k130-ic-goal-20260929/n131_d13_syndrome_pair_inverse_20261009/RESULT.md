# Sparse dual checks for the exact N131 d13 pair inverse

**Eight exact parity checks per seed sum rejected 1,044,364 of 1,048,448
sum/output trials before pivot solving, while preserving every pair result.**
The matched query median fell from 6.777 ms for the linear-batched inverse
to 3.683 ms with the checks, a 1.84× paired median ratio in this exploratory
run. This is the second measured iteration of the same exact pair primitive.

For a fixed nonzero seed sum `s`, the source index stores 12 independent
131-bit pivot vectors spanning `Im(L_s)`. A binary mask `h` is a valid
check when its parity dot product with every pivot vector is zero. Then
`h·R_s(z)=1` proves that the proposed `z` cannot arise from any valid pair
with that sum. The builder groups coordinate positions by their 12-bit
pivot signature and constructs masks of weight one, two, or three whose
signatures XOR to zero. It selects eight independent masks for every one
of the 8,191 sums. A passing right-hand side still goes through the exact
pivot solve and selector checks.

This construction is lossless: every element of `Im(L_s)` is a binary sum
of the 12 pivot vectors, so all eight parity checks vanish on every
genuine pair right-hand side. The [frozen protocol](protocol.json) uses the
same 64 output masks and two repetitions as the [first iteration](../n131_d13_batched_pair_inverse_20261009/RESULT.md), with alternating method
order. The [run receipt](result.json) includes every query, rejection and
solve count, exact output set, setup time, and process RSS. The
[independent audit](audit.json) checked all 65,528 masks against all
corresponding pivot vectors, tested rank eight in Sage for ten seed sums,
and matched all 64 output sets to the earlier independently replayed run.

| Measured stage or exact count | Observation |
| --- | ---: |
| Dual construction, target independent | 1.581 s |
| Mask weights 1 / 2 / 3 | 329 / 17,219 / 47,980 |
| Compact payload at 17 bytes per mask | 1,113,976 B |
| Sum/output trials in 128 complete queries | 1,048,448 |
| Rejected before pivot solving | 1,044,364 (99.610%) |
| Pivot solves retained | 4,084 |
| Linear-batched query median, 10th–90th percentile | 6.777 ms, 6.708–11.046 ms |
| Eight-check query median, 10th–90th percentile | 3.683 ms, 3.626–6.879 ms |
| Paired linear/eight-check ratio median, 10th–90th percentile | 1.840×, 1.215–2.207× |
| Peak process RSS | 48,447,488 B |

All 32 source positive outputs retained their pair; all 32 uniform field
controls yielded the same sets as the complete inverse. The compact
payload is the exact byte count for storing eight 131-bit masks per sum;
the measured run built the masks in memory before the query interval.
The host has no CPU isolation receipt, so the timing ratio is a stage
diagnostic. Candidate and run IDs remain null until a complete IC method
is specified.

The useful next test is target-coupled propagation: bring two or more
same-rotation pair domains into a joint N41 public-target solver, use these
exact dual checks on candidate intermediate outputs, and measure how many
partial states the target eliminates *before* either pair is fully chosen.
Only a method that supplies such compatible outputs cheaply can transfer
the pair-inverse gain to the N131 six-pair relation search.
