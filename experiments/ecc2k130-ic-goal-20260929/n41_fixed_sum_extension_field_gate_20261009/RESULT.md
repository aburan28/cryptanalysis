# Exact fixed-sum completion solves the N41 control; extension-field F4 reaches its cap

**A target-conditioned exact lookup resolved both frozen fixed-sum N41 pair
families and independently replayed a valid eight-point row.** The positive
family `[16,5]` completed in 3.699 seconds of charged local work; the
negative family `[1,1]` was proved empty in 4.630 seconds. The matched
extension-field Gröbner formulation began search on both inputs but reached
its 45-second cap on each. This result selects exact pair completion over
extension-field F4 for this two-free-pair subproblem. The times are local
stage diagnostics without a host-isolation receipt.

## Target-linked instance and equations

The frozen public subgroup point is
`Q=(1458168294740,1672312028033)` on `y²+xy=x³+1` over
`GF(2)[t]/(t^41+t³+1)`, with subgroup order `549756390943`. The first four
factor-base points are the prefix of a previously verified public row; no
leaf in either remaining W6 pair is fixed in the methods under test. Four
raw preimages of `Q` are obtained from the subgroup preimage plus the curve's
four torsion points. The positive control's raw endpoint is index 2. After
subtracting the verified prefix, its target residual has
`z_R=1/(x(R)+1)=526562639933`. The raw endpoint, prefix, field,
rotations `[0,10,20,30]`, two sum-mask controls, source hashes, and one-worker
limits are frozen in the [core protocol](protocol.json). This is a
target-coupled method control with a fixed prefix and fixed pair seed sums;
the sum-mask controls were selected using a prior row and an exact negative
census.

For either free pair, fix the nonzero seed sum `s` and leave all six bits of
one seed `a`, the raw parity `epsilon`, and the pair output `z` unknown.
The exact pair equation is

`(1+p)z² + pz + H(s)² + epsilon = 0`, where `p=a²+sa`.

The two outputs satisfy the public residual equation

`(z₀²+z₀)(z₁²+z₁)(z_R²+z_R) + (z₀+z₁+z_R)² = 0`.

The [Sage formulation](solve.py) has 16 variables, 17 equations, and maximum
input degree four over the exact extension field. It includes all 14 Boolean
seed and parity equations. It leaves rational-leaf and distinct-column
checks to exact replay. The positive saved row evaluates to pair outputs
`[585190544792,1979731517413]`, with parities `[0,0]`; independent Sage
recomputed every equation. The negative `[1,1]` sum family has no exact
pair-group completion for the same residual.

## Bounded decisions and exact baseline

The checked Sage runtime was saved in
[sage_runtime_info.json](sage_runtime_info.json) before the cases. The
[supervisor](run_cases.py) gave each Gröbner process 45 seconds and 4 GiB,
preserved the terminal streams, and recorded sampled RSS. Both stdout files
contain `START_GROEBNER`; neither contains a terminal basis. `WALL_CAP` is a
censored solver status, not an infeasibility decision. The exact baseline's
[protocol](baseline_protocol.json) froze the same public residual, pair sums,
limits, and sources before its run. It constructs exact pair domains under
the fixed sums, uses `R-P₀` to find the required second pair, and checks all
eight folded columns and the public group sum.

| Fixed sums | Exact pair-group sizes | Extension-field F4 | F4 launcher wall | Exact completion | Exact charged interval | Exact target lookup within interval |
| --- | ---: | --- | ---: | --- | ---: | ---: |
| `[16,5]` | `32 × 28` | `WALL_CAP` | 45.024 s | verified row | 3.699 s | 0.00717 s |
| `[1,1]` | `32 × 32` | `WALL_CAP` | 45.025 s | exact domain empty | 4.630 s | 0.00110 s |

For exact completion, the charged interval includes raw leaf reconstruction
(3.690 and 4.627 seconds), fixed-sum pair construction (0.00155 and
0.00203 seconds), target lookup, and interval overhead. Field construction
and input loading precede this interval. Self RSS peaked at 265,519,104 and
265,453,568 bytes; the F4 supervisor sampled 249,954,304 and 249,856,000
bytes. These runs use one process each. No F4/exact speed ratio is assigned
because the F4 costs are censored and CPU isolation was unavailable.

The [core independent audit](audit.json) reconstructed the raw target
preimage, all eight leaf lifts, both positive pair equations, the S3 target
equation, and the empty exact negative family. The separate [baseline
audit](baseline_audit.json) replayed the found eight-point row against the
frozen factor-base input, checked eight distinct folded columns, subgroup
membership, the exact target sum, phase totals, and the negative result.
The first producer attempt is retained in
[attempt1_failure.json](attempt1_failure.json): a sandbox-denied process
census and a Sage-integer JSON serialization error stopped it before
Gröbner search. The corrected source and second frozen protocol produced
the two capped decisions above.

## N131 transfer bound and next method

For one fixed nonzero W18 seed sum, at most `2^17` unordered seed pairs
exist, and each has at most four signed raw-pair states. Thus a fixed-sum
pair contributes at most `M=2^19=524288` group outputs. If a uniform
nonidentity N131 subgroup target is independent of a fixed four-pair prefix
and of the last two fixed seed sums, those two pair families cover at most
`M²=274877906944` group values. With the frozen N131 subgroup order
`r=680564733841876926932320129493409985129`, a single prefix succeeds
with probability at most `M²/(r−1) ≈ 4.039×10⁻²⁸`. The union bound requires
at least **1,237,940,039,285,380,274,909,257,659** independently chosen
fixed prefixes before it permits 50% success, or more than
`2.063×10²⁴` complete prefixes per second within 600 seconds. This is a
support bound under the stated input law; target-guided prefixes and a joint
solver with more than two free pair blocks require separate analysis.

The next constructive test should keep at least four pair blocks free when
the public point first acts on them. The fixed-sum linear image and partial
output gate are useful only if that joint target equation produces their
seed sums and output assignments before enumerating pair leaves. A method
that fixes four pair outputs and then calls this successful local completion
cannot meet the N131 work gate even with a free completion oracle. Complete
pipeline candidate and run IDs remain null for proposal
`Q20261009192700`; the exact baseline is `Q20261009192701`.
