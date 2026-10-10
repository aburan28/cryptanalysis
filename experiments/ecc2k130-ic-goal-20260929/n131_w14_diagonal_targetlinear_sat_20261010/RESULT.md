# One-hot target-linear join for N131 W14 diagonal pairs

The final reciprocal S3 join now uses the four fixed raw preimages of the
published target as a **one-hot field-linear map**. If `a,b` are the two
upper-chain reciprocals and `z_i` are the four target-preimage
reciprocals, the exact equation is

`(a+b+sum_i flag_i*z_i)^2 + sum_i flag_i * A(a*b*z_i) = 0`,

where `A(v)=v+v^2` and exactly one `flag_i` is true. Each `A(a*b*z_i)` is
linear in the 131 bits of `a*b` because `z_i` is fixed. The
[circuit](circuit.py) therefore uses 524 flag-by-product AND gates at
the final join in place of a general second field multiplication. The
five leaf joins retain the exact 27-bit bilinear W14 product-coordinate
encoding. A [complete constructed assignment](profile.json) satisfies
all 638,038 CNF clauses and 33,211 native-XOR rows, using the same ten
independently group-verified diagonal atoms and the same exact N131
curve as the preceding experiments.

| Same ECC2K-130 published point and W14 base | Source frame | Bilinear pairs | Bilinear pairs plus target-linear join |
| --- | ---: | ---: | ---: |
| Actual projected base points `B` | 82,200 | 82,200 | 82,200 |
| Folded columns `K` | 8,160 | 8,160 | 8,160 |
| Published formula AND gates | **59,049** | 64,698 | 59,908 |
| Published formula variables | 108,219 | 102,869 | **94,314** |
| Published formula native-XOR rows | 47,978 | 36,979 | **33,214** |
| Published formula CNF clauses | **635,469** | 652,408 | 638,038 |
| One-worker status at the 120-second search gate | `CENSORED_TIME` | `CENSORED_TIME` | `CENSORED_TIME` |

The one-hot join removes **4,790 AND gates** from the bilinear published
formula and leaves 859 more than the source-frame formula. Its published
XCNF is **54,009,338 bytes**, with decompressed SHA-256
`5fa804a3f6b62cd64ec9f9562a0ca7fe39813d2be4b81232a8ce2325eb79fb69`.
The [constructed formula](constructed.xcnf.gz) has decompressed SHA-256
`885b910c1c0247f4e1ea30275a224769d74b37680b78ac6021b9b5443890cc09`.
The [frozen protocols](protocol.json) and [published-query protocol](query_protocol.json)
bind the source, exact curve and target, checked Sage runtime, one worker,
4-GiB RSS limit, and 120-second construction-plus-search boundary.

On the [unpinned published-point query](public_query/result.json), all ten
source masks, eight intermediate reciprocals, and the one-hot target
choice remained solver-controlled. Formula construction took **7.128
seconds** and active CryptoMiniSat search **111.962 seconds**, totaling
**119.090 seconds** at the search boundary. The solver log records active
search without a terminal SAT or UNSAT line; sampled combined RSS peaked
at **388,431,872 bytes**. Compression and receipt writing added **2.733
seconds** after the search boundary, bringing recorded process wall to
121.823 seconds. The [terminal audit](terminal_audit.json) checks both
formula hashes, frozen sources, exact public point, the raw solver output,
and the two timing boundaries. These capped runs on an unisolated host
support circuit-construction conclusions, not a CPU speedup claim.

This remains a decomposition-stage proposal with `candidate_id: null`.
The published query produced zero independently verified relations and
zero novel matrix rows. Further gate-count reduction alone is unlikely
to clear the observed search barrier. The next experiment should combine
the [exact W14 diagonal pair inverse](../n131_w14_diagonal_pair_inverse_20261010/RESULT.md)
with a factored or sharded pair-image membership gate: generate candidate
upper-chain pair outputs, reject outputs outside the pair image, recover
source masks for accepted outputs, and independently replay group sums.
Measure accepted ordinary-query yield and novel rank before allocating
work to factor logs or a matched one-target rho comparison. The global
dense N131 pair polynomial exceeds the 4-GiB coefficient budget, so its
membership test needs a different representation.
