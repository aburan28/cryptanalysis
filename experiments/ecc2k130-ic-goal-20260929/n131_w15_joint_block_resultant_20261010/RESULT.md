# Joint block-output eliminant and dual-product N41 screen

The exact upper S3 equation joins two rotated four-atom resultants before
their output points or source masks are chosen. On a frozen N41 public-point
control, enumerating both unrestricted 1,024-family block product domains
produced **962** and **842** algebraic output entries. Their target-conditioned
join retained **one** output pair across all four raw-target branches.
Independent mask/sign reconstruction replayed that pair to one verified
12-distinct-column group relation. A constructed N131 W15 witness satisfying
the **eight-offset** policy independently replayed a degree-one joint GCD on
its matching branch and degree-zero GCDs on the other three.

## Exact joint condition

For block output reciprocal coordinates `z_A,z_B` and target residual
reciprocal coordinate `r`, the binary-curve S3 relation is

```text
U(z_A,z_B,r) = (1+z_A²z_B²)r² + z_Az_Br + (z_A+z_B)² = 0.
```

Let `H_A(z_A)` and `H_B(z_B)` be the frozen 266-term rotated four-atom
resultant specialized at each block's common seed and two products. Then

```text
K_B(z_A) = Res_{z_B}(H_B(z_B), U(z_A,z_B,r))
gcd(H_A(z_A), K_B(z_A)) != 1
```

is necessary for a compatible pair of block outputs. `deg H_A,deg H_B <= 8`
and `deg K_B <= 16`. This condition is exact algebraic elimination;
any surviving roots still undergo source-column and elliptic-curve replay.

## Frozen controls and measured stages

The N41 field is `GF(2)[t]/(t^41+t³+1)` on `y²+xy=x³+1`, with subgroup
order `549756390943`, W6 source `B=384`, and `K=26` folded columns.
The public point is `(1458168294740,1672312028033)`. The first two free
pairs and block seeds `4,7` were fixed from its archived verified relation;
both remaining blocks' product families were unrestricted in the dual screen.
The [dual protocol](dual_protocol.json) froze the runtime and sources before
the [screen](dual_result.json). The [source replay](replay_result.json)
reconstructed masks and all four sign bits per block from the surviving
products and verified the full group sum and 12 distinct columns without
using the archived constrained-block masks or signs as search inputs.

| N41 stage, one worker | First block | Second block | Four-branch join |
| --- | ---: | ---: | ---: |
| Product families | 1,024 | 1,024 | — |
| Algebraic output entries | 962 | 842 | — |
| Measured wall time | 4.544 s | 4.474 s | 4.057 s |
| Compatible output pairs by raw branch | — | — | `0, 0, 1, 0` |
| Verified full source replays by raw branch | — | — | `0, 0, 1, 0` |

The earlier [fixed-second-block screen](screen_result.json) checked all
1,024 first-block product families in each branch and retained `0,0,1,0`.
Its per-branch GCD screen costs were 7.123, 6.605, 5.883, and 6.367 seconds.
The [joint control receipt](receipt_v2.json) records a 6.753-second parent
run and 272,121,856-byte peak child RSS for the N41 and older N131
fixed-product panels together. These CPU timings were taken on an
unisolated host and are stage diagnostics.

For N131, the field is `GF(2)[t]/(t^131+t^13+t²+t+1)` with subgroup order
`680564733841876926932320129493409985129` and W15 source
`B=197,292`, `K=16,381`. The new [constructed control](restricted_result.json)
retains the first eight archived raw leaves and chooses the last four with
distinct folded columns and seed offset `3`. Its constructed public point is
`(653871031646478754012210499659674147866,
1889913704381273943030301406319481239163)`. The
[independent Sage replay](restricted_audit_result.json) verifies source
atoms, all 12 columns, subgroup projection, four raw branches, both block
resultants, and joint GCD degrees `0,0,1,0`. The older archived N131
constructed control used offset `14070`; its initial policy-assertion
[failure](failure_v1.json) and corrected [panel](result.json) remain
separate records.

## W15 work gate and continuation

For one nonzero W15 seed, each pair-product image contains `2^14` values,
so each four-atom block has `2^28 = 268,435,456` product families. A direct
dual enumeration therefore processes `536,870,912` families before joins.
The measured N41 build-and-factor rate was **4.403 ms per family**;
transferring that smaller-field rate gives **2,364,026 seconds** for just
the two N131 block enumerations. To fit 600 seconds, an implementation would
need at most **1.118 µs per family**, including both blocks and excluding
the free-pair search. This is a diagnostic projection, not a lower bound.
The [terminal audit](terminal_audit.json) binds the rates and all frozen
inputs.

The next algorithmic step is a target-conditioned compressed join over the
two `2^14`-dimensional product spaces that never materializes either
`2^28` output family. Test it with the first two free pairs and seeds
unfixed on the N41 public point, then require a source-bound N131 work and
RSS projection within one worker, 600 seconds, and 4 GiB before promoting
to the frozen N131 public query. The complete IC pipeline retains
`candidate_id: null` until that gate, relation rank, target descent, and
single-target online accounting are available.
