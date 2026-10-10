# Exact equal-B source m6 circuit: four target lifts and bounded solver pilot

An exact shared leaf circuit now represents the frozen 11,743,888-point
normal4 and W24 source factor bases without a post-solver membership filter.
Checked Sage replay matched 64 W24 and 128 normal4 source-point controls;
both planted six-summand chains satisfied every Boolean root, while changed
leaf-x and inverse-witness bits failed. Native-XOR CryptoMiniSat accepted a
pinned valid leaf and rejected its one-bit x mutation for each policy. The
first ordinary public query reached solver search for both formulas and
remained `BOUNDED_UNKNOWN` at the 150-second external wall cap. This makes
the next useful gate a search over **all four exact raw target lifts**, now
certified by an order-four torsion witness.

## Exact construction and controls

The source curve, field, bases, and query point are bound to the
[`equal-B input gate`](../ecc2k130-normal4-equalb-m6-20261010/RESULT.md).
The circuit uses `w*z=1`, `H(w)*(x+1)=1`, and `Tr(z)=0` per leaf. The proof in
[`PROTOCOL.md`](PROTOCOL.md) makes this an exact rational source-curve leaf.
Normal4 uses four-hot 131-coordinate selectors; W24 uses a 24-bit prefix
comparator. The complete source censuses found zero in-base reciprocal
partners for both geometries, so the two encodings have the same actual
usable point count `B=11,743,888` and signed-class count `C=5,871,944`.

The checked-Sage [`verification receipt`](runs/R1/sage_verification.json)
reconstructed every sampled source point and its `[4]` projection, then
evaluated both full six-summand Boolean programs on independently formed
group-sum chains. Its 192 point controls and four mutated-root controls
passed. The separate [native-XOR CNF receipt](runs/R1/cnf_controls/receipt.json)
records four pinned solver results: SAT for one valid W24 and one valid
normal4 leaf, UNSAT after flipping the x least-significant bit in each.
These are construction controls; the ordinary query below is distinct.

| Policy | Selector bits per leaf | m6 IR operations | XCNF vars | Ordinary clauses | Native XORs | Formula SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| W24 source | 24 | 334,882 | 328,948 | 326,422 | 218,645 | `d35fb4abe25a95516f9e43d0a2413c25b4e5113faf67067d8998e0dbb182fda4` |
| Normal4 source | 131 | 431,602 | 529,422 | 586,220 | 298,206 | `2a701b6ebdf75d39960572280c2fd8599b821cf6fb4a97fd2026686106572969` |

Both formulas use five S3 links, terminal x equality, a source point from
the first frozen ordinary query, and six exact leaves. Formula construction
itself used at most 372 MB peak RSS in the recorded local runs. The exact
XCNF streams are retained as deterministic gzip archives; decompression
reproduces every uncompressed formula SHA-256 above and in the
[build receipts](runs/R1/w24_m6_q0.json). The
[W24](runs/R1/w24_m6_q0.xcnf.gz) and
[normal4](runs/R1/normal4_m6_q0.xcnf.gz) ordinary-query archives can be
decompressed to `.xcnf` files for direct solver replay.

## First ordinary-query pilot

CryptoMiniSat 5.14.7 ran one worker with native XORs, `--maxtime=120`, an
external 150-second wall guard, and a 4 GiB resident-memory guard. The
public source query was point16 index zero, with x coordinate
`136967685723002862455696545888267170352`; the fixture scalar was outside
both formulas. The local host had no CPU-isolation receipt, so these wall
times are resource-capped diagnostics rather than controlled performance
ratios.

| Policy | Status | Wall cap reached (s) | Peak observed solver RSS | Search evidence | Verified relations | Novel rank |
| --- | --- | ---: | ---: | --- | ---: | --- |
| W24 source | `BOUNDED_UNKNOWN` | 150.265 | 270,532,608 B | 605 restart-progress lines | 0 | unknown |
| Normal4 source | `BOUNDED_UNKNOWN` | 150.454 | 325,337,088 B | 455 restart-progress lines | 0 | unknown |

The [W24](runs/R1/w24_m6_q0_pilot.json) and
[normal4](runs/R1/normal4_m6_q0_pilot.json) raw transcript receipts preserve
exit `-9` from the external guard, binary/formula hashes, stdout and stderr,
resource observations, and the independent [W24](runs/R1/w24_m6_q0_audit.json)
and [normal4](runs/R1/normal4_m6_q0_audit.json) search audits. The first
W24 launcher attempt is separately recorded as `PRODUCER_FAILURE`: the
sandbox denied the runner's `ps` RSS probe before solver search, after which
the guarded run used process inspection and completed the frozen cap. Neither
bounded result supplies a per-query yield estimate or evidence that one
factor-base geometry solves faster.

## Cofactor-four target-lift result and next decision

The [checked-Sage torsion receipt](runs/R1/torsion_lifts.json) found the
source point `T=(1,1)` of order four, with `2T=(0,1)`. For the frozen public
query `Q`, the four distinct points `Q+jT`, `j=0..3`, all project to `[4]Q`
and have four distinct x coordinates. The current S3 formula fixes only
`x(Q)`, so it searches one of the four raw target-lift classes. A projected
factor-base relation may live in any of the four classes. The next paired
experiment should build all four x-target formulas per ordinary query,
charge the complete four-attempt policy to that query, and compare verified
relations and new rank per charged query for W24 and normal4. A SAT model
must receive signed point replay and `[4]` row verification before rank
insertion.

The combinatorial identity
`(1/r) * sum_{R in E[r]} N_6(R) = binomial(B,6)/r = 5.353883452375603`
counts unordered distinct six-point projected decompositions averaged over
uniform subgroup targets, where `r=680564733841876926932320129493409985129`.
It follows by assigning each six-element subset of the fixed factor base to
its unique group sum. It includes structurally redundant sums and says
nothing by itself about the four raw lifts, solver work, or independent
relation rank. The actual ordinary-query yield and useful-row cost remain
the decision variables for advancing this base geometry.

The native-XOR search gate also directs solver work: reduce the six-leaf
S3 search space with target-first specialization or a verified indexed join
before scaling to the frozen 16/256-query prefixes. Compare any such variant
on the same target lifts and resource cap, retaining censored outcomes and
the failed-attempt charge. Keep the exact source circuit as the matched
control. The [file manifest](runs/R1/manifest.json) binds sources, formulas,
transcripts, and verification receipts.
