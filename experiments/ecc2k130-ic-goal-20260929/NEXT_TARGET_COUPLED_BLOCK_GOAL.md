# Next ECC2K-130 IC goal: target-coupled pair-block propagation

The ultimate objective remains a verified one-target ECC2K-130 discrete
logarithm with lower isolated online wall time than same-point rho. The next
**algorithm gate** is narrower and falsifiable:

> Preserve an unpinned ordinary N41 eight-point row on the frozen
> same-rotation W6 public target while propagating the target equation into
> at least two still-free exact pair domains. Represent pair states implicitly
> instead of materializing full pair-state vectors or the 4+4 pair-sum index.
> Then provide a source-bound operation and memory projection for the
> corresponding N131 W18 method under 600 seconds and 4 GiB before
> attempting an ordinary N131 target.

The [exact two-free-pair census](n41_two_free_pair_occupancy_20261009/README.md)
now fixes the smaller-field completion oracle for this gate. The last two
W6 pair domains produce 3,167,136 distinct group sums; on the frozen
public point, 19 first-two-pair residuals hit that support and 12 complete
an eight-column relation. Independent Sage arithmetic recounted every
suffix assignment and prefix residual. The reference materializes a
quadratic suffix index and spends 173.704 seconds in the target-dependent
scan. The earlier [compact lookup](n41_two_free_pair_compact_lookup_20261009/RESULT.md)
already recovered an ordinary row in 32.222 seconds and passed independent
Sage replay, but a literal N131 W18 pair-state vector exceeds 4 GiB even
at one bit per state. The exact census filters cross-pair column repeats
before constructing suffix support (3,167,136 assignments); the compact
lookup counted all 3,825,936 assignments and checked repeats after a hit.
The constructive gate now requires implicit pair-state generation and
target pruning with a credible N131 resource projection. Record how many
prefix families that method rejects *before* both remaining pair domains
are enumerated.

The [source-bound W18 calculation](n41_two_free_pair_occupancy_20261009/result.json)
also sharpens the N131 transfer test. For a uniform nonidentity target
independent of a fixed first-two-pair prefix, the last two W18 pair
domains can cover at most `1.747185e-18` of the subgroup. The union bound
requires at least `286,174,705,817,677,085` such fixed prefixes for 50%
success, more than `4.769e14` probes per second in 600 seconds. A public
target may guide prefixes adaptively; the next method must specify and
measure that guidance or eliminate many prefixes symbolically. A faster
terminal pair-membership oracle alone does not meet this work bound.

The natural representation is one seed sum `s_i`, one still-free seed
`a_i`, a parity bit, and pair-output coordinate `z_i` per pair. Preserve the
exact relation `a_i b_i=a_i^2+s_i a_i` with `b_i=s_i+a_i`; propagate the four
outputs through a balanced S3 tree to the *public* target. The existing
seed-sum-conditioned prefix gate and division-free subspace-polynomial
eliminant are local components, not a completed joint solver. A proposed
method may use a different exact representation if it supplies the same
early target-dependent pruning and independent replay.

The frozen N41 gate uses `EC1N41Ckb1h7d5e80d3c4d0`,
`Q=(1458168294740,1672312028033)`, four W6 windows at rotations
`0,10,20,30`, eight slots, actual `B=256`, and folded `K=26`. The
complete twelve-row census is a correctness oracle for development:
no row, seed, pair output, or scalar is pinned in the acceptance solve.
Freeze solver source and limits before the public-only solve. Require a
verified row within 120 seconds target-dependent wall time and 4 GiB peak
RSS, retain failures and phase times, and have checked Sage independently
replay base membership, eight distinct folded columns, exact sum, and
subgroup membership. Record the number of partial states rejected while
at least one pair still has an unchosen leaf. Compare this to the existing
unrestricted and shared-low-bit support counts; simple row postfiltering
does not meet the propagation gate.

For N131, use the exact same-rotation W18 policy on
`EC1N131Ckb1h136f03e58c98`: `B=1,050,456`, `K=131,068`, and rotations
`0,32,64,96`. Before an ordinary query, require a source-bound estimate
or measurement of worst-case pair-domain work, group/field operations,
memory, and failed attempts under 600 seconds and 4 GiB; a public-only
planted control must replay independently. The current independent-list
model needs about 391 GB raw payload for 50% coverage, and a shared
seed-sum bit still leaves over 361 GB for just one literal bit bucket.
The new solver therefore needs algebraic compression or target-adaptive
generation beyond a static pair-list join. A credible projection is a
**prerequisite**, not evidence of ordinary N131 yield.

The [four-pair seed-sum/target rank audit](N41_FOUR_PAIR_TARGET_QUADRATIC_RANK_RESULT.md)
proves that the only degree-at-most-two Boolean equalities in the four W6
pair seed-sum masks and target-x bits that hold for every valid N41 row are
the target subgroup trace equation and its multiples. A proposed cheap
cross-pair propagator in this feature family therefore has no nontrivial
universal equation to use. The gate remains open for conditions involving
pair outputs or leaf products, higher-degree block elimination, and other
exact target-dependent methods.

The [N41 DPLL_ANF method gate](N41_W6_S8_DPLL_ANF_RESULT.md) converted the
same exact quadratic public-target system and verified the solver input with
a pinned known row, but its unpinned worker timed out at 120 seconds without
a model. A direct generic ANF-solver substitution therefore does not clear
the N41 gate under this cap. Keep the target-coupled pair-domain requirement;
do not treat another solver flag set as a substitute for early pruning.

The [adjacent two-pair quadratic F4 control](N41_ADJACENT_TWO_PAIR_F4_RESULT.md)
also timed out at 120 seconds on a public-only planted N41 target, even after
reducing the exact equality core to four leaves, 142 Boolean variables, and
155 degree-at-most-two functional equations. The known row and its Sage
replay pass, and the unpinned formula matches the preflighted one. This is a
negative feasibility control for generic F4, not evidence that the target is
unrepresentable. A proposed pair-block method should now demonstrate an
exact structural elimination or target-conditioned generator on the same
small control before extrapolating its variable count to N131.

The [exact-domain SAT follow-up](N41_ADJACENT_TWO_PAIR_EXACT_SAT_RESULT.md)
then imposed all four seed mask/parity memberships and distinct folded
columns during search on the same public planted point. Its pinned copy
passed complete Boolean and group controls, but the unpinned one-worker run
timed out at 120 seconds without a model. Thus adding exact domain clauses
to the native-XOR quadratic encoding did not clear even this small control.
This does not evaluate exact-domain F4 or prove the target lacks a row;
structural target-conditioned pair selection remains the required next step.

The [exact-membership F4 follow-up](N41_ADJACENT_TWO_PAIR_MEMBERSHIP_F4_RESULT.md)
closed that remaining method-control gap. One degree-five membership ANF per
leaf, and then an exactly equivalent two-cubic representation per leaf, both
passed planted-row and public-formula checks; each unpinned Msolve run hit
the 120-second cap without a basis. The cubic pair lowers the maximum
functional degree from five to three but did not clear this control. This
reinforces the gate for target-dependent pruning across still-free pair
domains, rather than another generic algebraic encoding change.

The [official W2/m15 first-leaf probe](N131_W2_M15_FIRST_LEAF_PROBE_RESULT.md)
fixed the lexicographically smallest usable base x in R3's already built
setup-query formula. Although the exact subgroup-wide representation mean
for that anchor is 2.54, the bounded solver returned no model after
115 seconds. This is a censored search diagnostic on a reused formula, not
an online IC measurement. A single point anchor therefore supplies no
evidence to relax the target-coupled pair-domain gate; the full R3 worker
later ended with
[`INTERRUPTED_RUNNER_LOST_RAW_SOLVER_OUTPUT_RETAINED`](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/result.json).
Its recorded precomputation rank is 0/14 and the parent/solver processes are
absent. Treat this attempt as terminal censored evidence; any successor needs
a new frozen, supervised run rather than waiting on R3.

The independently checked [degree-five single-leaf rank result](N41_DEGREE5_SINGLE_LEAF_RESULT.md)
also reaches the exact syzygy rank ceiling after 42 degree-at-most-three
multipliers on one six-bit leaf. It leaves every first-pair assignment
consistent in that relaxation. Together with the degree-four pair and
cross-pair screens, this makes further invariant-column lifts a poor next
step; prioritize a target-coupled method that carries pair-output coordinates
or removes symbolic families across multiple pair domains.

The [first-pair frontier](FIRST_PAIR_GENERATION_FRONTIER_RESULT.md) adds a
work requirement to that memory gate. The literal N131 W18 first-pair
domain has at least 34,448,654,064 distinct-column states; scanning every
state within 600 seconds needs more than 57.4 million target-dependent
checks per second before any continuation work. A uniform-target bound
gives at most `6.025×10^-8` completion probability for a first pair chosen
independently of the target. By the union bound, a target-independent
sampling route needs at least 8,299,027 exact completion probes for 50%
uniform-target success, or 13,832 per second within 600 seconds; even this
is only necessary, not sufficient. A local two-point membership predicate
or list filter alone is insufficient. The N41 solver must show either a
mechanism that **generates** target-relevant first pairs or eliminates large
symbolic families, or a cheap exact three-pair completion oracle with a
credible measured probe rate. The N131 projection must charge the chosen
mechanism's work and memory rather than assume it.

After that gate, freeze one previously unseen public N131 target and run
an ordinary relation attempt. A verified relation is the next scientific
milestone, not a recovered DLP. Only after relation yield and rank support
factor-log computation should the project time target descent, scalar
recovery, and the same-point one-target rho solve with exclusive phases and
the required host-isolation receipt. Until a complete pipeline exists,
keep proposal IDs separate and complete candidate/run IDs null; do not
promote stage diagnostics or modeled row counts to an IC speedup claim.

The [N41 W2/m8 projective group-law gate](n41_w2_projective_group_gate_20261004/README.md)
also passed exact signed-base and independent Sage controls but timed out on
its unpinned public target at 119.243 seconds. Its inversion-free arithmetic
removes one source of SAT variables; it does not give target-conditioned
pruning while leaves remain free. The W6 pair-block method gate above is
unchanged, and a smaller group-law circuit alone is not grounds for an N131
ordinary query.

The [N41 sparse-orbit W2/m8 gate](n41_w2_sparse_orbit_gate_20261005/README.md)
tested the newer exact Frobenius-orbit multiplier specialization from the
N131 W2/m15 preflight. Its full-pin model passed, but fixing only the eight
known leaves left the intermediate x values unresolved at the 30-second
cap. A smaller multiplication circuit by itself is not evidence that the
public-target search will finish; keep early target-conditioned pruning as
the promotion requirement.

The [native exact offset-one W18 inverter](n131_w18_offset_one_native_exact_20261005/README.md)
now supplies a checked local final-pair primitive: all 32 planted and 64
uniform controls match the frozen Sage reference, and eight algebraically
consistent nonrational outputs are rejected. It accepts a *proposed* pair
output coordinate. The next algorithm step must derive useful proposed
coordinates from the public target while at least two other pair domains
remain free; scanning independent coordinates or completing three fixed
pairs first does not satisfy this gate. The local primitive's unisolated
timings do not change the 120-second/4-GiB N41 acceptance envelope or the
600-second/4-GiB N131 transfer gate.

The [fixed-left linear-right fallback](n131_w18_offset_one_native_exact_20261005/FIXED_LEFT_FALLBACK.md)
now handles exceptional proposed outputs whose 79-column gate loses rank.
All 104 frozen local controls retain their exact outputs, and the three
large-kernel negative cases finish in about 0.09–0.11 seconds internally on
the exploratory host. This removes a local inversion tail only. The public
target still has to constrain the proposed pair outputs before a full leaf
assignment; fast inversion of independently chosen coordinates does not
resolve that search problem.

The [exact final-pair sampling frontier](n131_w18_offset_one_native_exact_20261005/LAST_PAIR_FRONTIER.md)
further rules out a direct wrapper around that inverter: independently
choose six leaves, subtract their sum from a uniform target, and test the
last pair. Even before column exclusions, its one-probe hit probability is
at most `C(262614,2)/(r−1) ≈ 5.07×10^-29`; at least
`9.87×10^27` independent-target-law probes are necessary for 50% success
by the union bound. This does not constrain target-coordinate-guided prefix
selection or a joint solver. It makes the next N41 experiment's early
target-conditioned pair-domain pruning an essential algorithmic requirement,
not merely a timing preference.

The [Q1356 exact fingerprint follow-up](N41_THREE_PAIR_FINGERPRINT_GATE_RESULT.md)
closed the local inverse-classification variant of the N41 W2 three-pair
SAT gate. Eight quadratic and ten cubic cyclic features distinguish every
one of 2,424 exact orbit classes, and a known public row passes SAT and Sage
replay. The unpinned public point still times out at 120 seconds with zero
ordinary relations. This reinforces the acceptance requirement above:
measure public-target elimination of partial assignments across at least
two still-free pair domains. Local class identification alone does not
qualify as early target-coupled pruning.

The [Q1357 mixed-cubic rank witness](N41_TARGET_PAIR_MIXED_CUBIC_RANK_RESULT.md)
then tested the frozen N41 eight-slot adjacent-window input with slot
rotations `0,5,10,15,20,25,30,35`. Its 16,046 features
include every degree-at-most-two first-pair/target-x monomial and all cubic
terms mixing one pair bit with two target bits or two pair bits with one
target bit, after removing the known target-trace bit. Exact valid group
rows attain full feature rank, with independent Boolean and checked-Sage
replays. Thus no universal necessary equation in this declared one-pair,
target-x family can reject a first-pair state. The next target-dependent
condition on this geometry must involve another pair domain, target y, a
different nonlinear representation, or higher degree; the adjacent-window
N41 result does not veto a different window pairing or prove an N131
no-go theorem.

The [v3 W18 pair usability correction](n131_w18_offset_one_native_exact_20261005/COLUMN_FILTER_RESULT.md)
adds the factor-base condition needed by any future joint solver. Two
frozen rational group witnesses for one proposed output reuse a single
signed-Frobenius column and are now rejected as IC pairs. All 34 prior
planted usable pairs survive, and native/Sage orbit controls pass. A future
N41 or N131 relation worker must preserve this distinction between a
rational group sum and distinct usable matrix columns during search and
independent replay.

The [Q20261006043101 three-pair residual gate](Q1447_RESIDUAL_ORACLE_GATE.md) makes the
next algorithm decision quantitative. A target-independent first-pair scan
needs at least 8,299,027 exact three-pair completion probes for a 50%
uniform-target chance within the N131 budget, leaving 72.298 microseconds
per entire probe if all 600 seconds were spent there. The alternative is a
target-conditioned generator or symbolic elimination of first-pair families.
Neither calculation is a fixed-target yield measurement or a bound on such
an adaptive solver; it prevents promoting another fast local pair check as
the missing target-coupled search method.

The [Q20261006043102 compact pair-sum filter](q1448_pair_bloom/RESULT.md) gives an
executed control for early pruning: it found and independently replayed an
unpinned N41 row while rejecting 98.56% of examined two-free-pair residuals
with a 32-MiB bitmap. Its literal builder must enumerate at least
1,186,709,766,821,143,716,096 group sums at N131, so it fails the
600-second challenge-width work gate. Keep the early-pruning behavior as a
correctness control, but do not transfer this bitmap construction. A useful
next method needs an implicit two-pair domain or target-adaptive generation
that avoids the Cartesian product.

The [Q20261006065000 static-join frontier](n131_phi_torsion_frobenius_domains_20261005/m16_static/static_join_frontier_20261006/RESULT.md)
also tests the newer exact 300,304-state sparse-seed pair domain. An explicit
target-independent 35-byte-point-key table under 4 GiB, even paired with an
optimistic 600 billion full online probes in 600 seconds, covers at most
`1.08187e-19` of uniform subgroup targets in one orientation. A deliberately
unrealistic one-bit-per-explicit-state sensitivity still gives at most
`3.02923e-17` in one orientation. This counting gate is specific to explicit
per-state static tables and target-independent traversal; it does not
address the fixed published point, symbolic compression, or target-adaptive
algebraic generation. It reinforces the requirement above to demonstrate
early target-coupled pruning rather than enlarge a blind join.

The [Q20261006070300 global trace-character XOR gate](n41_pair_trace_xor_20261006/RESULT.md)
tested a different exact target-coupled condition on the same N41 public
point. One added 1,922-literal native-XOR row passed the known ordinary row,
an independent formula diff, and an installed-Sage audit of all 7,824 valid
pair additions, but the unpinned solver again reached 120 seconds without a
model. More decisively, every N41 exact pair domain has 480 trace-one and
498 trace-zero outputs, and the exact N131 sparse-seed domain has
150,120/150,184. A full free pair can therefore satisfy either residual
trace parity. This single group character cannot prune while a pair block
remains entirely free, so it fails the required two-free-pair propagation
gate independently of solver timing. Future work must carry stronger
nonlinear target information across free pair domains.

The [exact two-free-pair completion experiment](n41_two_free_pair_s3_norm_20261008/README.md)
now supplies the sharper method boundary. Its native batched-inversion
predicate classifies a known positive and a checked negative residual by
using the public target in the S3 condition while two pair domains remain
free. Its unpinned N41 search tested 75,264 residuals, ending
`ONLINE_TIME_CAP` after 120.154 seconds. The N131 transfer receipt proves
that even one bit per explicit W18 pair state needs 4,306,081,758 bytes,
above the 4-GiB cap before any coordinates or witnesses. The Q1448 bitmap
produced an independently replayed N41 row through early pruning. Its
literal N131 builder needs at least 1,186,709,766,821,143,716,096 group
sums. These receipts set the next concrete algorithm target: represent the
pair domains implicitly, then eliminate or generate two still-free domains
from their W18 seed equations and the target-dependent S3 link without
storing or scanning the full pair-output lists.

Freeze an N41 implementation of that implicit completion operator before
its public-Q search. Validate a known positive residual, independently
chosen negative residuals, exact pair-column rules, and every returned
eight-point row with the checked Sage launcher. The unpinned 120-second,
4-GiB acceptance run must record both the partial states rejected before
all leaves are chosen and all construction, query, failed-probe, and replay
costs. Before a corresponding N131 query, bind its source to a worst-case
600-second/4-GiB estimate or measurement for the full operator, including
failed probes, and show how its representation avoids the 34,448,654,064
distinct-column states per W18 pair domain. The recent exact d13 public-Q
[bridge and projection](n131_d13_public_bridge_projection_20261009/RESULT.md)
kept the largest solver XOR component to 3,038 rows, yet its bounded query
ended `CENSORED_TIME` at 580.12 seconds. The acceptance signal for the next
encoding is therefore verified target-dependent elimination of free pair
choices and an ordinary row, with static formula geometry retained as a
diagnostic.

The [N131 W18 product-span inverse](n41_n131_universal_product_linearized_20261011/RESULT.md)
now recovers pair seeds from a supplied reciprocal coordinate with one
19-variable binary solve. Its 196-case N131 panel and exhaustive N41 pair
control preserve exact source witnesses. A separate
[53-column joint-linear implementation](n131_w18_joint_linear_inverse_20261011/RESULT.md)
independently replayed two positive coordinates with checked Sage and
exercised a complete lower-rank fallback. Use the 19-variable method as the
reference supplied-coordinate checker; neither method generates the
coordinate from the public target.

The [N41 suffix-seed quadratic rank certificate](n41_suffix_seed_quadratic_rank_20261011/RESULT.md)
then reaches full rank **1,379/1,379** on exact two-free-pair x coordinates
and both six-bit seed sums. Its 1,379 witness rows are independently replayed
through group addition and column rules. Thus no universal degree-at-most-two
Boolean equation in those 52 variable bits can select a suffix seed-bin
pair for this geometry. The existing per-bin interpolation filters remain
exact, but their literal N131 table fails the work and memory gate. The next
joint operator must keep finite seed-conditioned output sets or stronger
nonlinear/group information while the public target constrains at least
four free pair domains. Measure whole-family rejection before source-mask
expansion on the unpinned N41 public point, then apply the frozen N131
600-second/4-GiB source-bound gate.
