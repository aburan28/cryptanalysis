# The fixed-witness Q1420 x-coordinate search frontier lies between 16 and 32 released bits under a fixed conflict cap

On each of the source and degree-263 descendant W24 circuits, at both the
first and last S3 leaf positions, all width-1/4/8/16 x-coordinate releases
returned `SAT_VERIFIED_GROUP`. All width-32/64/96/131 releases ended
`BOUNDED_UNKNOWN` under the frozen 20,000-conflict and 30/40-second wall
guards. The [independent audit](runs/R1/audit.json) rebuilt every input and
checked all 16 SAT models against the complete native-XOR XCNF and the exact
signed group sum. This identifies a reproducible **search-budget frontier**
in the leaf x equations even while all selectors, inverse-coordinate words,
other leaf x words, and S3 intermediates are fixed. It does not establish
that wider cells lack satisfying assignments: the archived positive witness
supplies one for every width.

The precommitted [protocol](PROTOCOL.md), [source record](source.json), and
runner/auditor are commit `477245bad177af34beafebcc1fca9738da855888`;
the 32 unit deltas and complete formula SHA-256s were frozen in commit
`367c69846751b2738231ce6af4811e45e8b4e954` before solver launch.
The source is `EC1N131Ckb1h136f03e58c98`; the oriented degree-263
descendant is `EC1N131Cbinh833014327b07` on route
`IW1E263d1hadee4e69fa3d`. Each checked fourfold W24 policy has
`B=16,772,828` distinct subgroup-usable points before sign folding.
The six-distinct finite witness, base XCNFs, named-input maps, and
CryptoMiniSat 5.14.7 binary are pinned by SHA-256 in `source.json`.
All 32 cells use the same positive raw target lift and a bit order
`(53*j) mod 131`, releasing one x word at leaf 0 or 5. They are planted
correctness/search diagnostics for proposal `Q1420`; `candidate_id` is
`null`.

| Released x bits | Source x0 | Descendant x0 | Source x5 | Descendant x5 | Search result at this width |
| ---: | --- | --- | --- | --- | --- |
| 1 | SAT | SAT | SAT | SAT | 4 verified SAT |
| 4 | SAT | SAT | SAT | SAT | 4 verified SAT |
| 8 | SAT | SAT | SAT | SAT | 4 verified SAT |
| 16 | SAT | SAT | SAT | SAT | 4 verified SAT |
| 32 | capped | wall-capped | capped | capped | 3 conflict caps; 1 external wall cap |
| 64 | capped | capped | capped | capped | 4 conflict caps |
| 96 | capped | capped | capped | capped | 4 conflict caps |
| 131 | capped | capped | capped | capped | 4 conflict caps |

Here `SAT` means `SAT_VERIFIED_GROUP`, and `capped` means
`BOUNDED_UNKNOWN` with final recorded conflicts 20,001–20,003. The
descendant x0/width-32 process reached the 40.111-second external guard
after 6.874 seconds of process CPU; it is wall-censored rather than known
to reach the conflict cap. No sampled 4-GiB RSS guard fired. The 16 SAT
cells used 0.440–4.634 seconds of process CPU and 1.077–9.364 seconds of
solver wall time; the 16 bounded cells used 2.800–8.706 CPU seconds and
8.647–40.111 wall seconds. These costs are exploratory because host-wide
CPU isolation was not established. The reported result is the verified
status under a fixed budget, not a CPU speed ratio.

For every SAT model the auditor checked 225,325 source or 229,902
descendant native XOR constraints, and respectively 359,642–359,657 or
359,084–359,099 ordinary clauses including the unit delta. It decoded the
same six distinct witness masks, x/z coordinates, four finite S3 states,
and the unique all-plus sign choice giving the exact raw target. The
width-131 unit deltas match the four independently archived full x-release
inputs byte for byte. A first unprivileged attempt failed at the sandbox
`ps` preflight **before solver launch**; its distinct
[`PRODUCER_FAILURE` receipt](runs/R1/source_x0_w1_sandbox_preflight.json)
and traceback are retained. The guarded cell was then run against the
unchanged frozen formula.

## Decision and next algorithmic gate

The leaf equations already determine the coordinates once a selector mask
is fixed. For the archived W24 construction, write
`w(s)=sum_j s_j*b_j`, `u(s)=halftrace(w(s))`. The circuit enforces
`w(s)*z=1` and `u(s)*(x+alpha)=alpha`, so at valid masks
`z=w(s)^(-1)` and `x=alpha+alpha*u(s)^(-1)`. The simultaneous width-32
frontier and prior full-x bounded controls therefore make **conditional
field-linear elimination at a leaf** the next implementation target: derive
its x/z values exactly when a selector becomes fixed, and substitute or
propagate them before asking SAT to cross the global S3 system. The first
gate is to reproduce and verify the width-131 witness cells using a
selector-derived cut without feeding archived x values as hints. The
next gate applies the same mechanism to frozen ordinary Q1420 queries,
charging base/table preparation, every partial branch and failed attempt,
model verification, verified relation yield, and novel rank. A table or
branching policy must beat its own preparation and search costs; this
fixed-witness frontier alone cannot answer the equal-B held-out yield or
single-target online IC/rho question.

Reproduce the archive-only audit with:

```sh
python3 -B experiments/ecc2k130-263-x-freedom-ladder-20261010/audit.py --write
```
