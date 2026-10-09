# Exact target-coupled join on the frozen N41 phi-chain target

An exact five-plus-five group join recovered an **ordinary 12-leaf relation**
on the frozen N41 public point while retaining the SAT control's two fixed
first-leaf codes and selected first-link S3 root. The witness was found from
the point alone: neither the fixture scalar nor any planted decomposition
entered the search. Independent checked-Sage replay verifies the 12 leaf
selectors, distinct x coordinates, cofactor-four subgroup transport, the
public point sum, and the full saved-formula assignment.

The reusable setup enumerated four adjacent signed two-leaf pair lists
(3,600 entries each) and indexed 1,800,000 deterministic draws of leaves
2–6. It retained 1,797,680 distinct five-leaf group points. The online
clock began with conversion of the supplied public target to its raw
cofactor-four endpoint, after setup, and included both signed first-root
residual queries, all unsuccessful probes, and the exact hit check. The
first verified hit occurred after 878,632 draws of leaves 7–11.

| Stage or result | Frozen observation |
| --- | ---: |
| Reusable setup wall | 185.304 s |
| Target-dependent join wall, including endpoint conversion and hit check | 256.384 s |
| Endpoint conversion within online stage | 0.895 ms |
| Exact hit check within online stage | 0.375 ms |
| Peak one-process RSS | 540,753,920 B |
| Setup / online wall caps | 600 s / 600 s |
| Combined RSS cap | 4 GiB |
| Target count | 1 |

The [frozen protocol](protocol.json), [preflight](preflight.json), and
[terminal audit](audit.json) retain source hashes, seeds, limits, all draws,
timing boundaries, and the complete [witness](result.json). The host had no
isolation receipt, so these wall times are exploratory stage costs rather
than a controlled speed comparison. The [independent checked-Sage
replay](replay.json) ran after the join clock; its command wall was 1.11 s
including launcher startup. It also evaluates a regenerated public XCNF
assignment. A separate [saved-XCNF audit](xcnf_replay.json) checks every
record of the original public source formula (52,397), the exact second-link
lookup formula (54,513), and the corrected target-conditioned suffix formula
(201,171). Thus the earlier censored SAT queries had a valid ordinary
assignment in this same first-link branch.

For the complete d6 policy of 30 valid codes, all 41 Frobenius rotations,
both signs, and cofactor-four projection, the [factor-base audit](factor_base_row.json)
finds **B=2,132 actual subgroup points** and **K=26 folded columns**.
Four code labels lie in already represented orbits. The verified target
equation has nine nonzero folded columns; independent group reconstruction
from those coefficients equals the public target.

The direct sampled join is a smaller-field control. For a uniformly sampled
N131 subgroup target independent of the fixed lists, the same 1.8-million
left draws and 2-million right draws across two first-root signs have
success probability at most **1.058×10⁻²⁶** by a union bound. Even an
idealized 600 billion right draws in 600 seconds raises that bound only to
**3.174×10⁻²¹**. The [exact transfer screen](n131_transfer_screen.json)
uses the frozen degree-131 subgroup order and does not bound the published
fixed target or target-adaptive list construction. It rules out promoting
this direct sampled join as the N131 search method. The next algorithmic
step is to use target information to restrict multiple pair choices before
building a five-leaf index, then measure an ordinary N131 relation under
the 600-second/4-GiB gate. Useful rank accumulation, factor logs, and the
fresh single-target online IC/rho comparison remain downstream gates.
