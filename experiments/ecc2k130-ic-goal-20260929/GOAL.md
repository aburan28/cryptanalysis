# ECC2K-130 single-target index-calculus goal

**Exact W15 cofactor-class gate (2026-10-10):** the
[source-frozen census](n131_w15_cofactor_class_gate_20261010/RESULT.md)
classifies all W15 masks by `Tr(H(w²)/w)`, with 8,295 usable masks in the
raw subgroup and 8,146 in its order-two coset. Independent Sage scalar
multiplication checked 512 signed lifts. Every nonzero W15 XOR seed has
7,660–8,856 class-zero and 7,664–8,856 class-one signed pair states,
so this one-bit character does not reject entire seed families. Exact
parity certificates rule out a degree-at-most-four Boolean formula for
the class on the usable masks. Restricting all five free pairs to subgroup
sums still leaves a source-count mean of 2,108.394 tuples per uniform
subgroup target before zero-intermediate filtering, but it supplies no
measured public relation. Keep the 32-KiB class table for cheap native
witness screening and continue with target-conditioned S3 elimination
while at least four pair blocks remain free.

**Exact W15 five-pair source gate (2026-10-10):** fixing a target-independent
two-column prefix and freeing the remaining five W15 pairs gives exactly
45,910,670,045,280,721,008,901,187,314,530,927,830,630,400 signed
source tuples with twelve distinct folded columns, or 67,459.667 per
uniform subgroup target before intermediate-point filtering. Two independent
counts agree. The [constructed XCNF control and public run](n131_w15_unrestricted_fivepair_public_20261010/RESULT.md)
reduce the public formula to 97,074 variables, 354,246 CNF clauses, and
34,509 native-XOR rows. The exact published-point search recorded
`CENSORED_TIME` at 592.101 seconds of target formula construction and
search under one worker and 4 GiB, with 796,459,008 bytes sampled peak RSS;
the [terminal audit](n131_w15_unrestricted_fivepair_public_20261010/terminal_audit.json)
replayed its formula and source hashes. The next method gate is a
target-conditioned generator of realizable partial sums that retains at
least four free pair blocks. On an ordinary unpinned N41 query, measure
verified relation yield and novel rows per query, then bound N131 work and
memory from the same algorithm before another frozen challenge-width run.

**Measured N131 public-target gate (2026-10-09 22:22 UTC):** the frozen
d13/m12 proposal `Q20261006081500` completed its first accepted-seed
ordinary query on the published target. The [v4 run](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/public_q_runs/d13_m12_20261009T221148Z/result.json)
reached `timeout` after 599.749 seconds of charged target-dependent wall
time: 4.373 seconds in target-query construction/overhead and 595.376
seconds in the one-worker CryptoMiniSat attempt. Its conservative combined
peak was 1,808,089,088 bytes under the 4-GiB cap. The
[independent audit](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/public_q_runs/d13_m12_20261009T221148Z/independent_sage_replay.json)
passed identity and resource checks and recorded zero models and zero
relations. This measures the search bottleneck for the exact d13 formula.
The next method gate is a **target-coupled six-pair solver**: on the frozen
ordinary N41 control, either generate early pair choices from the public
target or propagate it through at least four still-free pair blocks before
enumerating their Cartesian product. Apply the exact pair oracle, count
rejected partial states, recover and replay an ordinary relation, and use
an implicit pair-state representation. Only a
source-bound work/memory projection fitting 600 seconds and 4 GiB advances
that method to the published N131 point.

**Exact completion-density gate (2026-10-09):** an
[independently recounted N41 four-pair census](n41_two_free_pair_occupancy_20261009/README.md)
has 3,167,136 distinct last-two-pair group sums. On its fixed public
point, 19 of 3,167,136 first-two-pair residuals hit that support and 12
pass the full eight-column condition. The checked-Sage audit rebuilt every
suffix sum and prefix residual and replayed all 12 rows. Its quadratic
suffix index took 180.516 seconds of reusable setup; the target-dependent
full prefix scan took 173.704 seconds on an unisolated host. This exact
reference gives a filtered completion oracle. The earlier
[compact N41 two-free-pair lookup](n41_two_free_pair_compact_lookup_20261009/RESULT.md)
already recovered a row within 120 seconds, but its explicit pair-state
vectors fail the N131 W18 4-GiB memory gate. The exact censuses differ in
their column policy: this reference removes cross-pair column repeats
before building suffix support; the earlier lookup checks them after a hit.

The [exact N41 sign-orbit certificate](n41_two_pair_sign_orbit_x_support_20261009/RESULT.md)
partitions those 3,167,136 valid suffix assignments into 1,583,568
negation pairs. The prior independently audited collision-free group sums
make every pair's x coordinate unique; an x hit therefore identifies both
free pair seed sums and folded columns up to global sign. Independent Sage
verified every source-point and pair-state involution and recounted all
valid assignments. For this sign-closed completion domain, y adds no
feasibility rejection after x is known; it selects the recovered sign.
An x-only mixed-cubic filter was separately ruled out by exact full rank,
so the next solver should seek a compact nonlinear seed-conditioned
x inverse or equivalent target-bound elimination while multiple blocks
remain free. The N41 exact x table supplies a control, not an N131 memory
or work projection.

The [seed-conditioned affine x screen](n41_two_pair_seed_conditioned_affine_20261009/RESULT.md)
now closes the linear version of that inverse on the exact N41 control:
all `63²=3,969` fixed two-pair seed-sum bins have full affine rank
`41/41` in the 40 free completion-x bits plus the constant. Independent
Sage replayed all 162,729 valid rank witnesses, 41 per bin. Thus even
knowing both free seed sums yields no nontrivial affine x equation for
early residual rejection, and no global affine x map recovers a varying
seed-sum bit. The next method must use nonlinear pair realizability or
joint target elimination across more blocks; this N41 result is not an
N131 rank certificate.

For the current N131 d13 six-pair policy, a final-two-pair completion check
after **four target-independent fixed pairs** has uniform-target hit
probability at most `1.716e-24` per prefix. The
[source-bound calculation](n41_two_free_pair_occupancy_20261009/d13_fixed_prefix_bound.json)
requires at least `291,412,179,145,627,003,543,092` fixed prefixes for
50% success by the union bound, exceeding `4.857e20` probes per second
within 600 seconds. The different W18 four-pair policy has an analogous
`2.862e17` fixed-two-pair-prefix lower bound. These laws leave adaptive
target-guided prefix generation and symbolic family elimination open. A
separate [six-pair frontier](n131_d13_six_pair_prefix_frontier_20261009/RESULT.md)
shows that fixing two pair outputs still requires at least 249,560,561
complete **four-free-pair** probes for 50% uniform-target success, or
415,934.27 full probes per second within 600 seconds. A successor should
either charge and meet that full-probe rate or show target-conditioned
prefix generation or symbolic elimination before the final two-pair oracle;
accelerating that oracle alone cannot meet the density frontier.

**Joint N131 pair-oracle gate:** the
[full-rank joint linear inverse](n131_d13_joint_linear_pair_inverse_20261009/RESULT.md)
recovers the seed sum for proposed same-rotation d13 pair outputs through a
131-by-104 binary solve, then uses the cached fixed-sum inverse to verify
leaves. All 32 saved positive outputs were recovered and 32 uniform field
controls were rejected at the span gate; six rank-drop inputs took the exact
fallback. Independent Sage replay confirmed ranks and group sums. The
exploratory median query for positive outputs was 1.386 ms versus 4.322 ms
for the earlier eight-check sum scan on the same inputs. These are pair-stage
diagnostics on an unisolated host. The next solver must **generate** its
candidate pair outputs from the public target and measure cross-pair
elimination; the oracle alone does not supply relation yield.

**N131 pair-domain structural gate (2026-10-09 21:42 UTC):** an
[exact affine-span certificate](n131_d13_pair_output_linear_span_20261009/RESULT.md)
uses 132 independently replayed same-rotation d13 pair outputs to prove
that no nonzero affine equation in the 131 pair-output phi bits holds for
the full valid-pair domain. Independent Sage elliptic-curve arithmetic and
GF(2) rank both pass. Frobenius transports the conclusion to all six
planned rotations. A target-coupled solver must therefore retain seed-sum
information, use nonlinear pair-domain constraints, or derive restrictions
from the public target across blocks; output-only XOR filters cannot be the
missing universal pruning rule for this policy.

**Exact N131 pair-inverse gate (2026-10-09 21:27 UTC):** the
[same-rotation d13 proposal](n131_d13_same_rotation_pairs_20261009/RESULT.md)
orders twelve leaves as six pairs at Frobenius rotations
`[0,0,22,22,44,44,66,66,88,88,110,110]`, retaining the audited
1,083,108-point base and 4,134 folded columns. For each of the 8,191
nonzero seed sums, the exact S3 pair equation reduces to a rank-12 binary
map with only the pair-swap kernel. A 1,974,044-byte pivot index inverts all
those maps; the local producer enumerated 4,134 usable selectors and
8,542,911 unordered pairs, passed positive and negative controls, and
recovered an independently checked pair after scanning all sums. The
[independent full-index audit](n131_d13_same_rotation_pairs_20261009/audit.json)
reconstructed all 98,292 pivot rows, while the
[rotation audit](n131_d13_same_rotation_pairs_20261009/rotation_audit.json)
checked signed group outputs at all six rotations. Index construction took
1.076 seconds after 6.145 seconds of selector/pair geometry, with 45.3 MB
peak process RSS on an exploratory host. This is an exact pair primitive;
the next method gate is to generate compatible pair-sum and pair-output
inputs from the public target in a six-pair solver. Existing
[N41 same-rotation rows](N41_SAME_ROTATION_RESULT.md) and the
[four-pair control](N41_W6_S8_FOUR_PAIRS_RESULT.md) establish ordinary
positive inputs; their indexed joins do not scale to N131, and their
tested SAT handoffs were censored. The next N41 gate is a **new unpinned
target-coupled method** that finds an ordinary row without a quadratic
pair-sum index and records how many partial states the target eliminates
while at least two pair domains remain unchosen. Require a source-bound
work/memory projection before a frozen N131 public-Q query under 600
seconds and 4 GiB, including independent point replay.

**Current method gate (2026-10-09 21:17 UTC):** an [exact target-coupled
group join](n41_phi_target_coupled_pair_join_20261009/RESULT.md) found and
independently replayed an ordinary 12-leaf relation on the same frozen N41
public target and first-link branch used by the censored SAT controls.
Its witness satisfies every saved record in the source, [N41 second-link
lookup](n41_phi_second_link_control_20261009/RESULT.md), and corrected
[target-conditioned suffix](n41_phi_suffix2_corrected_20261009/RESULT.md)
XCNFs. The reusable five-leaf index took 185.304 seconds to build; the
target-dependent join took 256.384 seconds through exact hit verification
and peaked at 540,753,920 bytes. The complete d6 base has B=2,132 points
and K=26 sign/Frobenius columns; this target equation has nine nonzero
folded columns. These times come from a contended host and are stage
observations, while the relation and source replay are exact.

The next N131 method must **use the target to restrict multiple pair
choices before building a five-leaf index or applying the compact pair
inverse**. Directly copying the N41
sample counts to the degree-131 subgroup has a uniform-target union-bound
success probability at most `1.058e-26`; even an idealized 600 billion
right-side probes raise it only to `3.174e-21`. That screen does not bound
the fixed published point or an adaptive method. The [N131 exact
second-link table](n131_d13_second_link_lookup_20261009/RESULT.md) remains
available as a verified propagation primitive. Freeze the adaptive method,
prove or measure its 4-GiB index and 600-second one-worker target-dependent
query, then obtain and independently replay an ordinary relation on the
exact d13 public target. Useful rank, factor logs, fresh-target DLP, and
matched same-point rho timing follow from that gate.

**D10 predecessor process gate (2026-10-09 22:04 UTC):** the
[exact-handle audit](n131_d10_v3_external_interruption_20261009/result.json)
found the recorded d10/m15 v3 solver PID 60681 absent, with its creation
time checked and 1,517,745 bytes of raw output retained. The output contains
zero SAT status and model lines. Surviving progress remains rank 0/532 with
zero completed attempts; the run has no terminal result receipt, and its
exact stop cause is unknown. The distinct d10 v1 continuation result is
`PRODUCER_FAILURE`; it satisfied the d13 runner's frozen predecessor gate.
Keep the v3 process-loss audit separate from that v1 terminal result.

**Current algorithmic result (2026-10-09):** exact fill-limited elimination
of CNF-private XOR variables reduces the frozen N131 public-Q d13/m12 formula
from 232,244 variables and 171,278 XOR rows to 112,342 variables and
51,376 XOR rows while retaining all 228,629 CNF clauses. The output has
748,344 XOR literal occurrences against 748,346 in the original, and occupies
10.3 MB against 30.1 MB for complete elimination. An
[independent pivot replay](fill_controlled_projection_20261009/n131_budget1/independent_elimination_audit.json)
matches all 119,902 saved elimination steps and every projected record.
The [N41 known-solution lift](fill_controlled_projection_20261009/n41_budget1/independent_control_audit.json)
passes, but the [unpinned N41 query](fill_controlled_projection_20261009/n41_budget1_unpinned_R1/independent_terminal_audit.json)
ended `CENSORED_TIME` after 240.096 solver-stage seconds with no model.
The [result and method](fill_controlled_projection_20261009/RESULT.md)
establish an exact, sparsity-controlled encoding; the next search method
must use the public target to restrict leaf choices and pass an ordinary
unpinned smaller-field relation gate before N131 promotion.

**Research goal:** obtain an unpinned, independently verified ordinary
factor-base relation on the exact degree-131 challenge curve, then recover
one previously unseen target scalar with a complete index-calculus pipeline.
The final performance gate is lower verified online wall time than a
same-point Pollard-rho solve under matched, isolated resources. The repository's
`AGENTS.md` defines the candidate IDs, measurement phases, and claim gates.
Status: active.

**Immediate measurable goal (2026-10-09):** obtain an unpinned,
independently checked ordinary factor-base decomposition of the frozen
published N131 target Q (workload `3c1992b7c92f`) within a one-worker,
600-second, 4-GiB combined-RSS query envelope. The measured high-density
[d13/m12 probe](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/RESULT.md)
uses 12 summands from exact d13 Frobenius domains, 1,083,108 usable base
points, and 4,134 folded columns. Its accepted-seed v4 attempt is the
zero-yield baseline. For a successor method, freeze the target-coupled
search rule, verify its ordinary N41 control, and record pruning, work,
memory, failures, and exact N131 input hashes before promotion. Count a
relation only after saved-formula assignment and independent installed-Sage
point-sum, subgroup, and factor-base checks. The complete d13/m12 candidate
`IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0h36143c49e85d`
remains downstream of this ordinary-relation gate; a successful predecessor
scalar would instead advance to its same-point rho comparison.

**Exact projected public-Q screen (2026-10-09):** the separate
[Q20261009171800 proposal](n131_d13_projected_public_q_20261009/projected_public_q_protocol.json)
eliminates CNF-private XOR variables from the frozen d13/m12 public-Q
formula. It retains all 228,629 CNF clauses while reducing 232,244
variables to 104,791 and 171,278 XOR rows to 43,825. The
[structure audit](n131_d13_projected_public_q_20261009/public_q_projection/independent_structure_audit.json)
checks the exact clause map and reverse lift order. A separate planted
assignment [passes](n131_d13_projected_public_q_20261009/planted_projection/independent_control_audit.json)
projected-record checking, reverse lifting, and every original XCNF record.
The one-worker, 540-second, 4-GiB public-Q solver stage has a terminal
`CENSORED_TIME` result with zero model lines. Its first saved launch exited
at argument parsing because
the inherited random seed exceeded CryptoMiniSat's accepted integer range;
the [terminal audit](n131_d13_projected_public_q_20261009/public_q_stage_run_R1/independent_terminal_audit.json)
classifies it as `PRODUCER_SOLVER_ARGUMENT_FAILURE`. The corrected R2
preflight passed; the [terminal audit](n131_d13_projected_public_q_20261009/public_q_stage_run_R2/independent_terminal_audit.json)
confirmed the censored outcome and peak combined RSS of 341,491,712 bytes. This is an
exploratory solver-stage diagnostic: its clock excludes target-dependent
formula construction and projection, so a successful relation still needs
a complete charged single-target interval for the primary comparison.

**R3 terminal status (2026-10-09 16:45 UTC):** the original R3 Sage runner
and CryptoMiniSat child have drained. The
[external interruption audit](n131_phi_torsion_frobenius_domains_20261005/continuation_20261009/r3_external_interruption_audit.json)
hashes the frozen query and raw logs: the solver emitted zero status and
model lines, and the surviving precomputation rank is 0/14. The
[terminal run row](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/result.json)
is `INTERRUPTED_RUNNER_LOST_RAW_SOLVER_OUTPUT_RETAINED`; exact stop cause and
charged precomputation wall time are unknown. This releases the frozen d10
predecessor gate. The d10 protocol allows 604,800 seconds per query and
remains a separate resource envelope from the immediate 600-second ordinary
relation goal.

The [exact R3 XOR analysis](n131_r3_xor_core_20261009/r3_xor_peeling_audit.json)
certifies rank 523,995 for all 523,995 XOR rows and a zero-row incidence
2-core. The [complete projection](xor_projection_20261009/n131_r3_projection/result.json)
of the saved N131 R3 XCNF retains all 1,054,158 CNF clauses while reducing
845,062 variables to 349,395 and 523,995 XOR rows to 28,328. The projected
file is 112,706,215 bytes versus 32,625,708 original bytes, so the
compression is in variables and rows, with denser equations and larger
storage. An [independent audit](xor_projection_20261009/n131_r3_projection/independent_structure_audit.json)
checks the exact clause map and inverse-lift order. CNF-private-variable
components expose thirteen independent
35,578-row leaf blocks and one 25,956-row block. A bounded sparse elimination
of one large leaf block reduced 35,578 XOR rows to 262 boundary equations in
3.18 seconds using 261 MB peak RSS, but produced 1,027,528 residual literal
occurrences. These are linear-encoding facts, not search timings. The next
method should use the block structure to constrain realizability with the
public target before leaf selection, with an unpinned smaller-field relation
and model lift as its promotion gate.

The [R3 model-recovery preflight](n131_phi_torsion_frobenius_domains_20261005/continuation_20261009/RESULT.md)
now makes any eventual raw solver model auditable: the exact saved R3 XCNF
rebuild passed, and the final decoder checked every XCNF record and
independently replayed the frozen planted control in Sage. The live R3
solver still has no model or relation; the planted pass is not natural yield.

If d13/m12 yields an ordinary row, next measure the distribution of failed
and verified ordinary queries and novel rank per query, solve and replay all
4,134 factor-base logs, then recover and independently verify Q's scalar.
Only a completed single-target online interval paired with a verified rho
solve of that same Q under an auditable isolation record can support the
headline speedup. If the d13 probe is censored or fails, retain that result
and require the next method to improve target-coupled search on an unpinned
smaller-field control before projecting it to N131; formula size and expected
tuple count alone are insufficient. The earlier
[N41 W2/m8 boundary result](N41_W2_M8_SEARCH_BOUNDARY_RESULT.md) is one
such small-field correctness control, not evidence of N131 yield.

**Exact d13 membership compression (2026-10-06):** proposal
[Q20261006153000](n131_phi_torsion_frobenius_domains_20261005/d13_m12_membership_cubes_20261006/RESULT.md)
replaces the 4,058 forbidden 13-bit selector minterms per leaf with 1,251
exact covering clauses. The public-Q formula loses 33,684 CNF clauses
while retaining every arithmetic clause and native XOR row. An independent
exhaustive selector audit and a complete planted-XCNF model check pass.
Its separate unpinned public-Q stage gate ran while R3 remained active
and ended `CENSORED_TIME` after 599.264 seconds with no model or relation;
the combined peak RSS was 1.436 GB. The independent audit verified the
saved input and zero-row result. This exploratory, contended stage
diagnostic has no candidate ID, full IC online interval, DLP, or speedup.
It does not replace the queued original d13 probe: the exact clause
compression did not clear search within the frozen limit, and its wall
time is not a controlled speed comparison.

**Fresh smaller-field full-pipeline control (2026-10-04):** proposal Q1330
used the exact N41 W2 base and a reusable signed-triple index to obtain two
independent ordinary setup equations, verify both factor logs, recover a
fresh public target scalar, and pass separate installed-Sage replay. A
one-worker signed-Frobenius rho run on the isomorphic representation of the
same point recovered the same scalar. The
[full result](N41_W2_INDEXED_FULL_PIPELINE_RESULT.md) preserves both arms,
exclusive provisional IC target phases, and the paired audit. Its IC
independent check was outside the producer clock, rho input conversion was
outside its native clock, and no CPU-isolation receipt exists, so controlled
online speedup remains unknown. This validates an N41 complete-pipeline
path. An [exact transfer screen](n41_w2_indexed_pipeline/n131_transfer_screen.json)
shows that m8 has at most a `1.176×10⁻¹⁵` uniform-target support fraction
on the official N131 W2 base, while the literal triple index remains far
beyond the N131 memory limit. N131 requires both a longer relation and a
different search structure.

**Official N131 W2 triple-quotient gate (2026-10-04):** proposal Q1333
reduces the literal signed-triple domain by Frobenius to 31,341,856
descriptors. Its frozen 6,000-sum correctness sample passed an independent
installed-Sage replay, and Sage verified the Frobenius eigenvalue on all
fourteen official base representatives. Exact symbolic counting finds
31,239,334 column-coefficient signatures after 102,522 algebraic duplicates.
A packed 17-byte x key plus four-byte descriptor would use 0.613 GiB of raw
array payload, but a full index and its target-conditioned search are unbuilt.
The [gate result](N131_W2_TRIPLE_QUOTIENT_GATE_RESULT.md) records the counts,
receipts, and biased-sample boundary. The next method gate is a frozen
target-coupled composition algorithm with a smaller-field ordinary-row
control and an N131 600-second/4-GiB preflight. A subsequent fixed-bucket
five-triple screen shows that the straightforward m15 join would need
40 filter bits per pair list under 4 GiB and retain only a modeled
`4.54×10⁻¹⁴` target solutions. Do not build the full quotient table solely
for that join. No ordinary N131 relation,
factor logs, DLP, or speedup follows from this quotient.

**Official W2 adjacent-pair macro gate (2026-10-04):** proposal Q1334
materialized 392 distinct output Frobenius classes and 102,704 signed
macro points as exact sums of the same B=3,668 / K=14 official factor base;
independent checked Sage reproduced the full point-set digest. A frozen
structural sample found 90.710% of ten-macro subsets keep all 20 original x
coordinates distinct, giving an estimated 47,941 valid representations per
uniform subgroup target. This is not fixed-Q yield. On the previously public
N41 point, Q1336's one-hot six-macro SAT circuit passed a planted control
only after its known intermediate sums were pinned; its unpinned ordinary
query timed out without a model at 118.979 s. Q1337 replaced absolute-x
one-hot membership with a class selector and Frobenius barrel rotation,
cutting N41 CNF clauses from 138,995 to 61,049 while retaining 28,727 XOR
rows. Its planted control passed and its unpinned ordinary query also timed
out without a model at 119.031 s. Both terminal rows and Sage replays are
in the [macro gate result](N131_W2_ADJACENT_MACRO_GATE_RESULT.md). The
barrel encoder projects 571,040 **domain-only** clauses for a ten-macro N131
circuit, but its full formula and search are unmeasured. The N41 ordinary
SAT search gate failed, so no N131 query is promoted. An exact Q1338 N41
`3+1+2` reference index then found and independently replayed a six-macro
ordinary row on that same public point after 6,174 prefixes and 3,538,048
probes in 109.639 target-dependent seconds. Pinning that verified witness
into Q1337's public-target formula passed in 0.181 seconds: the timeout was
search failure on a satisfiable instance, not absent target support. A
literal N131 pair index would need 83.50 GiB for raw 17-byte keys alone, and
its independently uniform residual support fraction is at most
`1.55×10⁻²⁹`, so it is only a small-field reference. The next method must make
macro pair realizability propagate with the target before full leaf
selection; no N131 relation, logs, scalar, or online speedup exists.

**Macro search and quotient follow-up (2026-10-04):** Q1339 changed the
same N41 six-macro barrel formula to a balanced S3 tree. Its planted control
and a pinned Q1338 public witness both passed, but the unpinned public query
again timed out without a model at 118.949 s. This was another search
failure on a satisfiable instance; no N131 query was promoted. Q1340 then
exhaustively checked the signed/Frobenius **pair quotient** on N41: 2,616
descriptors expanded to exactly the same output-x set as all 214,512 valid
raw pairs. The official N131 Q1334 macro geometry implies 20,129,592 pair
descriptor slots, 262 times fewer than raw signed pairs and 0.394 GiB of
17-byte key plus four-byte descriptor payload. This is an exact descriptor
count and a raw storage projection, not a built 4-GiB index or a fixed-Q
search. The [follow-up result](N131_W2_MACRO_PAIR_QUOTIENT_RESULT.md)
sets the next gate: build and verify the packed quotient index, make the
public target constrain multi-pair composition, pass an unpinned N41 row,
and preflight 600 s/4 GiB before N131. No ordinary N131 relation, factor
logs, scalar, or online speedup exists.

**Packed N131 macro-pair index (2026-10-04):** Q1341 completed the
target-independent part of that gate. Batched x-only arithmetic built all
20,129,592 quotient records for the exact official W2 macro geometry, then
sorted them into a 422,721,432-byte index. The frozen build finished in
766.033 s with 488,423,424 bytes observed peak RSS under its 1,800-s/4-GiB
precomputation caps. A full sorted-record scan and 134 direct point-add
samples passed; a separate installed-Sage process independently replayed
134 sorted records. The index has 19,951,147 distinct **stored
representative** x keys, with duplicate buckets up to 53 records; these
are not Frobenius-canonical orbit counts. The [stage result](N131_W2_MACRO_PAIR_PACKED_INDEX_RESULT.md)
preserves hashes and phase receipts. This establishes a reproducible index,
but no target-coupled ten-macro search or ordinary N131 relation. The next
small-field gate is an unpinned N41 public solve using three exact
macro-pair output domains; an N131 full-target query still requires a
credible 600-s/4-GiB method preflight. No factor logs, scalar, or online
IC/rho speedup exists.

**Three-pair target-coupled SAT gate (2026-10-04):** Q1342 used the exact
N41 sum domain of two W2 macros with four distinct underlying x values:
205,984 pair witnesses, 99,384 output x masks, and 2,424 Frobenius
classes. It represented the same public Q1338 point as three pair outputs
using only two S3 links. The known public row passed a pinned formula and
independent Sage replay, but the **unpinned** query returned no model at
119.114 s under its 120-s/4-GiB gate; observed combined peak was
760,627,200 bytes. The [full stage result](N41_W2_THREE_PAIR_SAT_GATE_RESULT.md)
preserves the terminal failure. Compact pair storage alone did not make
target-dependent search viable. Do not transfer this x-only SAT encoding to
the N131 public target; the next method needs earlier joint propagation of
pair realizability and Q. No ordinary N131 relation, logs, scalar, or
online speedup exists.

**Canonical macro-pair query index (2026-10-04):** Q1343 transformed Q1341's
20,129,592 official N131 pair descriptors into a Frobenius-canonical
422,721,432-byte index without changing the 21-byte record size. One x
query now uses one canonical-key bucket lookup and recovers the descriptor's
relative Frobenius rotation; the original representative-key layout
requires checking up to 131 rotations. The target-independent transform
finished in 28.953 s with 849 MB peak child RSS. An independent installed-
Sage replay checked the full sorted rank permutation, 38 exact group sums,
and 114 rotated queries; a separate query-API check passed 416 known
rotated queries and 100 random queries. The
[result](N131_W2_MACRO_PAIR_CANONICAL_INDEX_RESULT.md) preserves the
frozen source, binary hashes, receipts, and claim boundary. This makes
exact pair-output membership practical as a primitive, but still gives no
target-conditioned joint five-pair search. The next method gate remains an
unpinned, independently replayed N41 ordinary row from a search whose N131
five-pair work and memory can credibly fit one worker, 600 s, and 4 GiB.
Do not use a random four-pair prefix plus final-pair lookup as that method;
its independent residual coverage is negligible. No ordinary N131 relation,
logs, scalar, or IC/rho speedup exists.

**Canonical-index collision rank screen (2026-10-04):** Q1344 checked
whether Q1343's duplicate pair-output x keys could supply the 14 official
W2 factor-base logs without an ordinary target relation. A frozen full
scan of all 20,129,592 records found 123,886 multi-descriptor buckets
containing 317,394 records; every bucket had just one folded-column
coefficient signature up to sign after its Frobenius shift. Thus these
collisions produce zero novel relation rows in the built index. An
independent installed-Sage replay checked all 392 macros, the Frobenius
eigenvalue on all 14 base representatives, and 131 pair outputs in 33
sampled collision buckets, including a 57-record bucket. The
[full result](N131_W2_MACRO_PAIR_COLLISION_RANK_RESULT.md) records the
frozen protocol and terminal receipts. Keep duplicate witnesses for
leaf-disjoint target search, but do not use them as a factor-log rank
source. The next gate remains a genuinely target-conditioned joint
five-pair method; no N131 ordinary relation or factor logs exist.

**Final-pair residual bound (2026-10-04):** Q1345 independently counted
19,936,084 canonical x orbits in Q1343's complete index. They represent
5,223,254,008 signed subgroup points, a fraction
`7.674881974×10⁻³⁰` of the exact N131 subgroup. For a uniform target and
prefixes fixed independently of it, even a hypothetical one-nanosecond
query rate for 600 seconds gives a union-bound success probability below
`4.605×10⁻¹⁸`; independent-hit median work is about `9.031×10²⁸`
probes, 57.06 bits beyond that optimistic budget. The
[frozen result](N131_W2_MACRO_PAIR_RESIDUAL_BOUND_RESULT.md) separates
this exact support count from its distributional work model. It does not
bound an adaptive target-conditioned solver or the specific published Q.
Do not spend the N131 query budget on a nonadaptive four-pair prefix plus
final-pair lookup; the next method must couple Q before those choices.
No ordinary N131 relation, factor logs, scalar, or IC/rho speedup exists.

**Exact published-Q pair-domain check (2026-10-04):** Q1346 froze one lookup
of the official N131 target against Q1343's complete W2 macro-pair index. A
single Frobenius-canonical x query covers all 131 target orientations and
both y-sign lifts. It returned no descriptor. An independent implementation
then scanned all 20,129,592 records, verified sorted-key order and the complete
descriptor-rank permutation, and independently confirmed the zero bucket.
This rules out only a direct four-factor-base-point representation in this
exact pair-output domain; longer rows and target-adaptive multi-pair searches
remain open. Candidate and run IDs and cost fields stay null. The frozen
[protocol](n131_w2_macro_pair_canonical_index/target_membership_protocol.json),
[query result](n131_w2_macro_pair_canonical_index/target_membership_result.json),
and [independent full-index verification](n131_w2_macro_pair_canonical_index/target_membership_independent_verification.json)
preserve the one-target evidence.

**Exact N41 group-law method gate (2026-10-04):** An exact balanced
six-macro-point affine formula with free slopes passed a fully pinned known
row but timed out in 28.323 s when only its six leaves were pinned; its
ordinary query was not launched. A deterministic Itoh–Tsujii affine formula
then recovered that same leaf-pinned row in 0.249 s, with independent Sage
replay. Its unpinned ordinary-point query nevertheless returned no model in
118.840 s under one worker and 4 GiB (372,277,248 bytes observed combined
peak). The [method-gate result](N41_W2_GROUP_LAW_SAT_METHOD_GATE_RESULT.md)
records both frozen protocols, the Q1346 label collision and Q1348 alias for
the free-intermediate experiment, the Q1347 deterministic result, and the
strict claim boundary. The next gate is an unpinned verified N41 ordinary
row within 120 s/4 GiB from a target-conditioned method with credible N83
and N131 scaling; deterministic group-law propagation alone does not clear
search. No ordinary N131 relation, logs, scalar, or online speedup exists.

**Slope-witness N41 follow-up (2026-10-04):** Q1349 removed Q1347's five
inversion circuits and made every intermediate point a deterministic
function of five free slopes. The 32,821-variable formula was algebraically
correct on the known row and passed a post-run control with leaves and
slopes pinned, but its leaf-only control was time-censored at 28.328 s;
therefore no ordinary query ran. The [frozen result](N41_W2_SLOPE_WITNESS_GATE_RESULT.md)
preserves the timeout, complete formula statistics, exact row control,
source hashes, and Sage receipts. Smaller SAT size did not provide the
target-conditioned propagation needed at N41, so this encoding is not
promoted to N131. The next method must keep exact pair realizability
coupled to the target before committing a multi-pair prefix. No ordinary
N131 relation, rank, logs, scalar, or online speedup follows.

**Gaussian-matrix limit check (2026-10-04):** Q1350 kept Q1349's exact
leaf-only XCNF hash and raised CryptoMiniSat's maximum matrix rows from
6,000 to 20,000, columns from 18,000 to 25,000, and matrix count from
five to eight. The previously excluded 9,224×15,429 component was admitted,
but the known-row control still timed out at 28.667 s; observed combined
peak RSS rose from 132.5 MB to 463.4 MB. Its ordinary query was therefore
not launched. The [frozen paired result](N41_W2_SLOPE_GAUSS_GATE_RESULT.md)
preserves both solver logs and the exact common formula hash. This rules
out that matrix-size limit alone as the propagation fix; the next method
must couple exact pair realizability to the target at a stronger algebraic
level before another N131 promotion.

**Three-way batch-inversion group gate (2026-10-04):** Q1351 used one
Montgomery batch inverse for the three independent first-level macro pairs
and sequential inverses for the two upper additions. Its IR fell from
108,326 to 91,492 operations; the exact N41 leaf-only known-row control
still passed in 0.270 s. The unpinned ordinary solver returned
`INDETERMINATE` after 118.48 internal seconds with no model, but its parent
raised an RSS-read exception during shutdown. The [recovered terminal
result](N41_W2_BATCH_INVERSE_GATE_RESULT.md) preserves the producer failure
and keeps exact online wall, exclusive phases, and peak RSS null. Independent
installed Sage replay passed for the known relation and terminal audit.
This circuit reduction is not an N131 relation or a complete timing result;
the next method must change target-conditioned search rather than only
reduce inversion gates.

**Exact pair-output arity screen (2026-10-04):** Q20261004113601 reused Q1345's
independently checked 5,223,254,008-point official W2 pair-output set. For
a fixed set and a uniform independent subgroup target, the exact ordered
tuple count bounds support for one, two, and three pair outputs by
`7.67×10⁻³⁰`, `4.01×10⁻²⁰`, and `2.09×10⁻¹⁰`, respectively. Four and five
outputs have only the trivial upper bound 1; their tuple means do not prove
coverage or relation yield. The [frozen result](N131_W2_PAIR_ARITY_SUPPORT_RESULT.md)
and independent rational audit refine the next method gate to target-coupled
composition of at least four exact pair outputs on this route, first clearing
the N41 ordinary-row control and an N131 work/memory preflight. Earlier
`Q1352` and `Q1353` screen labels collided with concurrent N41 experiments;
the cited result was refrozen with a timestamp-derived proposal ID. No
ordinary N131 relation, factor logs, scalar, or online speedup follows.

**Quadratic pair-output constraint boundary (2026-10-04):** a frozen
Frobenius-rotated subset of the Q1343 official W2 pair-output index has
rank **8,516/8,647** on all degree-at-most-two Boolean x features. The
131-dimensional nullspace is exactly the multiples `xᵢ·Tr(x)` of the
already known subgroup trace-zero constraint. A separate 100,000-output
holdout had zero violations, and a full 20,129,592-record scan found no
odd-parity key. The [rank and exact-basis result](N131_W2_PAIR_QUADRATIC_COMPLETE_RESULT.md)
shows there is no additional quadratic x-only cut to add to this route;
the earlier m18 trace-only SAT stage already timed out. The next method
must use mixed factor-base seed/output equations or joint target-coupled
information. This is a structural gate, not an N131 relation or speedup.

**W2 orbit-leaf stage gate (2026-10-04):** the official B=3,668 base's
1,834 usable x coordinates are exactly fourteen full Frobenius rotations.
The isolated 14-class/rotation leaf encoder reproduced that exact set and
passed its SAT-domain and planted S3 controls. Its unqueried published-Q m17
formula saved 1.66% of bytes but added variables. The required smaller-field
ordinary-query comparison has now failed its gate: on one frozen N41 target,
both old and orbit encodings were time-censored near 118.8 seconds without a
model; orbit encoding added variables and peak RSS for only a 2.62% clause
reduction. The N131 R2 solver was active on the same host during both arms,
and no CPU-isolation receipt exists, so these times are exploratory. See the
[stage result](N131_W2_ORBIT_LEAF_GATE_RESULT.md) and the
[paired comparison](n41_w2_orbit_gate/paired_ordinary_comparison.json). Do
not query N131 with this encoding-only variant. The separate frozen W2/M15
full-pipeline run was last observed active on its reusable setup query; its
current liveness has not been verified here. No N131 ordinary relation,
factor log, DLP, or online IC/rho comparison exists yet.

**Latest official W2 summand-count gate (2026-10-04):** raising the same
official base's chained-S3 decomposition from m15 to m16 and m17 increased
the exact distinct-x signed-row mean over uniform subgroup targets from
about 311 to 70,613 and 15.1 million. Both new planted controls passed
complete XCNF and fresh checked-Sage replay. The unpinned published-Q m16
and m17 searches each ran one worker for about 590.2 target-dependent
seconds below 4 GiB but returned no model at the solver budget. The first
m16 planted attempt, pinned in the wrong lexicographic order, remains an
UNSAT control-input-error row; its corrected control passed before Q was
queried. The [paired stage result](N131_W2_SUMMAND_COUNT_GATE_RESULT.md)
and [exact support count](n131_w2_distinct_x_support_m14_m17.json) preserve
the receipts. More represented rows alone did not clear the ordinary-Q
search gate. The next method needs target-dependent pruning or elimination,
with a smaller-field ordinary control before another N131 query. No N131
factor logs, scalar, or IC/rho online speedup exists.

**Latest official m15 matrix gate (2026-10-04):** three frozen, paired
CryptoMiniSat settings on the same official-generator known-scalar
precomputation point all passed their planted formula and independent Sage
controls, but each ordinary probe hit the 4-GiB RSS cap without a model.
The wide 50,000×60,000/ten-matrix run stopped after 139.428 solver seconds
at a sampled 4,665,475,072-byte combined peak; limiting it to five
matrices stopped after 69.899 seconds, and excluding the largest matrix
with 30,000×45,000 limits stopped after 15.362 seconds. The caps did not
make this query viable. These are stage diagnostics on a reusable
precomputation point, not an official-Q online solve or a CPU speedup.
The [full result](N131_M15_GAUSSIAN_MATRIX_GATE_RESULT.md) preserves
all three terminal rows. A candidate-bound repeat on the same formula
selected the same ten matrices and stopped at 105.070 solver seconds with
4,539,170,816 bytes combined peak, 244,203,520 bytes above the cap. Its
pinned control and independent Sage replay passed, but the ordinary probe did
not return a model. The [candidate gate receipt](n131_w2_m15_official_gausswide_4g_20261003/candidate_gate_status.json)
preserves that separate run. The frozen wide-Gaussian full-pipeline candidate
was not launched; its solver-stage gate failed.

**Latest W2 Gaussian and row-acceptance result (2026-10-04):** on the
byte-identical published-Q seven-pair XCNF, a disk-backed solver alone still
hit 4 GiB, but raising Gaussian limits from 2,000×1,000 to 6,000×18,000
selected five 5,193×16,955 matrices and kept the ordinary 600-second search
under 1.83 GB. Its planted control passed full XCNF, group, and fresh
checked-Sage replay; the official-Q search returned no model at its time
limit. Separately, the official row verifier's old requirement that a
14-point row use all 14 folded columns was mathematically unnecessary.
An exact count gives only `262^14/r ≈ 1.06×10^-5` such rows per uniform
target, versus `C(3668,14)/r ≈ 1.31` unrestricted distinct-point rows and
`C(3668,15)/r ≈ 319.61` unrestricted 15-point rows. The live W2 replay
now accepts repeated columns; a 13-column/14-point constructed row passed
independent Sage. These are uniform-target counts and planted controls, not
measured ordinary yield on Q. The [full result](N131_W2_GAUSS_AND_COLUMN_GATE_RESULT.md)
preserves the failed solver rows, source hashes, and next-method implication.

**Latest N131 inverse-witness gate (2026-10-03):** replacing the six
forward S3 inversions by checked inverse witnesses cut the planted
last-fingerprint formula from 1,267,751 to 812,999 variables and from
2,894,309 to 2,047,445 clauses. A direct six-link root check passed, but
the planted SAT solve with witness words free returned no model at its
120-second cap. Replacing only the target-facing link also timed out.
Fixing that one inverse from the planted fixture solved in 3.812 seconds,
and fresh checked Sage independently replayed all 14 official-base points.
This confirms the encoding while identifying free-inverse propagation as
the bottleneck. The [stage result](N131_W2_INVERSE_WITNESS_RESULT.md)
preserves all failed rows. Per the frozen gate, no ordinary Q query was
launched for this variant; the separate m15 precomputation remains active.
The next method must retain or replace deterministic intermediate-root
propagation before another bounded challenge query.

**Official one-target candidate frozen (2026-10-03):** the active W2/m15
diagnostics used a deterministic generator different from the published
ECC2K-130 generator, so they could not establish a solve of the fixed public
challenge. An independent checked-Sage bridge now maps the exact published
polynomial-basis G and Q into the IC ONB and verifies both in the prime
subgroup. The prepared
[official single-target candidate](n131_w2_m15_official_single_target/README.md)
has IDs `EC1N131Ckb1heb5f1998f20b`,
`IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h5f2f038b5008`, and
`3c1992b7c92f`; its workload contains exactly that one published Q. The
official-generator factor-base rebuild has 3,668 usable points and 14 folded
columns, with the same point geometry as the earlier diagnostic base. The
candidate is frozen before any challenge-target query. It has produced no
ordinary relation, reusable factor logs, DLP, online solve, rho pair, or
speedup. Its separate official-generator m15 pinned planted control passed
within 4.88 seconds total (1.05 million clauses, 522,755 XOR rows, about 859
MiB combined solver/parent peak under the 4-GiB cap), and a fresh checked-Sage
process independently replayed its 15-leaf, 14-column row. The first control
attempt is retained as a harness-pin failure; run 2 is the passing receipt.
This is a wiring/correctness control, not natural relation yield. The
bounded query-only result below is the only completed ordinary m15 query; it
returned no row and is not a candidate DLP result.

**N41 ordinary-row gate passed (2026-10-03):** a single-target `RCwalk`
diagnostic on the frozen public N41 point used B=136 raw factor-base points
(K=34 folded columns), one worker, no pair/four-sum index, and a 4-GiB cap.
R1 preserved the original short-cycle failure; R2 preserved a 3,000,000-step
no-collision target search after its table walk stopped on a point repeat.
R3 changed the table stop rule to detect repeated augmented states, found a
cross-walk collision at table step 590,635 / target step 635,719, and replayed
the resulting 136-coefficient row to Q in producer arithmetic. The target
online interval, including coefficient recovery and producer group replay,
was **17.6919 s**; the reusable 1,000,000-state table setup was **25.6813 s**
outside that interval. Peak RSS was **509,509,632 bytes**. A fresh checked-Sage
process independently verified the target and every base point in the prime
subgroup and replayed the row to Q in 0.625 s (outside the online interval).
The [R3 result](n41_target_walk_relation_20261003/result_R3.json),
[frozen protocol](n41_target_walk_relation_20261003/protocol_R3.json), and
[independent replay](n41_target_walk_relation_20261003/independent_sage_replay_R3.json)
record this pass. It clears only the small-field operational gate; it is not
an N131 relation, complete DLP, candidate promotion, or speedup measurement.

**Official N131 bounded m15 query (2026-10-03):** the exact published Q was
queried once with the frozen m15/weight-two circuit, a single CryptoMiniSat
worker, one solve slice, a 600-second online cap, and a 4-GiB combined
Sage/solver RSS ceiling. The formula built in 1.05 million clauses, 523,122
XOR rows, and 844,189 variables. The solver reached its 590-second internal
budget; total target-online time was **591.193 s**, no model was returned, and
combined RSS peaked at **2,224,308,224 bytes**. The result is a censored
single-target query, not UNSAT or zero natural yield. The [protocol](n131_official_single_target_gate_20261003/protocol.json)
and [result](n131_official_single_target_gate_20261003/result.json) preserve
the full row. This clears the bounded work/memory preflight but not ordinary
relation yield. A separate 4-GiB full-pipeline candidate is frozen at
`IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658`; its
candidate-specific planted control passed and independently replayed. Its
long one-target run is not included in this gate result.
That candidate's R1 process is no longer live, but the run has no terminal
result record. At 2026-10-04 05:08 UTC, its recorded CryptoMiniSat PID 82077
was absent and the saved exec session was no longer queryable. The last saved
solver output ends at restart 2935 (modified 2026-10-04 02:48:32 UTC); stderr
is empty and no solver `result.json` exists. Its progress file still says
`RUNNING` at rank 0/14 and is stale. The official Q had not entered its online
interval. The [termination observation](n131_w2_m15_official_single_target_4g_20261003/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR1/termination_observation.json)
preserves the checks and unknown cause. No timeout status, UNSAT result, or
zero-yield conclusion can be drawn.

**Official N131 one-target candidate R2 active (2026-10-04):** a fresh run
was frozen before launch with the checked Sage runtime and the unchanged
single-target candidate/workload. Run ID:
`IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2`.
At 2026-10-04 07:11 UTC it remained on its first target-independent
factor-base-log query at rank 0/14. Its saved log advanced from CMS restart
4,199 at 07:03 to 4,507. The [07:11 progress observation](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_progress_observation_20261004T0711Z.json)
records the counter parse rule. The latest direct RSS sample remains 06:38.
Live macOS process samples measured 2,551,955,456 bytes
combined solver/Sage-parent RSS at 06:22 UTC, 2,423,390,208 bytes at 06:27 UTC,
2,570,354,688 bytes at 06:33 UTC, and 2,533,982,208 bytes at 06:38 UTC.
The latest leaves 1,760,985,088 bytes below the 4-GiB cap. See the [06:22 sample](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T0622Z.json),
[06:27 sample](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T0627Z.json),
[06:33 sample](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T0633Z.json),
and [06:38 sample](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T0638Z.json).
The active setup formula has 845,158 variables, 1,054,158 CNF records, and
524,091 XOR records in a 32,628,124-byte XCNF; the
[audit](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/precomputation/attempt_001/formula_audit_live.json)
records its SHA-256 and header-count check.
The run uses one solver worker and a seven-day per-query limit. These
sequential known-scalar setup queries are reusable factor-base preparation, not a multi-target
workload and not part of the official Q online interval. Its workload contains
exactly one previously unseen published Q; Q's online interval has not started, and its
scalar is not available to the solver. The
freeze audit passed for the candidate, protocol, canonical workload,
checked-Sage runtime, and all 13 source hashes. The runner starts the online
clock immediately before Q's target-dependent CNF encoding and stops after
independent scalar replay. The
[R2 freeze receipt](n131_w2_m15_official_single_target_4g_r2_20261004/run_R2_freeze_receipt.json),
[started record](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/started.json),
and [live solver log](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/precomputation/attempt_001/cryptominisat.stdout.txt)
preserve this state. Earlier full-pipeline R1 remains separately unresolved;
it is not counted as an R2 result. No relation, rank, DLP, online time, rho
pair, or speedup has yet been measured for R2.

**N131 CMS matrix audit (2026-10-04):** the R1 setup query's frozen XCNF
contains 1,054,158 CNF clauses and 525,396 native XOR rows (846,463 variables;
see the [formula audit](n131_w2_m15_official_single_target_4g_20261003/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR1/precomputation/attempt_001/formula_audit.json)
for its SHA-256 and record counts). The solver log shows the current
10,000-row/15,000-column Gaussian limits rejecting larger XOR components;
one later preprocessing snapshot in the current query's log selecting ten
65-by-81 matrices. An earlier paired m15 precomputation diagnostic with
50,000-row/60,000-column
setting used ten 27,276-by-44,919 matrices and peaked at 3,538,206,720 bytes,
versus 1,963,573,248 bytes with 10,000 rows/15,000 columns; neither found a
model in 300 seconds. Both used the same single generated point and solver
seed, but on an earlier diagnostic curve/workload, and the wide run's cap was
16 GiB. This is a paired solver-stage lead for a separate official-workload
candidate with an enforced 4-GiB limit, not a measured speedup. The
[matrix-frontier note](N131_CMS_GAUSS_MATRIX_FRONTIER_20261004.md) preserves
the diagnostics and follow-up gate. The official R1 process is absent with an
unresolved result, as recorded above; do not rely on its stale `RUNNING`
progress snapshot as evidence that it remains live.

**Official N131 wide-Gaussian candidate frozen (2026-10-04):** the new
candidate
`IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0hd42534190db2` preserves
the official one-target workload `3c1992b7c92f`, B=3,668, K=14, one worker,
and the combined 4-GiB cap while raising CMS Gaussian limits to 50,000 rows ×
60,000 columns. Its full identity hash is
`d42534190db2ce61a471e02bfb75ac60fa7e6e90a21437922bad646831607666`.
The [candidate directory](n131_w2_m15_official_gausswide_4g_20261003/)
contains the immutable manifest, exact source hashes, protocol, run control,
and planted-control protocol. Its one-target pinned control passed in 1.100 s
of solver time with 897,826,816 bytes combined peak RSS. A fresh separate
checked-Sage process independently rebuilt the factor base and replayed the
signed row to the planted Q.

The next one-point fixed-scalar precomputation probe reused the exact setup
point from the prior official R1 and selected ten Gaussian matrices: one
44,515×52,477 and nine 27,276×44,919. The solver stopped after 105.070 s with
`solver_stop_reason: rss_limit`; combined sampled peak was 4,539,170,816 bytes,
244,203,520 bytes above the 4-GiB cap. The wrapper's raw status is `budget`,
exit code is -15, and no model or relation was returned. This is a resource-cap
failure, not UNSAT or zero-yield evidence. The [terminal gate receipt](n131_w2_m15_official_gausswide_4g_20261003/candidate_gate_status.json)
and [matrix-log audit](n131_w2_m15_official_gausswide_4g_20261003/precomputation_probe/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0hd42534190db2W3c6fda2faf50R1/matrix_log_audit.json)
preserve the measurements. The published Q was not queried, and this candidate
has no ordinary relation, recovered factor-base-log rank, DLP, online time, or
speedup. The next gate is a distinct candidate with lower Gaussian thresholds,
followed by its one-target planted control, independent replay, and a fresh
single-point setup probe under 4 GiB.

**N131 W2 disk-backed solver replay (2026-10-04):** the frozen official-Q
functional-chain XCNF was replayed in a low-memory supervisor for one target,
with a 4-GiB combined RSS cap, one worker, and 2,000×1,000 Gaussian limits.
R1 has an interruption audit; R2 ended after 33.252963208 solver seconds with
`RESOURCE_CAP_NO_MODEL`, return code `-15`, and a combined peak of
4,360,601,600 bytes—65,634,304 bytes above the cap. No model was returned,
and the 141,566,644-byte XCNF hash remained unchanged. Removing the formula
builder from memory did not keep this W2 solver stage below the cap. The
earlier target-dependent formula build took 5.004998375 seconds and was
excluded from this solver-only replay, so complete one-target online time
remains unknown. This diagnostic has `candidate_id: null` and `run_id: null`;
it yields no verified N131 relation or speedup. See the
[disk-solver protocol and R2 result](N131_W2_DISK_SOLVER_PROTOCOL.md).

Operational gates: (1) return an unpinned ordinary N41 factor-base row from
a target-coupled solver without a quadratic pair or four-sum index — **passed**
by the R3 `RCwalk` result above, with exact producer and independent checked-
Sage replay within one worker, 120 seconds, and 4 GiB; (2) show a complete
work/memory bound and pass a planted N131 control before an unpinned ordinary
N131 relation attempt under a frozen 600-second/4-GiB envelope — **preflight
passed**, with the ordinary query censored without a row; (3) measure useful
ordinary N131 yield and rank, obtain verified factor logs, recover and
independently replay one fresh target scalar; (4) beat matched one-target rho
online, with canonical candidate/workload/run IDs and exclusive phase
accounting. A failed or timed-out gate stays in the ledger and cannot count
as a speedup.

**Latest N131 functional-chain boundary (2026-10-03):** six exact S3
two-root circuits replaced the five free intermediate x words in the
seven-pair W2 selector. Direct field/group arithmetic proved a planted
witness, but with all pair keys fixed and root choices free, SAT timed out
at 120 seconds; putting the six choices at low variable IDs also timed out.
Pinning the known six choices passed SAT and independent official-base Sage
replay. A target-independent all-zero root pattern had a separately
constructed planted fixture and passed the same checks. On the published
ordinary Q, its all-leaf-fingerprint variant hit 4 GiB after 141.112 s;
its last-leaf-only fingerprint variant hit 4 GiB after 44.823 s. Both are
resource stops with no model, not 600-second timeouts or evidence of zero
natural yield. The [full stage result](N131_W2_FUNCTIONAL_CHAIN_RESULT.md)
preserves the restricted-chart definition, source/runtime hashes, controls,
and failed rows. No ordinary N131 relation or DLP follows. The official m15
full-pipeline run above remains unresolved and separate from these diagnostics.

**Latest official-point all-leaf fingerprint result (2026-10-03):** all
seven exact W2 pair selectors were augmented with the 25-feature inverse
fingerprint and queried against the **published** ECC2K-130 point with no
pair or intermediate pins. Planted controls under both installed and
corrected affine IR emitters passed independent checked-Sage replay in the
official 3,668-point base. On the same official one-point workload and
600-second/4-GiB envelope, both ordinary searches returned no model. The
affine emitter cut XOR rows from 233,537 to 78,250 and combined peak RSS
from 3.15 to 2.04 GB, but its 30,913-row XOR component still exceeded the
frozen Gaussian cap. The [paired stage result](N131_W2_FINGERPRINT_OFFICIAL_QUERY_RESULT.md)
preserves both censored rows and the first misconfigured affine-control
attempt. No ordinary N131 relation, logs, scalar, or IC/rho speedup follows.
The separate N41 RCwalk row above clears its small-field gate but does not
transfer a relation to N131. The next N131 method gate needs stronger
target-coupled elimination, not another local selector or XOR-size change.

**Latest N131 W2 inverse-propagation result (2026-10-03):** an exact,
rotation-invariant quadratic fingerprint distinguishes all 25,634 pair-x
orbit keys using 25 selected parity features. On one planted pair with x
fixed, the prior key/rotation inverse timed out at 60 seconds; the augmented
formula recovered and replayed the exact key/rotation in 0.778 seconds. In
the seven-pair planted S3 control with six pairs and four intermediates
pinned, adding the fingerprint to the last leaf changed the last-x-fixed
120-second timeout to a 20.345-second verified solve. With last x also free,
the augmented control recovered that leaf in 114.896 seconds under 1.69 GB;
the prior formula timed out. Both full models passed independent checked-Sage
replay for 14 subgroup points and 14 folded columns. The [full stage result](N131_W2_PAIR_FINGERPRINT_INVERSE_RESULT.md)
retains exact formulas and censored rows. This is planted inverse
propagation, not natural yield: six pair witnesses and four intermediates
were fixed, and the official challenge candidate has not used this method.
The immediate gate is an unpinned ordinary row from target-coupled
elimination, then the existing verified one-target IC/rho goal.

**Latest N131 12-column selector test (2026-10-03):** the exact
at-least-12 folded-column restriction was encoded both as 98 wide XOR
membership rows and through 105 pair categories per slot. Both pinned
N131 controls passed full XCNF and custom group replay; independent
checked Sage also verified all 14 points and the folded sum for the
category control. On the same ordinary public target, the wide-XOR
encoding crossed 4 GiB after 28.763 seconds, while the category
encoding stayed below the cap (3,308,945,408-byte combined peak) but
reached its 600-second solver limit without a model. The [paired stage
result](N131_W2_PAIR_COVERAGE12_RESULT.md) preserves both censored rows.
The heuristic 2,523-row density prediction has no measured yield behind
it; column occupancy alone has not cleared the ordinary relation gate.
The next method needs target-coupled elimination and an unpinned N41
control, rather than another occupancy-only encoding.

**Latest N131 selector solver-cap diagnostic (2026-10-03):** on the same
frozen ordinary one-target XCNF, reducing CryptoMiniSat's Gaussian matrix
limits from 50,000/200,000 to 2,000/1,000 kept the observed combined RSS
at 2,008,662,016 bytes through at least 597.032 seconds, versus the
wide-matrix trial's 4,351,344,640-byte resource stop at 263.681 seconds.
The default-cap solver emitted no status or model, and a post-exit monitor
bug prevented a terminal receipt; the preserved evidence is classified as
`PRODUCER_FAILURE_NO_MODEL_OBSERVED`. The monitor has been corrected for
future runs. This [stage result](N131_W2_SELECTOR_DEFAULT_GAUSS_RESULT.md)
shows a memory reduction but no ordinary relation, DLP, or online speedup.
The next search change must improve target-coupled elimination rather than
only solver memory settings. An [exact column-coverage count](n131_w2_column_coverage/result.json)
suggests at-least-12 distinct folded columns as a bounded **proposal**:
the uniform-sum heuristic predicts about 2,523 target rows while filtering
98.6% of seven-pair key tuples. No target-coupled solver gain or ordinary
yield has been measured from that restriction.

**Latest N131 W2 pair-domain rank screen (2026-10-03):** all 25,634 exact
canonical pair-output x keys have affine dimension 126. Their complete
degree-at-most-two Boolean feature matrix has rank 8,002, exactly the
maximum on that affine hull, so output-only quadratic equations add no
pair selectivity. Three local 48-bit cubic windows were measured: the low
and middle windows had full rank; the high-window deficit was comparable
to two matched random-canonical controls and vanished after rotating the
actual keys. The [rank result](N131_W2_PAIR_LOW_DEGREE_RANK_RESULT.md) does
not establish a pair-specific compact cubic gate. The next solver must
retain exact pair input/orbit information in its target-coupled elimination.
No ordinary N131 relation or complete DLP follows from this screen.

**Latest exact sum-root pair gate (2026-10-03):** the same-rotation N41
pair was reparameterized by `U=w1+w2` and one root `V=w1`, with exact
product `P=V²+UV` and pair-order symmetry breaking. Its pinned natural
control passed SAT, all 18,667 CNF clauses and 6,016 XOR rows, and exact
group lift. The unpinned ordinary solver slice reached a 140-second
external guard with no model. [Corrected stage accounting](N41_SUM_ROOT_PAIR_GATE_RESULT.md)
leaves full target-online time unknown because the executed runner built
its target-dependent formula before the timed slice. This is an invertible
seed reparameterization with the same 5,553 AND gates as the earlier exact
pair circuit; it does not supply the missing target-conditioned elimination.
No N131 ordinary relation or complete DLP was produced.

**Latest relaxed pair-gate screen (2026-10-03):** a target-coupled N41
same-rotation S3 circuit with independent six-bit seed-sum and eleven-bit
product-span variables passed its fully pinned SAT, complete CNF/XOR replay,
and exact group-lift control. Its public-only ordinary solve was censored by
an external 140-second timeout without a recorded model. Exact N41
enumeration found only 1,956 normalized pair outputs, while the full-rank
relaxed gate admits about 262,144 under a uniform model. At N131/W27, 64
sampled gates had rank 81; the same model admits about `2^81` coordinates,
roughly 67.1 million times the loose upper bound from all exact unrotated
raw pairs. The [result](N41_RELAXED_PAIR_GATE_RESULT.md) parks this relaxation.
The next method gate must retain exact product–seed consistency, find an
unpinned ordinary N41 row, and provide a complete N131 work/memory estimate
before another challenge-width solve. No ordinary N131 relation or full DLP
has been verified by this experiment.

**Latest N131 W2 pair-inverse boundary (2026-10-03):** the exact pair
quotient now has a [callable inverse](N131_W2_PAIR_INVERSE_RESULT.md)
that recovered signed source points and folded columns for all 55,020
normalized controls and 128 additional Frobenius rotations. Its
independently checked pair-sum support is exactly 6,716,109 subgroup
points including identity, or about `2^-106.32` of the group. Hence
one billion residual probes from a target-independent prefix schedule
have a uniform-target union upper bound below `9.87×10^-24`. This
eliminates blind last-pair probing as the next method, while leaving a
target-adaptive joint pair solver open. No ordinary N131 relation,
factor logs, scalar, or matched one-target IC/rho result exists yet.

**Latest one-target correction-search gate (2026-10-03):** a new iterative
finite-difference method started from uniform 48-bit N41 slot states and
repeatedly solved the complete affine first-order correction space for one
frozen public point. On its fixed 120-second online interval, the
checked-Sage-launched run scored 669,002 corrected states over 5,122
iterations and 2,166 restarts, but found no exact eight-distinct-column
relation; its best target-coordinate residual was five bits. This does not
clear the unpinned ordinary-row gate, and the method is parked rather than
transferred to N131. Two prelaunch failures and one timed producer failure
are retained separately. No ECC2K-130 relation, factor logs, scalar, or
IC/rho speedup follows.

**Latest exact N131 W2 pair-domain result (2026-10-03):** simultaneous
Frobenius quotienting of every signed two-point W2 sum produced an exact
25,634-entry output-x orbit index from 55,020 normalized descriptors.
[Independent checked Sage](N131_W2_PAIR_FROBENIUS_QUOTIENT_RESULT.md)
replayed the complete map and showed that every output orbit determines
one folded-column pair. This supplies a compact, exact pair witness
decoder. A direct BDD for its 131-bit seed set needs 2,489,269 decision
nodes per pair slot, so ninefold replication is not the next 4-GiB
solver route. The next gate is a compact **target-coupled** use of the
pair inverse, tested first on a frozen ordinary small-field query and
then on N131. No N131 ordinary relation, factor logs, recovered scalar,
or single-target IC/rho speedup has been verified.

**Latest W2 exact pair-selector result (2026-10-03):** a one-hot key plus
Frobenius-rotation encoding turns the complete 25,634-orbit pair index into
S3 leaves while preserving exact source-point witnesses and the 14-column
matrix. The pinned seven-pair control passed SAT and exact group replay,
including a proper nonzero row over all 14 folded columns. The ordinary
single-Q searches found no model: seven pair leaves reached 600 seconds at
1.39 GB under conservative Gaussian limits, and eight leaves reached 600
seconds at 1.08 GB; nine and ten leaves also reached 600 seconds without a
model at 2.12 and 2.42 GB. Two wider-Gaussian seven-leaf trials hit their
2/4-GiB RSS caps earlier. This proves the selector wiring, not useful
natural-target yield; increasing the leaf count alone did not clear the
relation gate. Q-specific formula construction took 4.082–6.899 seconds;
the retained query-stage wall also includes formula writing and solver
launch, so none is an IC online time. The
[full result](N131_W2_PAIR_SELECTOR_RESULT.md) retains formulas, receipts,
and censored outcomes. There is still no N131 relation for ordinary Q,
prepared factor logs, recovered scalar, complete IC online interval, or
paired one-target rho comparison.

**Latest N131 balanced-tree result (2026-10-03):** an isolated m18 S3
builder shortened every target-to-leaf path to four or five links while
keeping the exact W2 base and affine-XOR gate counts. Its planted 18-point
control passed full CNF/XOR replay. On the same ordinary precomputation
point and frozen 300-second/4-GiB envelope, the
[balanced-tree query](N131_W2_M18_BALANCED_AFFINE_RESULT.md) returned zero
models, as did the left chain. Its largest XOR component fell from 26,363
to 17,419 rows, but topology alone did not clear the N131 relation gate.
Future solver work must add earlier target-dependent restrictions on
realizable factor-base pairs; no factor logs, target scalar, or matched
single-target IC/rho result has been established.

**Latest N131 wide-Gaussian test (2026-10-03):** on the byte-identical
affine-XOR W2/m18 ordinary formula, raising CryptoMiniSat's matrix limits
selected the formerly rejected 26,363 × 34,584 XOR component. The
[paired wide-Gaussian result](N131_W2_M18_AFFINE_WIDEGAUSS_RESULT.md)
reached the same 300-second budget with zero models while combined peak RSS
rose from 1,027 to 1,620 MiB. The encoding improvement is retained, but
this solver setting did not produce an N131 relation. The next method gate
is stronger target-coupled decomposition under the bounded N131 preflight;
factor logs, scalar recovery, and matched one-target IC/rho comparison
remain open.

**Latest N131 XOR-encoding improvement (2026-10-03):** an isolated affine
emitter inlined bounded single-use XOR wiring in the exact W2/m18 S3
formula. On the same ordinary precomputation point, it cut Boolean
variables from 1,033,081 to 572,728, XOR rows from 639,489 to 179,136,
and XCNF bytes by 21.3%, while keeping CNF clause count unchanged. The
known 18-point control passed full model replay in 3.259 seconds versus
7.687 seconds for the installed emitter; an exhaustive small-gate check
also passed. The [paired result](N131_W2_M18_AFFINE_XOR_RESULT.md) records
lower peak memory but **zero models at the 300-second unpinned limit** in
both cases. Formula size improved; ordinary relation recovery remains
unproven. No factor logs, scalar, or single-target IC/rho speedup follows.

**Latest N131 intermediate subgroup cut (2026-10-03):** the m18 chained-S3
formula omitted a necessary trace-zero condition on each of its 16
intermediate x coordinates. An isolated variant added exactly 16 parity
XOR rows. A pinned 18-point control passed complete CNF/XOR replay, and
independent checked Sage verified that every generator has trace one and
that all 16 planted partial sums have trace zero. The sound
[trace-cut result](N131_W2_M18_INTERMEDIATE_TRACE_RESULT.md) nevertheless
reached its paired 300-second ordinary-point budget with zero models,
like the original m18 formula. This narrows the solver bottleneck without
establishing measured yield, an N131 ordinary relation, or any IC/rho
speedup. The full one-target goal remains active.

**Latest N131 summand-density stage (2026-10-03):** on the same exact
weight-two base and ordinary precomputation public point, chained-S3 m15,
m16, and m18 SAT searches each reached a paired 300-second limit with zero
models. The uniform-sum expected labeled-row estimates rise from 310.56 to
70,612.83 to about 3.049 billion, but these are not measured target yields.
The [stage comparison](N131_W2_SUMMAND_DENSITY_STAGE_RESULT.md) retains
formula sizes, process memory and the censored outcomes. A separate m18
planted control passed full XCNF replay, and independent checked Sage
verified 18 subgroup points and all 16 intermediate sums. Thus the m18
formula represents a known group relation, but adding summands alone has
not cleared the unpinned ordinary N131 solver gate within 300 seconds.
The seven-day V14 and W2/m15 searches remain separate live trials; no
N131 ordinary relation, factor logs, recovered scalar, or paired online
IC/rho speedup has been verified.

**Latest functional signed-point gate (2026-10-03):** a deterministic
Itoh–Tsujii slope circuit passed the known-row control with only eight
signed-pair selectors fixed, including full XCNF and group replay. Its
unpinned N41 ordinary-target search reached the 120-second cap without a
model, as did the smaller free-slope signed-point formula. The
[paired stage result](N41_MIXED_S16_SIGNED_PAIR_FUNCTIONAL_RESULT.md) shows
that removing 287 free slope bits increased formula size about 3.8-fold
without clearing the toy search gate. Both public times are censored, so
there is no solver speed ranking. The next method gate is an unpinned,
independently verified ordinary N41 relation from a compact target-coupled
solver under the same 120-second/4-GiB envelope, followed by an N131
representation that passes a
600-second/4-GiB preflight and yields an unpinned ordinary N131 relation.
The overall goal remains a verified single-target N131 scalar recovery and
matched one-target IC/rho online comparison; no such result exists yet.

**Latest oracle-assisted propagation test (2026-10-03):** checked Sage mapped
all N41 mixed-S16 first-pair raw lifts to their signed projected states and
bottom S3 `u` values. An oracle-derived 35-value `u` subset rejects 50 of
the 80 impossible first-pair states, while 30 negatives share output values
with positives. A public SAT formula with this target-specific constraint,
all primary variables free, still reached its 120-second cap without a
model; the pinned ordinary-row control passed full XCNF/group replay. The
[result](N41_MIXED_S16_TARGET_U_ORACLE_RESULT.md) charges the prerequisite
19.622-second exact oracle separately. Output-only membership, even when
derived from an already solved target, does not clear the toy solver gate.
The next method must retain signed pair identity or jointly eliminate
pair-input and target conditions, then pass a full N131 preflight.

**Latest target-conditioned completion measurement (2026-10-03):** the exact
mixed-S16 N41 reference join was extended from first-hit mode to an
exhaustive one-target scan. It finished all 24,576,000 last-half probes in
19.622 seconds after a reusable 1,105,920-entry first-half index and found
53 verified labeled rows across 40 of 120 first-pair states. Checked Sage
independently replayed a complete row for each positive state. The
[full result](N41_MIXED_S16_FIRST_PAIR_COMPLETION_RESULT.md) measures 66.7%
exact target-dependent rejection at two-leaf depth on the ordinary toy
point. On the selected N131 mixed policy, 63,000 first-pair choices and the
28.376 group-wide mean imply an average positive fraction no greater than
0.0451% under a uniform target law; this is not a fixed-target prediction.
The literal N41 index is not scalable. A compact target-coupled oracle that
fits the N131 600-second/4-GiB gate is still missing. A fixed-target
[low-degree selector audit](N41_MIXED_S16_FIRST_PAIR_COMPLETION_RESULT.md)
shows that linear equalities reject none of the 80 impossible N41 first
pairs; quadratic equalities preserving all 40 positive states can reject
only eight. Cubic interpolation can separate the toy truth table only after
the exact oracle has already supplied it, so it is not an online method.

**Latest pair-domain propagation gate (2026-10-03):** checked Sage completed
all eight N41 mixed-S16 raw pair domains. A sound 12-bit pair-output-prefix
BDD and a stronger complete 40-bit pair-output BDD each pass a planted
control, yet each unpinned search on the same ordinary public N41 point
reached its 120-second limit without a model. Copies of both public formulas
with the already verified ordinary row's 644 primary units appended solve in
0.145 and 0.120 seconds and pass full XCNF/group replay. The
[full result](N41_MIXED_S16_PAIR_BDD_RESULT.md) shows that more precise,
target-independent pair membership does not clear this small search gate.
The next method must couple the public target to pair realizability earlier,
produce an unpinned N41 row, and pass a bounded N131 preflight. No ordinary
N131 relation, factor logs, target scalar, or paired one-target IC/rho timing
exists; candidate/run IDs remain null.

**Latest mixed sixteen-leaf toy gate (2026-10-03):** the exact N41 analogue
of the mixed N131 policy has checked-Sage `B=136`, `K=34`. On the same
previously frozen ordinary N41 public point, both a balanced S3 SAT
formula and a forward-computed pair-root SAT formula reached their
120-second one-worker caps with no model. An exact toy 4+4 reference join
then found a sixteen-point row in 0.09149 seconds of target-dependent
lookup after a reusable 1,105,920-entry index, and independent checked
Sage verified all points, columns, target sum, and fixture scalar. The
[full result](N41_AFFINE_MIXED_W3_W4_S16_RESULT.md) proves target support
and isolates unpinned seed search as the unresolved solver gate. A
[checked-Sage and SAT coverage control](N41_AFFINE_MIXED_S16_ORDINARY_WITNESS_RESULT.md)
also proves that this ordinary row satisfies both frozen public formulas;
with its primary choices pinned, both return complete verified models in
under one second of solver time. Their original unpinned timeouts remain
censored. The exact join
does not scale to N131 under 4 GiB; no N131 ordinary relation, factor
logs, scalar, or paired one-target IC/rho result follows.

**Latest exact N131 policy screen (2026-10-02):** a target-independent
[mixed W8/W9 sixteen-leaf policy](N131_MIXED_W8_W9_S16_RESULT.md) now has
checked-Sage actual `B=5,576` and folded `K=1,394` on the exact challenge
subgroup under the `h136f03e58c98` curve record. Its eight local pair
domains and their nested W9 superset were
enumerated and audited. The selected policy uses 134 nominal leaf-mask
bits and has a uniform-sum arithmetic mean of 28.376 labeled rows per
group point; that is not measured ordinary-target yield. Its literal
balanced join remains at least 855,652,512,935 times above the 4-GiB
bare-key capacity. All eight complete even-u domains have full
degree-at-most-two feature rank 8,516 on their 130 free bits, removing
output-only quadratic local filters from this route. The next solver
must keep pair inputs and the public target together; require an unpinned
ordinary N41 row and a bounded N131 preflight before any N131 ordinary
query. No N131 relation, logs, scalar, or paired rho timing is established;
candidate and run IDs remain null.

An [input/output quadratic gate](N131_MIXED_W8_PAIR_JOINT_QUADRATIC_RESULT.md)
also found full feature rank 10,732/10,732 on all 31,500 mask/output rows
of mixed W8 pair 0, independently confirmed by checked-Sage row replay
and Python elimination. This rules out a quadratic local filter for that
pair's two seed masks and even-`u` output; it does not rule out cubic S3
constraints or other pairs. The ordinary N131 relation gate remains open.

The policy screen uses curve ID `EC1N131Ckb1h136f03e58c98`; the concurrent
V14 run below uses `EC1N131Ckb1h155d3f35afb8` because its generator differs.
Their field, equation, and subgroup match, but a future candidate or paired
workload must bind to one exact generator and curve ID.

**Current one-target continuation (2026-10-02):** the V14 N131 eight-leaf
formula is running against one ordinary target with a seven-day solver
ceiling, one worker, and a 4-GiB solver-plus-supervisor RSS guard. An identity
audit found that the original formula report and run protocol label its target
as workload `cc09e7eb202a`, although the actual point is the older W27 fixture
`(1355423786541859459261381388617191999353,
2148501774881016834676288718946084235950)`. The frozen `cc09` workload uses a
different point and generator. Under the current canonical identity rules,
the actual target's curve ID is
`EC1N131Ckb1h155d3f35afb8` and its one-target workload ID is
`fd70f5065828`; the exact records, hashes, and independent fixture-replay
evidence are in the append-only
[identity reconciliation](v14_eightleaf_public_search/ordinary_attempt_7d_single_retry1/identity_reconciliation.json).
The existing run files remain intact. The formula metadata also incorrectly
marks target-generation exclusion false; the point was generated and replayed
as a fixture before solver timing, so target generation is excluded. Do not
pair this run under the legacy `cc09` label. Its previous 1,800-second solver
limit and 1,002.914-ms target-dependent formula build remain charged to this
actual point; process launch and XCNF loading remain outside any claimed
online interval. Supervisor and wrapper failures are preserved separately.
This is still only a relation-search stage: no candidate/run ID, verified
relation, scalar, or IC/rho speedup is claimed.

**Latest N83 planted-control result (2026-10-02):** the frozen Q1108 one-target
five-summand planted SAT attempt exited `INDETERMINATE` at its 200,000-conflict
limit after 38.972 seconds, without a model. The run is terminal under its
one-attempt protocol; it is neither UNSAT nor evidence about ordinary relation
yield. The [result note](../koblitz-n83-index-design-20260929/Q1108_N83_ONB_SEED_PDP5_S6_PLANTED_CONTROL_RESULT.md)
records the stage receipt. This closes that planted solver control without
advancing N131; the ECC2K-130 single-target relation, logs, scalar, and paired
rho gates remain open. Candidate, workload, and run IDs remain null.

**Latest torsion-branch identity (2026-10-02):** the complete raw-target
preimage set is an order-four torsion coset. Independent checked Sage
verified all four classes for the frozen N41 near-pair target and for the
exact N131 ordinary workload `cc09e7eb202a`. The [full result](N41_N131_RAW_TORSION_COSET_RESULT.md)
proves that a root-level one- or two-bit torsion character only routes raw
tuples among the four branches; it does not prune their union. The exact
N41 distinct-column count is 279,727,983,360 labeled eight-mask tuples,
of which 11,491,200 have all-even raw characters. The next method must
couple the public point and pair-input restrictions *within* a branch
before three leaves are fixed. No ordinary N131 relation, factor logs,
scalar, or matched IC/rho timing exists; candidate and run IDs remain null.

**Latest target-conditioned prefix oracle (2026-10-02):** an exact N41
eight-leaf oracle classifies every first-pair state on the frozen ordinary
public point. It rejects 3,788 of 3,912 two-leaf prefixes (96.8303%), and
checked Sage replays all 124 reported positive completions. Two complete
sweeps take 11.232–12.553 seconds after a reusable 12,668,544-row/407.6-MB middle-four
index. The [result](N41_FIRST_PAIR_COMPLETION_ORACLE_RESULT.md) proves a
useful early decision exists, but the literal index does not transfer to
the exact N131 W18 near-pair base: even a bare-key middle-four table has a
rigorous distinct-column lower bound of 4.7279×10^21 rows. The next gate is
a compact target-conditioned replacement with a 4-GiB/600-second N131
preflight and independent unpinned ordinary relation replay. No N131
relation, factor logs, scalar, or matched speedup is established;
`candidate_id` and `run_id` remain null.

**Latest prefix-algebra gate (2026-10-02):** the 124 exactly completable N41
first-pair prefixes have full rank 106 across every Boolean monomial of
degree at most two in their 14 seed/sign bits; all 3,912 admissible prefixes
also have rank 106. Native bitset elimination and independent checked-Sage
GF(2) matrix ranks agree. Therefore no sound nonzero prefix-only quadratic
equality can prune the frozen ordinary target's first-pair states. The
[rank result](N41_FIRST_PAIR_COMPLETION_ORACLE_RESULT.md) excludes that
specific compact replacement, including invertible linear sum/overlap
coordinates. It leaves joint equations involving remaining pairs and
higher-degree target-conditioned elimination open. No N131 ordinary
relation or complete DLP result follows.

**Latest joint quadratic solver gate (2026-10-02):** the frozen four-pair N41
degree-two equations were translated exactly to 9,984 shared AND gates,
31,496 CNF clauses, and 498 native XOR rows, with exact seed-rationality
and distinct-column clauses. The known ordinary row passes the whole
formula and an independent symbolic translation audit passes. The unpinned
public search still returned `INDETERMINATE` after its 120-second solver
timer (121.969 s process wall, 443 MB direct RSS); even a 15-second
all-eight-mask-pinned control returned `INDETERMINATE`. The
[result](N41_W6_S8_SHARED_AND_SAT_RESULT.md) preserves the failed first
launcher and calibrated retry. This closes a direct Msolve-to-XOR/AND
translation as a sufficient improvement; native local elimination must
remove intermediate-coordinate search and couple the remaining pair
inputs to the public target before N131 promotion. No N131 ordinary row
or complete IC/rho result exists.

**Latest joint linearization gate (2026-10-02):** on that same populated
N41 four-pair system, fixing the first pair's twelve mask bits and lifting
every remaining degree-two monomial to an independent GF(2) variable
rejects **zero** of the 978 rational, distinct-column first-pair choices.
The [full result](N41_W6_S8_LINEARIZED_PREFIX_GATE_RESULT.md) checked all
4,096 Boolean assignments: coefficient and augmented ranks are 413 in
every case. Its 85 symbolic row dependencies are full source-polynomial
identities, independently verified by checked Sage, which also replayed
four representative matrix ranks. This excludes plain degree-two rank
consistency as the missing early propagator for this exact N41 branch;
the next method must preserve nonlinear multiplication or grow degree
while coupling other pairs to the target. It is no N131 yield or DLP
claim.

**Latest selected degree-three prefix gate (2026-10-02):** multiplying the
frozen N41 four-pair equations by the next 6, 12, or 24 leaf-mask variables
also cannot reject a first-pair assignment by lifted GF(2) rank
consistency. A [prefix-independent-column certificate](N41_W6_S8_DEGREE3_PREFIX_GATE_RESULT.md)
reaches ranks 2,891, 5,369, and 10,325, exactly the upper bounds from the
85 independently verified raw-polynomial identities and their multiples.
It proves equal coefficient and augmented ranks for all 4,096 first-pair
bit assignments on this selected N41 target branch; the largest bounded
proof run completed in 29.092 seconds and 1.20 GB sampled direct RSS.
This excludes these specific first multiples as the needed early
propagator, not the full degree-three closure or nonlinear constraints.
The constructive gate remains a target-coupled unpinned ordinary N41 row
before N131 promotion; no N131 relation or DLP result follows.

**Latest raw trace-character gate (2026-10-02):** the full rational-point
character `Tr(x)` gives an exact XOR across raw summands and each raw
target preimage. On the frozen N41 near-pair base, checked Sage verified all
256 allowed slot masks, four preimages, and 128 random group sums. The
[same-input public solver trial](N41_NEAR_PAIR_RAW_TRACE_GATE_RESULT.md)
added only 7,300 formula bytes but hit the 120-second online cap across all
four preimages without a model; the baseline was also censored. Each slot
has both trace bits (12 zero, 20 one), so the character equation alone
cannot reject any prefix while a slot is unassigned. It is sound but does
not meet the required early target-dependent pruning gate. No N131 ordinary
relation, factor logs, challenge scalar, or paired online IC/rho timing
exists; candidate and run IDs remain null.

**Latest sum/overlap representation gate (2026-10-02):** an exact invertible
N41 adjacent-pair coordinate change passed the known ordinary-row XCNF
control and 256 full-assignment equivalence checks. But its [whole-system
result](N41_SUM_OVERLAP_NORMAL_FORM_RESULT.md) removes only 56 of 106,385
equation term occurrences, adds 36 AND gates, and increases serialized bytes
by 2.325%. It is not an early target-dependent propagator, so the monolithic
coordinate change is parked without another 120-second solver run. The
conditional fixed-sum inverse remains available for a future joint method
that generates pair outputs from the public target. No N131 ordinary relation,
factor logs, scalar, or matched IC/rho timing exists; candidate and run IDs
remain null.

**Latest N41 solver and group-hash screen (2026-10-02):** four 30-second,
one-worker trials of the same unpinned, column-aware public-target formula
tested two CryptoMiniSat seeds with and without a larger XOR-matrix
allowance. All four were [censored without a model](N41_COLUMN_SOLVER_PORTFOLIO_RESULT.md)
at a combined 120.081 seconds of solver-only wall. This provides no
successful relation or solver-time ranking and leaves the target-coupled
partial-state-pruning gate unchanged. A separate [group argument](N131_NO_BINARY_SUM_HASH_RESULT.md)
shows that no nontrivial homomorphism from the odd-order challenge subgroup
to a binary vector space can supply a cheap XOR-like fingerprint for the
large direct join. The next solver must use target-coupled algebra or another
nonliteral mechanism; `candidate_id` and `run_id` remain null.

**Current method goal (2026-10-02):** integrate exact first-pair
realizability into target-dependent leaf selection. The new
[pair-membership gate](PAIR_MEMBERSHIP_NEXT_GOAL.md) spells out the N41
ordinary-row acceptance test, independent group replay, measured partial-
state pruning requirement, and the N131 600-second/4-GiB preflight. An exact
N41 first-pair image preflight passes the known row with 5,904 admissible
pair states and 2,952 output coordinates. Independent checked Sage matched
the complete pair-output set, while two public-only SAT diagnostics were
[censored at 120 seconds](N41_PAIR_MEMBERSHIP_RESULT.md) without a model.
A [column-aware follow-up](N41_PAIR_COLUMN_PROPAGATION_RESULT.md) proved
every N41 output coordinate has a unique folded-column pair, enforced all
six distinct columns, and passed independent Sage group/map replay; its
public solver also timed out at 120 seconds. Exact three-leaf N41 lookahead
rejects eight frozen ordinary prefixes and accepts the known row, but the
direct N131 analogue has up to 9.08 quadrillion pair-plus-last states in
the 12-bit seed-sum family. Monolithic BDD and direct three-leaf lookup are
parked. The next solver must use pair-input restrictions and the target to
prune **before** fixing three leaves, with an explicit N131 work/memory
bound. This is proposal-stage work, so `candidate_id` and `run_id` remain
null.

**Latest N131 algebraic cut gate (2026-10-02):** 12,000 exact sums sampled
from the first two frozen W6/S24 pair domains span all 8,647 Boolean
degree-at-most-two features of their output `u=1/(x+1)` coordinate. Native
M4RI and independent bit-vector ranks agree; 32 selected sums also passed
independent integer-field group replay. Because the sample is contained in
the complete two-pair image, no nonzero output-only quadratic can vanish on
that image. The [result](N131_W6_CROSS_PAIR_QUADRATIC_RESULT.md) closes the
local-output-equation propagation route at this cut, while leaving
input-aware and higher-degree elimination open. Separately, the frozen
exact pair-selector/root systems need 95 N41 or 157 N131 primary bits,
beyond the current direct Boolean F5/M4RI backend's 12-variable interface;
see the [width receipt](joint_f5_capacity_screen.json). The next method
must retain pair-input membership and the target together, demonstrate
target-dependent pruning plus an unpinned ordinary N41 row within
120 seconds/4 GiB, and preflight the N131 600-second/4-GiB query before
running it. These are method diagnostics only: no ordinary N131 relation,
factor logs, DLP scalar, or matched rho timing has been obtained.

**Latest exact four-leaf cut (2026-10-02):** replacing repeated point lifts
with the characteristic-two S3 root equation enumerated all 2,999,808
combinations of the first two frozen W6/S24 pair domains in 169.641 seconds
at 858 MB sampled peak RSS. Their two signed branches yielded 5,999,616
distinct even-`u` quotient coordinates, with no exceptional or collision
case. The [complete result](N131_W6_PAIRPAIR_S3_CUT_RESULT.md) has a sorted
102 MB output, checked-Sage runtime and source hashes, matched pilot
digests, and independent integer-field/group spot checks. This is a
reusable exact target-independent four-leaf image, not a target-driven
relation: a solver still has to select the other ten pair inputs jointly
with the public point. The N131 ordinary-row and complete IC/rho gates
remain open.
The same cut was queried against all 15,872 backward coordinates from
pair 11 on the frozen fresh ordinary N131 workload `cc09e7eb202a` in
0.365 seconds, with hashes matching the prior checked-Sage backward-domain
replay and **zero** exact coordinate hits. The
[target-dependent receipt](n131_affine_w6_pairpair_cut_query/receipt.json)
excludes only this designated three-pair six-leaf restriction; it neither
estimates full-policy yield nor finds the required ordinary 24-point row.

**Direct-join boundary for that cut (2026-10-02):** exact W6 domain counts
put a literal last-four-leaf index behind `2.4965×10^35` labeled
other-ten-pair probes. The best balanced 6/6 explicit join still has
`1.73079×10^21` entries on each side; bare 17-byte keys exceed 4 GiB by
a factor of `6.8507×10^12`. Even a fixed target-independent 4-GiB table
with two signed points per key has a uniform-nonidentity-target hit
probability below `2.55×10^-9` when exhaustively paired with its other
six-block side. The [source-bound frontier and corrected claim scope](N131_W6_PAIRPAIR_DIRECT_JOIN_FRONTIER.md)
apply only to those literal tables, not adaptive algebraic search or the
fixed public point. The four-leaf cut is a useful local inverse, but the
next full-target method must eliminate choices jointly with the public
point before a large group-sum table.

**Latest N131 ordinary-target result (2026-10-02):** the exact V14 eight-leaf
relation circuit has a checked-Sage base audit (`B=527,668`, `K=2,014`) and
passing planted formula/decoder controls. Its one-worker search on the frozen
ordinary N131 point was censored at 1,800 seconds without a model. This is not
UNSAT or zero yield; `candidate_id` remains null. See
[`N131_V14_EIGHTLEAF_RESULT.md`](N131_V14_EIGHTLEAF_RESULT.md).

The [earlier W7 target-coupled method gate](N131_NEXT_TARGET_COUPLED_GATE_20260930.md)
sets its frozen N41 and N131 acceptance workloads and explicit-join
work/memory frontier. The current V20 route has its separate gate below.

**Latest rotated-leaf method gate (2026-10-02):** exact N41 link counts and
an independent exhaustive audit of 945 labeled trees found a `4+2` S3 tree
with 408,246 product-term coordinate occurrences, 42.7307% below the prior
`3+3` slot assignment. The [full result](N41_ROTATED_TREE_AND_PREIMAGE_F4_RESULT.md)
passed known-row and serialized-input checks and reduced the N41 functional
input to 409,721 terms, but its unpinned F4 run hit the 120-second wall cap
without a basis. A detailed trace selected the same 125,390 × 1,568,482
degree-four matrix dimensions as `3+3`. Fixing the known row's target
preimage reduced the `3+3` input to 616,152 terms yet also timed out in a
solver-only diagnostic. Further tree-shape or preimage-flag tuning on this
full-coordinate F4 system is parked; the next method must reduce
intermediate-coordinate freedom or degree-four matrix growth and produce
an independently replayed unpinned N41 row before N131 promotion.
`candidate_id` remains null.

**Latest tree-shape gate (2026-10-02):** an
[exact six-leaf S3 tree DP](N131_V20_OPTIMAL_S3_TREE_RESULT.md) finds a
`3+3`/`2+4` root split with 12,089,977 counted N131 nonlinear coordinate
occurrences, 54.8486% below the original balanced tree and 19.8590% below
the left chain. On the frozen N41 ordinary point, the `3+3` formula passed
the known-row and serialized-input audits, used 714,328 functional terms,
and peaked at 1,065,582,592 bytes (0.992 GiB) under the 120-second/4-GiB
unpinned F4 gate. It still hit the wall cap without a basis. A verbose trace selected a smaller
125,390 × 1,568,482 degree-four matrix but did not complete it. The next
acceptance gate is a changed solver that returns an independently replayed
unpinned N41 row before any N131 promotion; no IC/rho speedup is established.
`candidate_id` remains null.

**Earlier S3 topology screen (2026-10-02):** replacing the balanced six-leaf
V20 `S3_z` tree with a left-associated chain for the same intended group sum
removes its unrestricted `FFF` center link. Exact native and independent
polynomial-basis counts agree: 15,085,880 versus 26,776,539 nonlinear
coordinate term occurrences, a 43.6601% reduction on the frozen N131 point.
The [formula-support result](N131_V20_LEFT_CHAIN_S3_SUPPORT_RESULT.md) is
not an N131 F4 runtime, natural relation, or DLP result. On the frozen N41
ordinary point, the [left-chain F4 gate](N41_LEFT_CHAIN_S3_F4_RESULT.md)
passed a known-row and serialized-formula replay and reduced functional
input terms by 23.2534%. Its unpinned run peaked at 1,420,247,040 bytes
(1.323 GiB) but hit the 120-second wall cap without a basis; the balanced run crossed 4 GiB after
70 seconds. [Bounded F4 traces](N41_LEFT_CHAIN_F4_PAIR_BATCH_TRACE_RESULT.md)
expose a 142,030 × 1,902,754 degree-four matrix with unlimited pair
selection; 64- and 256-pair caps complete smaller rounds but grow their pair
queues and still return no basis in 120 seconds. The next gate is a solver
that controls degree-four pair growth and returns an independently checked
unpinned N41 row before N131 promotion.
`candidate_id` remains null.

**Earlier algebraic-solver width gate (2026-10-02):** the unfurled six-leaf
V20 cubic `S3_z` chain has 638 Boolean variables and 6,882,079,843
squarefree features through degree four. One dense bit row is 860,259,981
bytes; five such rows exceed the 4-GiB gate. The
[exact width receipt](N131_S3_CHAIN_DEGREE4_WIDTH_RESULT.md) is a
representation preflight, not a lower bound on sparse or block F4. It makes
active-monomial and peak-memory measurements mandatory for any new
degree-four solver proposal; a heuristic low regularity degree alone is not
enough to justify an N131 run.

**Latest joint-core audit (2026-10-02):** the proposed four-leaf `S3_z`
formula with a free first-pair output admits every nonexceptional four-leaf
choice by setting that output to the exact target residual. Trace zero does
not prune these residuals: it holds for every nonidentity point in the odd
subgroup of this Koblitz curve. Independent checked Sage confirmed the two
group links and trace condition for 256/256 frozen ordinary N41 controls,
including a known-row positive control. The
[structural result](N41_N131_FREE_PAIR_CORE_STRUCTURE_RESULT.md) parks the
black-box pair-inverse postfilter; the next solver must put pair realizability
into target-dependent leaf selection and show actual pruning on N41 before
an N131 preflight. `candidate_id` remains `null`.

**Latest V20 pair-join screen (2026-10-02):** even granting every designated
first and middle pair, an optimistic 4-GiB target-independent last-pair
sample has an exact uniform-target coverage upper bound of only 0.205232%
with 8 bytes per stored state, or 0.102616% with 16 bytes. Exhausting the
first-plus-middle loop itself would require `2.6016×10^27` probes. The
[bound and assumptions](N131_V20_MEMORY_LIMITED_JOIN_RESULT.md) rule out
sampling the existing explicit index as the next method under this envelope;
they do not bound adaptive algebraic selection or decide whether the fixed
public point has a relation. Keep `candidate_id: null`. The next solver must
select pair outputs jointly with the public target, first clearing an
unpinned ordinary N41 gate and an explicit N131 work/memory preflight.

**Latest N41 solver-isolation gate (2026-10-02):** the implicit V6 six-leaf
SAT formula timed out even with every leaf fixed and only its intermediate
S3 coordinates free; a fully pinned model solved in 0.115 seconds. A new
[functional S3_z root circuit](N41_V6_FUNCTIONAL_S3_Z_RESULT.md) replaces
those four 41-bit coordinates with four root-branch bits and passed full
Boolean replay plus independent checked-Sage group replay of a pinned SAT
model. Its all-leaves-fixed/branches-free slice still timed out after 45
seconds; its unpinned public and correct-first-pair-plus-all-branches-pinned
four-leaf searches each reached a 135-second external cap without a model.
All are populated, censored method diagnostics. This isolates a stronger
requirement for the next N131 proposal: native target-driven leaf selection
and direct group joins, with a complete work/memory bound, rather than a
local pair oracle attached to the current SAT arithmetic tree. No ordinary
N131 relation or IC/rho time follows from the N41 controls.

**Latest V20 method gate (2026-10-02):** the restricted pair inverse's local
speed gain does not improve blind residual probing: its 12-bit seed-sum
domain has proportionally less pair support. An [exact union-bound screen](v20_seed_pair_z_quadratic/restricted_pair_blind_bound.json)
puts one million target-independent fixed-orientation residual calls below
`3.9085×10^-25` success under the declared uniform-target law; at the
observed local query median, a cost-free 600-second calibration gives
`3.7119×10^-25`, close to the complete inverse's earlier `3.6187×10^-25`.
Separately, [two populated N41 SAT diagnostics](N41_V6_SUM_CONDITIONING_RESULT.md)
fixed the known first-pair sum and then the entire correct first pair,
rotation, and output. Both reached their 135-second external wall guard
without a model, although the known row remains in each formula. These are
censored method diagnostics, not UNSAT or ordinary N131 yield. Do not spend
the next challenge-width budget on blind residual sampling or this SAT
four-leaf core; the active gate remains a materially different target-driven
join or elimination that first returns an unpinned N41 row and then an
independently replayed fresh N131 row.

A new [restricted pair-output index frontier](v20_seed_pair_z_quadratic/PAIR_OUTPUT_INDEX_FRONTIER.md)
shows that the 12-bit pair family has at most 132,998,850 signless outputs
for one normalized Frobenius orientation, a 2.105-GiB packed-key array before
sort scratch and runtime overhead. This is a target-independent lookup
preflight only; it could make pair-oracle misses cheaper inside a future
target-driven core, but it does not generate residuals or clear the active
ordinary-row gate.

**Latest local inverse gate (2026-10-02):** a new exact V20 pair inverse
restricts the first pair's eta-seed sum to a fixed 12-bit subspace while
retaining all 19 seed coordinates for each leaf. It scans 4,095 rather than
524,287 nonzero sums per pair-output query. A checked-Sage positive pair
control and the existing ordinary public point were paired against the
complete inverse in twelve alternating repetitions each; every restricted
hit list matched the complete inverse filtered to the same subspace.
Independent checked Sage replayed the positive exact curve sum and 64
ordinary-query negative linear-system samples. The [result](N131_V20_RESTRICTED_PAIR_INVERSE_RESULT.md)
records 0.917/0.632 ms restricted medians versus 109.148/100.002 ms complete
medians, with raw paired samples and interquartile ranges. This is a faster
local *restricted* pair check, not a six-point relation search or DLP
speedup. The joint target-coupled output and sum-selection problem remains
the decisive gate.

**Latest V20 sum-subspace gate (2026-10-02):** exact XOR convolution shows
that constraining the first pair's 19-bit eta-seed sum to a fixed
12-dimensional subspace retains 66,499,425 accepted seed pairs and a
group-wide labelled six-sum mean of 2.90172–2.90209. The analogous
known-populated N41 public SAT trial still reached its 135-second external
wall cap without a model. More decisively, 10,080 exact N131 pair outputs
within that restricted family span the full 8,516-dimensional quadratic
feature space of the trace-zero hyperplane; checked Sage production and
independent integer-field group/rank replay agree. Thus output-only
quadratic filters add no constraint for the complete restricted family.
The [result](N131_V20_SEED_SUM_SUBSPACE_RESULT.md) also bounds naive
residual probing with the local inverse under the uniform-target law.
This is method-selection evidence only; the first ordinary N131 row and
the complete one-target IC/rho comparison remain open.

**Latest circuit test (2026-10-02):** factoring a shared Frobenius rotation
from two V6/V20 leaves reduced the N131 six-leaf formula by 10.03% in
bytes and 8.78% in AND gates. A planted N131 control passed full Boolean
replay and independent checked-Sage group/base replay. The same exact
restriction contains the already verified ordinary N41 row, but its
public-only SAT search returned `INDETERMINATE` at the 120-second cap.
Replacing the N41 trace-inverse gates with the exact nine-mask seed domain
cut the formula to 636,249 bytes, but its public run also returned no model
by the 135-second external wall cap. A V20 seed-domain ROBDD screen needed
43,896–44,003 nodes per seed across three variable orders, so this finite
gate has no compact N131 transfer demonstrated.
The [factored-pair result](N41_N131_FACTORED_PAIR_SAT_RESULT.md) keeps the
ordinary N131 formula as an unsolved preflight; no factored N131 solver run
or relation is claimed. The earlier full N131 V20 solver ended censored at
its 1,800-second wall cap with no model. A new method must exploit the
fixed-seed pair inverse inside a joint target constraint, rather than rely
on this circuit-size reduction alone.

**Latest gate result (2026-10-02):** a restricted V6 six-point join returned
an unpinned relation for a fresh ordinary N41 target. Checked Sage
independently replayed all 738 usable base points and the six-point sum
across six distinct folded columns. The native target-dependent relation
search took 2.166977458 seconds after an 0.084874583-second reusable pair
index setup; this is a decomposition-stage timing, not an IC DLP online
time. The [result and transfer screen](N41_V6_SPECIAL_PAIR_RESULT.md) show
why its explicit index cannot run at N131: 583,191,676,014,432 pair states
would take 8.29 PiB for an illustrative 16-byte payload per state, before
index overhead. A
separate input-aware N131 V20 local pair inverse exhausts all 524,287 seed
sums in one fixed orientation in 82.957584 ms for an ordinary public
point, using about 9 MB peak RSS; it has not been coupled to the remaining
four leaves. The active method gate is a table-free, target-coupled six-leaf
solver with an explicit 600-second/4-GiB N131 bound, demonstrated first on
an unpinned ordinary N41 point and then on an independently replayed fresh
ordinary N131 point. Keep `candidate_id: null`; no N131 relation, factor
logs, scalar, or paired rho timing exists for this route.

**Current N131 relation-search gate (2026-10-02):** V20 now has an exact
six-leaf target equation using five `S3_z` links, the exact 20-dimensional
trace-gated base, complete Frobenius selectors, and exact sign replay. Its
planted formula passed full CNF/XOR replay; a separate decoder replayed the
planted point sum from six distinct folded columns. The ordinary query used
one frozen N131 public target and one CryptoMiniSat worker. It reached the
1,800-second cap at 586,907,648 bytes sampled peak RSS without a status line or
model. Preserve this as censored, not UNSAT or zero yield. The base is
`B=34,152,486`, `K=130,353`; the group-wide six-column support mean is about
3,238, not a measured fixed-target hit rate. The [V20 result](N131_V20_SIXLEAF_RESULT.md)
records the circuit and run. The next useful step is a solver/search method
that exploits the checked fixed-sum pair inverse rather than feeding this
full-width circuit to SAT. `candidate_id` remains `null`; logs, matrix solve,
target scalar, and a same-point online rho comparison remain open.

**Latest method-selection result (2026-10-01):** the frozen N53 four-point
relative-orientation candidate completed a [verified one-target IC/rho pair](../koblitz-n53-relative-batch-20261001/N53_ONE_TARGET_RESULT.md):
0.586083 ms IC online after reusable preparation versus 2,215.175250 ms
rho online on the same point, a one-run ratio of 3,779.627. The failed first
wrapper run is retained. A [frozen serial-parent comparison](../koblitz-n53-relative-batch-20261001/serial_peer_comparison.json)
on the same point, identical base, rank witnesses, and logs independently
replayed both target relations: the eight-offset method's 0.586083 ms
online time beats the parent's 4.490332 ms by 7.662× in this one run.
The [exact transfer screen](N131_RELATIVE_BATCH_TRANSFER_SCREEN.md)
finds that this four-point index cannot serve directly on the challenge
curve: V20 has a uniform-target four-point support upper bound of
`8.32891855443e-11`, while V29 would require `5.898e17` pair-orientation
state visits in the current construction. This N53 result is method
selection evidence, not a challenge solve. The N41 six-leaf transformed-S3
[public-search gate](N41_VD_Z_S3_SIXLEAF_RESULT.md) failed to return a row
within its frozen limits, despite a passing planted control. A later
restricted pair join returned an unpinned ordinary N41 row, while its direct
N131 transfer fails the memory bound above.

**Earlier N131 V29 gate (2026-10-01):** the N131 V29 order-four quotient has
an exact four-factor-plus-target relation equation. Its direct three-link
`G3` circuit keeps two pair coordinates existential and imposes a strict order
on the four canonical seed masks, removing permutation duplicates. The
planted control passes exact CNF/XOR replay, and the circuit is 3.01 times
smaller in bytes than the eliminated 63-term invariant circuit. A single
ordinary target was run alone for 600 seconds; CryptoMiniSat returned
`INDETERMINATE` without a model at 516 MB sampled peak RSS. This is a censored
relation-search result, not UNSAT or zero yield. Keep `candidate_id: null`.
The next gate is a materially different one-target relation solver that can
return and exactly lift an ordinary N131 row. Only after that should work
proceed to factor logs, the 67-million-column matrix, target descent, and the
paired one-target IC/rho online measurement. See
[`N131_ORDER4_S5_RESULT.md`](N131_ORDER4_S5_RESULT.md).

**Earlier W7 research direction (historical):** the compact affine W7/S24 seed-selector S3
solver has now been tested on the frozen N41 public target. Its exact base
extends the indexed W4 control to `B=2,392`, `K=598`; checked Sage replay
confirms all 551,232 pair additions, and two of twelve pair blocks retain
selective quadratic-u equations. The public-only exact-domain formula and
the compact selector each timed out at 120 seconds without a model; the same
selector then ended without a model after 1,800 seconds on one worker and
1,044.328 seconds with eight workers. The latter emitted
`s INDETERMINATE` at 892 MB peak RSS. Preserve these as censored searches, not
UNSAT. The compact selector is parked. The next proposal must materially
change target-conditioned cross-pair elimination and carry a complete N131
work/memory bound before an ordinary challenge-point relation attempt. Any
returned row must be independently replayed. A relation is a stage result;
factor logs, a verified target scalar, and a matched one-target rho clock are
still required for the overall goal. See
[`N41_AFFINE_W7_SEED_SELECTOR_PARALLEL_RESULT.md`](N41_AFFINE_W7_SEED_SELECTOR_PARALLEL_RESULT.md).

A [target-independent N131 W7 rotation redesign](N131_AFFINE_W7_SELECTIVE_ROTATIONS_RESULT.md)
now has a checked base of **B=2,572**, **K=643** and all twelve pair
blocks with 2,132–4,556 independent quadratic-u annihilators; the old
schedule had four full-rank blocks. Complete pair additions, ranks, and
1,536 held-out curve controls passed independent Sage checks. Its uniform
raw-tuple support heuristic is 46 times smaller than the old W7 policy but
still `5.84×10^9` per target. These are local, target-independent results:
the dense equations have no measured cross-pair propagation, unpinned
relation yield, or online speed. Keep both the old selector and the new
policy behind the materially different joint-solver gate.

The [selected-W7 two-pair target control](N131_W7_SELECTIVE_TWO_PAIR_TARGET_RESULT.md)
now recovers an unpinned **planted four-point** N131 relation and passes
independent Sage replay. This is genuine target-conditioned cross-pair
elimination over two local blocks, but the calibrated direct Sage-point
hash takes a 203.165 ms median versus 1,684.389 ms for evaluating local
quadratic equations before lookup on the same target. The equations help
only if a future solver can propagate them while residual coordinates
remain symbolic. A direct two-pair Cartesian materialization already has
323,136,000 pair-point tuples before cross-block sum deduplication, so this
four-point primitive is not a complete 24-point work bound or an ordinary
relation.

The [selected-W7 cross-pair rank screen](N131_W7_CROSSPAIR_U_RANK_RESULT.md)
then added exact points from pair blocks 0 and 1. Their individual u-output
domains have 4,556 and 3,416 quadratic annihilators, but 8,649 deterministic
four-point sums span all 8,647 quadratic-u features. Independent native
M4RI and checked-Sage group replay passed. Thus no output-only quadratic-u
equation survives this particular pair-of-pairs join. A useful joint solver
must retain pair-input information or use a different target-coupled
constraint; the screen says nothing about ordinary N131 relation yield.

The [cofactor-projected three-pair join](N131_W7_PROJECTED_THREE_PAIR_JOIN_RESULT.md)
is the first source-locked N131 method control to recover a six-point row on
the frozen planted public target without reading its witness. Complete
projected domains for the first three selected-W7 pair blocks have 7,920,
10,200, and 10,200 exact subgroup points. A one-worker native streaming join
found the row after 52,227,266 probes and 62.113 seconds, and independent
checked Sage replay verified six distinct base columns in another 0.217
seconds. The 83.072-second domain build is reusable setup. A corrected
input-aware S3/SAT formulation timed out at 120 seconds on the same
public-only planted control; its first version had an XCNF producer parse
error, preserved separately. The join is a real three-pair primitive,
not an ordinary 12-pair relation or a DLP. Its 80,784,000-probe bound does
not extend to the remaining nine pair blocks; the ordinary challenge-width
gate, relation yield/rank, factor logs, target scalar, and paired rho clock
remain open.

The [projected-length frontier](N131_W7_PROJECTED_LENGTH_FRONTIER_RESULT.md)
then computed all twelve exact projected pair-domain sizes from the existing
checked-Sage raw-output files. An independent Sage replay checked the
`x([4]P)` identity on five inputs in every block, and the first three complete
projected sets matched the earlier Sage enumeration. For a uniform ordinary
subgroup point, even the best nine fixed blocks cover at most **0.7085%**
of targets in one query; the planted three-block control's support is at most
`1.211×10^-27`. The best ten-block subset is a new 20-summand proposal with
exact `B=2,188`, `K=547` and **72.259 average labelled projected tuples per
subgroup point**. That average is not measured ordinary coverage or solver
cost. The next structural test should focus on a target-coupled ten-pair
method rather than further optimizing the short planted join. It still needs
the fresh ordinary toy gate, a complete N131 work/memory bound, and an
ordinary N131 row before any candidate or speedup claim.

The default workload remains **one unseen target**. These N41 selector runs
are method-gate diagnostics, not IC online DLP measurements: they do not
recover a scalar or compare against rho. Target-dependent binding and model
verification must be charged if any such representation is later promoted
to a timed online candidate. No batch result may replace that single-target
gate.

The older N53 multi-target panel and other batch artifacts are secondary
historical evidence. Do not resume or headline a pending panel until the
primary one-target IC/rho result is complete and a separate shared-setup
question has been defined; the latest single-target instruction supersedes
the earlier panel roadmap.
The earlier W19 route's
[indexed-join screen](n131_w19_near_pair_geometry/residual_join_screen.json)
rules out directly materializing one three-point residual side in the local
envelope: its 144,521,288,719,352,000 raw tuples would take about 4.62
exabytes at an illustrative 32 bytes each.

The [latest W4 u-equation joint trial](N41_AFFINE_W4_U_S3_JOINT_RESULT.md)
passes exact pinned controls, but free-root, zero-root, and complete
torsion-normalized public-only SAT variants all reached 120 seconds
without a model. The zero-root pattern omits the known row; it is not a
complete symmetry reduction. Full pair-witness checks establish that
setting each pair-u low bit to zero **is** complete for exact rows when
all raw target preimages remain available, yet that normalization alone
did not make the monolithic SAT tree practical. The next implementation
must eliminate or constrain intermediate S3 coordinates using the
public target before a general SAT/F4 search, then clear the unchanged
unpinned W4 row gate above.

The [exact W4 torsion-quotient mux trial](N41_AFFINE_W4_U_QUOTIENT_MUX_RESULT.md)
also passed a pinned group-lift control, but its full public search and
a witness-independent seven-pair random slice each timed out at 120
seconds. Local exact membership and reduced selector entropy alone
therefore have not cleared the gate. The slice's 36.34 expected rows
are a uniform-sum prediction, not measured yield; a later
[indexed existence audit](N41_AFFINE_W4_RESIDUAL_SLICE_EXISTENCE_RESULT.md)
proved that this particular slice contains at least one exact row.
Keep the next experiment focused on public-target-driven
cross-pair elimination before another full S3 SAT call.

A [bounded-prefix residualization trial](N41_AFFINE_W4_U_RESIDUAL_S3_RESULT.md)
removed seven fixed toy pairs from the Boolean tree and generated 512
target-specific residuals from 128 reusable raw prefix sums. Its
known-row control and independent checked-Sage group replay passed;
the public random slice still reached 120 seconds without a model,
despite a 62.1% smaller formula. A later
[frozen-slice diagnostic](N41_AFFINE_W4_RESIDUAL_SLICE_EXISTENCE_RESULT.md)
found and independently replayed a row in that exact slice. The same
public XCNF accepts it when fully pinned, while pinning only its known
populated residual still timed out at 30 seconds. The unpinned timeout
is therefore a search failure on a populated slice, not an empty-slice
artifact. Future work should establish a
challenge-width relation-density and work/memory bound before
promoting another fixed-prefix strategy; the unpinned W4 gate and full
ECC2K-130 single-target objective remain open.

The [symmetric-S3 residual follow-up](N41_AFFINE_W4_RESIDUAL_SYMMETRIC_S3_RESULT.md)
cut the public five-pair circuit to 25,878 variables, 80.2% below the
forward-root version. A pinned exact row passed in both CryptoMiniSat and
Z3, but the public CryptoMiniSat trial reached 120 seconds without a
model; both solvers also timed out after 30 seconds when only the known
populated residual was fixed. These are censored searches on the same
N41 target, not negative relation evidence. Another encoding or
solver-family switch alone is no longer the immediate gate: the next
trial must prune pair-group choices using the public target and prove a
complete N131 work/memory bound before claiming challenge transfer.

An [exact backward-S3 domain trial](N41_AFFINE_W4_BACKWARD_DOMAIN_RESULT.md)
now applies such a target-dependent local rule to one known-populated
residual: the last pair's 60 coordinates yield exactly 120 allowed
four-pair upper coordinates, independently checked by Sage curve-group
addition. The resulting 19,273-variable pinned control passes, but
four free pair choices still timed out at 30 seconds. Because the
residual was selected using the existence witness, this is only a
diagnostic. A public solver must handle all residuals and return an
exact row under the unchanged N41 gate; N131 relation density and
search bounds remain open.

The [challenge-width W6 backward-domain screen](N131_AFFINE_W6_BACKWARD_DOMAIN_RESULT.md)
transferred that one local equation to the exact sparse-basis N131
curve on an ordinary public point. All four raw target preimages and
1,984 last-pair even-u coordinates were covered; each preimage gave
3,968 distinct allowed upper coordinates, with 15,872 in their union.
Every algebraic root matched independent Sage curve addition.
The corrected target-dependent domain generation and replay took 2.588
seconds after 82.275 seconds of reusable pair-point lifting and
generator validation. This is only a local
constraint: the remaining eleven-pair search, ordinary relation yield,
and a complete N131 memory bound remain open. The initial attempt also
exposed a legacy public point encoded in a different field polynomial
under the same readable curve label; the accepted run binds the exact
modulus explicitly before combining inputs.

A [new fresh sparse-basis target](N131_FRESH_SPARSE_TARGET_RESULT.md)
now fixes workload `cc09e7eb202a` on that exact curve. Its public
point, canonical workload hash, subgroup checks, and private scalar
replay passed an independent integer-field audit. The backward-domain
stage on this fresh point again passed every algebraic/group check
over all four raw preimages, with 15,872 distinct allowed upper
coordinates. Direct half-trace pair lifting cut its separate reusable
setup observation to 1.626 seconds; the Q-dependent local interval
was 1.722 seconds. This prepares a sound ordinary N131 input and
cheaper local setup, but it does not solve the other eleven pair
groups or produce a relation.

An [exact black-box sampling frontier](N131_BACKWARD_BLACK_BOX_FRONTIER_RESULT.md)
shows why the small allowed upper domain is not by itself a viable
search. Under an explicitly conditional uniform-coordinate model,
independently sampling the other eleven W6 pair sums needs about
`2^116.046` probes on average to hit the measured 15,872-element
set. The corresponding W7 upper bounds still require at least
`2^114.023` probes without fixed pairs or `2^112.023` after two
fixed pair outputs. These are model-based method rejections, not
complexity lower bounds on algebraic solvers. The next advance must
couple several remaining pair groups to the public target before
sampling or SAT.

The [exact N131 affine W7/S24 geometry screen](N131_AFFINE_W7_S24_GEOMETRY_RESULT.md)
adds a denser challenge-width base proposal after checked-Sage point
replay: `B=3,024` before folding and `K=756`, versus W6's `B=1,440`
and `K=360`. Its uniform-sum 24-slot support prediction rises from
about 4,402 to 268 billion rows per point; under further
no-collision assumptions, two fixed even-u pairs would leave about
4,546 predicted rows. Natural relation yield and target-dependent solver
cost remain unmeasured. Complete W7 raw pair-x domains
are now enumerated and all twelve have full rank in the 8,647 quadratic
x features, so this base loses the x-coordinate quadratic pruning used
by W6. A
materialized six-plus-six pair join also exceeds `1.36e25` assignments per
side. Do not spend another W7 attempt on this route; any different
target-dependent pruning method needs a complete work/memory bound, and the
small-field unpinned method gate remains open.

A separate [complete u-domain replay](N131_AFFINE_W7_PAIR_OUTPUT_RESULT.md)
independently checked every W7 raw pair addition in Sage and verified
94,872 even-u representatives across the twelve blocks. The
[ten-pair build-only preflight](N131_AFFINE_W7_TEN_PAIR_PREFLIGHT_RESULT.md)
constructed exact domains and nine functional links in 48.4 seconds at
1.915 GiB RSS. This shows the representation can be built locally, but
does not alter the W7 x-coordinate pruning rejection: prefix selection,
target-dependent solver time and memory, and natural relation yield
remain unbounded. W7 stays parked until a different target-dependent
pruning method clears the stated gates.

The [complete W7 u-coordinate rank replay](N131_AFFINE_W7_U_RANK_RESULT.md)
corrects any broader inference from the x screen: **eight of twelve**
pair blocks do retain degree-two annihilators in the S3 `u=1/(x+1)`
coordinate, with 11,540 local nullspace dimensions in total. Native
M4RI and independent checked Sage agree on every rank. These are local
necessary equations only; their target-coupled propagation has not been
measured. W7 still needs a concrete joint
pruning method, an unpinned N41 solve, and a complete N131 search bound
before an ordinary challenge query.

The [W7 u-equation control screen](N131_AFFINE_W7_U_EQUATIONS_RESULT.md)
then extracted 512 local necessary equations across those eight blocks.
All 7,243,264 positive evaluations vanished; checked Sage confirmed
1,024 held-out rational-curve controls, with zero survivors after the
first 16 equations in every non-full block. The selected equations are
dense, averaging about 3,455 monomials, and four pair blocks have no
quadratic u equations at all. These local controls do not establish
target-coupled propagation, ordinary relation yield, or a viable W7
online solve. The unpinned N41 method gate remains the next live step.

The [W19 fingerprint-join frontier](N131_W19_FINGERPRINT_FRONTIER_RESULT.md)
also rejects direct extension of the successful N41 compact join: a single
generic raw-pair fingerprint list is 2,051.85 GiB at eight bytes per entry,
and its diagonal-by-two-pair target loop has 7.96×10^28 exhaustive probes.
These are method-specific raw counts; deduplication and algebraic joint
pruning are not bounded by them. The next method must couple the other three
pair outputs to the public target without that Cartesian-product loop.

The [N41 diagonal residual-S4 result](N41_DIAGONAL_S4_RESIDUAL_RESULT.md)
proves a compact residual equation and passes an independent natural-row
replay, but both the generic and fixed-diagonal one-target SAT searches were
censored by the frozen 120-second envelope. The fixed-diagonal formula is
about 20% smaller, yet it returned no row after 47 of 512 branches. This is
not evidence of unsatisfiability or an IC speedup; the next method still has
to make target-coupled search materially more effective before any N131
ordinary relation attempt.

The subsequent [60-minute fixed-branch sweep](N41_DIAGONAL_S4_RESIDUAL_RESULT.md)
attempted all 512 diagonal choices for the same single N41 target. All
per-branch five-second SAT attempts were indeterminate and no relation was
returned after 3,367.727 online seconds. This is a completed one-target
search experiment, not an UNSAT result or a complete IC measurement.

The [W19 adjacent-pair x-coordinate quadratic screen](N131_W19_PAIR_X_QUADRATIC_RESULT.md)
now rules out another narrow shortcut. All 8,647 degree-at-most-two Boolean
features of the 131-bit pair-output x have full rank on 16,248 admissible,
distinct-column W19 pair sums. An independent integer-field replay checked
every sum and the rank; the Semaev coordinate `z=1/(x+1)` also has full
quadratic feature rank on the same outputs. A joint solver must keep the
low-rank input sum/product
variables or use higher-degree and cross-pair constraints; no ordinary N131
relation follows from this structural screen.

The [W19 adjacent-pair inverse control](N131_W19_ADJACENT_INVERSE_RESULT.md)
now supplies an exact, table-free recovery step for a proposed generic pair
output on the selected challenge-field base. It recovered all 32 planted
full-width raw pairs; an independent checked-Sage replay verified the points,
subgroup projections, and 64 negative first-gate controls. This closes one
local primitive, while the target-coupled generation of the three pair
outputs remains open.

The [sum/overlap follow-up](N131_W19_SUM_OVERLAP_FIXED_SUM_RESULT.md) gives an
invertible 29-sum-bit/nine-overlap-bit coordinate system for W19 adjacent
pairs. At fixed seed sum `U`, the product is affine linear in the overlap,
and the pair-output inverse reduces to a ten-column GF(2) system. It recovered
all 32 planted W19 pairs, rejected 64 independent conditioned controls, and
passed independent checked-Sage point and rank replay. It does not propose
`U` or a pair output from the public target. Enumerating its `2^29` sums and
`2^9` overlap choices restores the original `2^38` seed-pair domain, so the
unpinned N41 and ordinary N131 relation gates remain open.

The [opt-in ARM64 W19 first gate](N131_W19_NATIVE_FIRST_GATE_RESULT.md)
preserves the exact pair-inverse decisions and improves prepared miss-only
batch throughput by a measured 49.08× over the portable Python path on this
host, with process launch and input parsing charged to the native batch.
This makes screening proposed pair outputs cheaper; it does not address how
to propose the three outputs jointly from a public target. No hardware
backend is enabled automatically.

The [latest W19 near-pair geometry and residual gate](N131_W19_NEAR_PAIR_GEOMETRY_AND_RESIDUAL_RESULT.md)
establishes an exact challenge-field eight-slot base with **B=4,196,344**
usable points and **K=262,151** signed-Frobenius columns. Independent
checked-Sage enumerations agree on the complete rational mask count and
eight-window union digest; a full reciprocal scan found zero collisions.
The one-diagonal relation-support value of about 32.21 is a uniform-sum
prediction, not observed yield. Fixing only the known first diagonal pair
still left the N41 six-point residual SAT control indeterminate after
34.5 seconds. The target-coupled six-point solver remains the next gate;
there is still no ordinary N131 relation or target DLP.

The [new Frobenius-diagonal rational reduction](N131_DIAGONAL_RATIONAL_IDENTITY_RESULT.md)
replaces one equal-mask near-pair S3 leaf by two exact rational formulas.
Independent checked-Sage replay passed every N41 diagonal mask and the
frozen N131 sample. A table-free N131 inverse recovered all 128 frozen
pair-output masks and rejected 64 uniform-coordinate controls, with exact
group replay. The resulting N41 rational-leaf formula passed its known-row
control but its public-only one-target search also hit the 120-second cap.
The missing gate is still a target-coupled solver for the other three pairs
and a fresh ordinary N131 relation; no complete IC/rho speedup is known.

The [latest one-diagonal-pair solver gate](N41_NEAR_PAIR_DIAGONAL_LOOKUP_RESULT.md)
uses an exact first-pair lookup: 32 allowed N41 masks have 64 total
nonexceptional outputs, all independently checked in Sage. The lookup
removes 711 total Boolean variables and 57 functional equations from the
previous diagonal SAT formula, and both known-row preflights pass. Neither
public-only one-target trial returned a model under its frozen 120-second
envelope. These are censored N41 searches. A new method must couple the
remaining three pair outputs to the target without materializing an N131
pair or four-sum index; the first ordinary N131 relation remains open.

The [latest near-pair admissibility and target control](N41_N131_NEAR_PAIR_ADMISSIBILITY_RESULT.md)
adds a frozen N131 sample of 512 distinct-column pair outputs with full
first-gate rank and independent Sage replay. A structured equal-mask sample
exposed 91 deficient N131 outputs, but those pairs share one folded column;
the exhaustive N41 analogue found no admissible deficient output. An
offset-one N41 indexed join recovered and independently replayed an
eight-point row on the frozen public target. Its 12,668,544-row reusable
index is a positive control only. The missing gate is still a scalable
target-coupled N131 joint search and an ordinary N131 relation.

The [offset-one N131 pair-policy result](N131_NEAR_PAIR_POLICY_RESULT.md)
establishes an exact `B=2,099,016`, `K=131,068` eight-window base with a
rank-79 local pair-output gate on the frozen controls. An inverse oracle recovered all 32
planted pair queries and passed independent Sage replay of 68 sign witnesses;
64 random-coordinate controls failed the gate. This retains 99.91% of the
widely spaced base while preserving a useful local algebraic filter. The
remaining algorithm gate is to generate four pair outputs **jointly from an
ordinary public target**. None of these local controls is an N131 relation,
factor-log system, target DLP, or IC/rho speedup.
An exhaustive N41 local-pair check inverted all 2,004 nonexceptional output
coordinates and independent Sage replay confirmed its rank distribution;
30 outputs required first-gate kernel enumeration. That edge case is now an
explicit requirement for a complete joint solver.

The [fixed-mask target predicate and landscape check](N41_W6_S8_FIXED_MASK_TARGET_RESULT.md)
now couples exact pair-leaf roots to all four raw preimages of the public
N41 point. It recovered and group-verified all 12 known tuples, while 64
frozen independent controls gave no resultant zero. A one-mask neighborhood
around those rows showed no improvement over independent controls in the
minimum-resultant Hamming score, so simple score-guided hill climbing has no
measured support. The exact frozen support implies about 1.46 billion
uniform canonical mask probes per relation. A target-coupled structural
search remains necessary; this is not an unpinned N41 or N131 solve.

The [exact N41 W6/eight-slot row census](N41_W6_S8_ALL_ROWS_RESULT.md)
found 12 distinct-column relations for one frozen public target by scanning
the complete indexed toy support. Independent checked Sage replay verified
all 12 and found rank 11 among same-target row differences. Five rows lie in
the fixed raw-target branch of the timed-out double-resultant SAT trial, so
the branch was populated; all five also pass the exact serialized SAT
formula. The unresolved issue is finding a row without the unscalable
four-point index. These are N41 stage diagnostics, not an N131
relation, complete IC solve, or speedup.

The [exact forward pair-leaf solver](N41_N131_PAIR_LEAF_ROOTS_RESULT.md)
now computes each leaf's two possible S3 coordinates directly from its two
seed masks, without a pair table or SAT leaf variables. It passed all 7,824
N41 point-pair entries, independent raw group checks on 110 pair controls,
and four planted N131 challenge-field pairs. A witness-guided CMS control
with all eight masks pinned still returned `INDETERMINATE` at 15 seconds;
the direct solver removes its free leaf-coordinate search but does not supply a
target-coupled mask search. The unpinned N41 and ordinary N131 gates remain
open.

The latest [exact W18 local pair-oracle transfer](N131_W18_LINEAR_PAIR_ORACLE_RESULT.md)
recovers the two seed masks from a proposed raw pair-sum coordinate by two
binary-linear systems, without a pair table. Sixteen frozen planted N131
pairs passed independent field and group replay; 64 uniform field-coordinate
controls were inconsistent with the first system. This is a usable local
primitive, not a natural relation: the missing step is a target-coupled
**joint** search across four pairs. Do not promote single-pair membership
throughput or planted replays to an N131 DLP claim.

The [full-width follow-up](N131_W18_FULL_WIDTH_PAIR_ORACLE_RESULT.md) closes
the first sample's low-mask coverage gap: 64 rational masks span all 18 seed
bits, 128 branch/sign pair queries passed, and independent Sage replay
reproduced every result. A cardinality bound limits an independent uniform
projected pair-oracle hit to at most `5.067e-29`; the next method must solve
the four pair outputs jointly, not scan random output points. No natural
challenge-field relation is established.

The [quadratic auxiliary-product joint trial](N41_W6_S8_QUADRATIC_JOINT_RESULT.md)
then encoded all four W6 pairs and their outer S3 links as exact degree-two
equations. Planted and ordinary known-row controls passed independent Sage
and serialized-equation replay. Its public-only one-target trial covered all
four target preimages under one 120-second/4-GiB envelope, but every branch
hit its time cap without a basis or model; peak sampled group RSS was 784 MB.
Thus the new representation is correct but has not cleared the unpinned N41
search gate. No N131 ordinary query is promoted from it.

The [exact W6 rationality audit](n41_w6_s8_quadratic_joint/rationality_anf.json)
also identifies a limitation of that quadratic trial: its S3 links did not
enforce seed rationality or distinct folded columns. The valid-seed
predicate has degree five, with no nonzero quadratic equation in the six
mask bits vanishing on all 32 valid masks. Any next quadratic joint method
must represent this filter with auxiliary structure or verify and exclude
invalid models; the timed-out relaxed system is not a complete factor-base
solver.

The [validity-aware native-XOR SAT follow-up](N41_W6_S8_QUADRATIC_XOR_SAT_RESULT.md)
included the exact allowed-mask and distinct-column constraints and passed
the known-row translation control. Its public-only CryptoMiniSat search
returned `s INDETERMINATE` without a model after 113.704 seconds online;
the original frozen receipt mislabeled exit code 15 as an error. The
[classification-chain audit](n41_w6_s8_quadratic_xor_sat/ordinary_subgroup_root_R2/classification_chain_audit.json)
binds that receipt and the executed source to the corrected
`CMS_INDETERMINATE` receipt. The N41 gate still
requires an unpinned verified row from a materially stronger search method.

The [slot-mask hybrid follow-up](N41_W6_S8_QUADRATIC_HYBRID_RESULT.md)
retained the complete target equations and exact validity filters, then
branched one seed mask over its 32 allowed values serially. It examined two
branches in 120.045 seconds online (including a 44.6 ms supervisor overshoot)
and returned no model; branch 1 was indeterminate and branch 2 was stopped at
the cap. This is a censored one-target failure, not UNSAT. The R1 quadratic
system already factors W6 pair products through their exact rank-11 spans and
couples all four pair outputs to the outer target links; re-encoding that
same system is not the next method. The next attempt must add global
elimination or a structurally different joint search with an explicit N131
work/memory bound.

The [exact cubic product-elimination trial](N41_W6_S8_CUBIC_ELIMINATION_RESULT.md)
proved symbolic equivalence to the quadratic S3 system and passed its known
natural row. Eliminating six pair-product auxiliaries reduced variables from
420 to 294 but expanded ANF monomial occurrences from 95,919 to 1,774,675.
Its public-only N41 Msolve run hit the 120-second parent cap at 3.919 GB
sampled peak process-tree RSS without a basis, model, or relation. This is a
censored search, not UNSAT. The next method must retain sparse pair/tree
structure while doing global target-coupled elimination, with a credible
N131 work/memory bound before an ordinary challenge-field query.

The [complete-branch double-resultant follow-up](N41_W6_S8_DOUBLE_RESULTANT_RESULT.md)
eliminated both middle S3 coordinates and passed 53 independent N41/N131
algebra checks, including known witnesses and linear exceptional branches.
A direct-gate N131 target block built at 397 MB peak self RSS, but this is
only a size control without the leaf equations or solver. The complete
validity-aware N41 formula passed its known row, then its unpinned public
search hit 120.005 seconds online at 487 MB sampled peak process-tree RSS
with no model. It is another censored search, not a natural relation.
The next method needs adaptive/blockwise target-coupled search, not another
whole-system SAT timeout; the ordinary N131 relation gate stays closed.

The [quadratic-system Jacobian diagnostic](N41_W6_S8_QUADRATIC_JACOBIAN_RESULT.md)
now measures rank 413 at the known natural N41 row: all 372 auxiliary columns
have full rank, leaving 41 independent first-order conditions on 48 mask
bits. An independent finite-difference audit agrees. This is local structure
for choosing an elimination method, not a solved public search or an N131
work bound.

The [one-step finite-difference Newton basin control](N41_W6_S8_FINITE_DIFFERENCE_NEWTON_RESULT.md)
repaired all 16 one-bit perturbations of a known N41 row, as expected, but
found no exact relation in 63 valid perturbations at distances 2–16. Its
predeclared four-to-sixteen-bit gate averaged only a 0.383-bit improvement
over a matched same-weight random correction, with a descriptive 95%
interval from −0.851 to +1.681 bits; only 10 of 47 corrected states retained
distinct columns. This local Newton branch is parked without a witness-free
public search or N131 transfer. It does not change the unpinned joint-solver
milestone.

The [exact planted N131 W18/eight-slot transfer](N131_W18_S8_JACOBIAN_RESULT.md)
now confirms all seven S3 links and the full quadratic-tree Jacobian on the
challenge curve. Its rank is 1,319 of 1,332 variables, with all 1,188
auxiliary columns full rank only after the four pair outputs are coupled to
the outer links. An independent finite-difference and group replay passed.
The first frozen fixture failed its distinct-column rule and remains
preserved; the second was fixed before execution. Neither fixture is an
ordinary relation or a target DLP.

The latest [exact N131 W18 pair-output rank screen](N131_W18_PAIR_OUTPUT_RANK_RESULT.md)
found that 12,716 valid same-window pair sums span **all 8,516** Boolean
x-coordinate features of degree at most two after the subgroup's universal
trace-zero condition. Independent checked Sage rebuilt every pair sum and
a separate bitset elimination reproduced full rank. Thus the rank-35
seed-product span does not yield a standalone linear or quadratic x-output
filter; the next solver must retain pair inputs and eliminate their exact
addition constraints jointly with the target. This is target-independent
geometry, not a natural N131 relation. The first N131 relation gate remains
open.

The latest [complete N41 W6/eight-summand pipeline](N41_W6_S8_COMPLETE_PIPELINE_RESULT.md)
recovered an unseen toy target from 26 independently verified factor logs,
then passed independent Sage replay. Its **957.162 ms** one-target IC online
time lost to **332.376 ms** same-point, one-worker rho (`rho/IC=0.3473`).
This settles the toy full-pipeline correctness gate but does not support a
speedup claim. The indexed first-four table is unscalable at N131. The next
algorithm milestone is a table-free, unpinned ordinary N41 row on the frozen
W6/eight-slot point with an explicit N131 resource bound; then exact planted
N131 replay and a fresh natural N131 row. The goal remains active.

The latest [exact W18/eight-window geometry screen](N131_LOWPOWER_W18_M8_GEOMETRY_RESULT.md)
establishes a smaller challenge-field base proposal: **B=2,100,912** actual
fixed-window subgroup points and **K=131,068** signed-Frobenius columns.
Independent checked-Sage scans cover the rational seeds, direct folds, and
all reciprocal shifts. Its ordered eight-summand support count is a heuristic,
not a natural-relation measurement. The added summands make joint search the
decisive unknown. No `IC1` candidate, natural N131 relation, DLP, or speedup
is implied; the unpinned structural N41 solver gate remains first.

The [four same-rotation-pair follow-up](N41_W6_S8_FOUR_PAIRS_RESULT.md)
changed that proposal to rotations `[0,0,32,32,64,64,96,96]`: the exact
N131 fixed union is **B=1,050,456** with the same **K=131,068**, and each
pair product has rank 35. On a matching N41 W6/eight-slot base, an exact
indexed 4+4 join found a natural row on the frozen ordinary target and
independent Sage replay passed. Its 3,167,136-row reusable index and
0.090947-second target-online lookup are toy reference costs. Two index-free
SAT encodings passed full planted models and Sage replay but both timed out
on seed-pinned solver controls at 30 seconds; per protocol, neither advanced
to a blind ordinary run. Thus the structural unpinned method gate and the
fresh ordinary N131 decomposition gate remain open.

An earlier W9/S6 follow-up, the
[incremental selector-partition screen](N41_W9_S6_INCREMENTAL_PARTITION_RESULT.md),
did not clear its one-mask positive control: the assumed solve returned
`UNKNOWN` at its frozen 30-second/500,000-conflict branch cap. The run is
censored, not UNSAT, and the blind selector schedule remains blocked. Do not
increase this formula's budget by repeating the earlier 120-second pinned
control; pursue a materially different search primitive before another N41
SAT attempt. The overall ECC2K-130 single-target IC-versus-rho goal remains
active.

## Latest gate — 2026-09-30

The [disjoint S5 Boolean-F4 screen](N41_DISJOINT_S5_BOOLEAN_F4_RESULT.md)
passed its pinned N41 control and independent checked-Sage replay on one
public target (`B=1,300`, `K=61`). The public-only ordinary formula reached
its 120-second online cap before producing a Groebner basis or natural row.
No ECC2K-130 single-target IC solve, factor-log system, scalar recovery, or
paired one-target rho comparison exists yet. The goal remains active; the
next method must recover an unpinned ordinary N41 row before a new N131
ordinary-target attempt. A follow-up root-enumeration F4 run again stopped at
the 120-second wall cap without a basis; see
[its result](N41_DISJOINT_S5_BOOLEAN_F4_ROOT_ENUM_V2_RESULT.md). The next
formulation applies the cofactor-four map to each summand before the S5 chain.
Its exact branch-free projection map passes exhaustive N41 base replay and a
planted N131/W26 formula control, but has not yet been run through an
unpinned solver. The direct ANF expansion then reached 74 MB and degree 7,
so it was stopped before solver launch; see
[the F4 preflight result](N41_PROJECTED_S5_F4_PREFLIGHT_RESULT.md). The next
factored XCNF passed a fully fixed natural-row control at 1.56 MB, then its
single-target unpinned N41 search returned `INDETERMINATE` after 118.908 s
online without a model or UNSAT proof; see the
[circuit preflight](N41_PROJECTED_S5_CIRCUIT_PREFLIGHT_RESULT.md) and
[single-target result](N41_PROJECTED_S5_SINGLE_TARGET_RESULT.md). The next
attempt must change the search primitive and recover an unpinned N41 row
before an exact N131 planted replay or any natural N131 query; see the
[projection formula gate](N131_COFACTOR_FOUR_PROJECTION_FORMULA.md) and
[next joint-solver gate](NEXT_JOINT_SOLVER_GATE.md).

Current state: two exact W27 base policies are established: the five fixed
summand windows have **B=670,967,620** points and **K=33,547,983** folded
columns, while full 131-shift closure has **B=8,789,571,546** with the same
K. The planted challenge-size five-point circuits are independently
verified, but blind solver trials on one fresh ordinary point found no
relation. A later disjoint-Frobenius method found and independently replayed a
natural five-point row on the frozen N41 toy target. Its exact W26 N131
analogue passes a full planted formula-witness replay, while both
CryptoMiniSat and WDSat public-only searches return no model at 600 seconds.
These results are recorded in
[N41_DISJOINT_FROBENIUS_RESULT.md](N41_DISJOINT_FROBENIUS_RESULT.md) and
[N131_W26_DISJOINT_S5_RESULT.md](N131_W26_DISJOINT_S5_RESULT.md). The active
method gate and next acceptance criteria are at
[Current gate](#current-gate-2026-09-29) and
[Next joint-solver gate](NEXT_JOINT_SOLVER_GATE.md).

The [N131 W27 five-list birthday screen](N131_W27_BIRTHDAY_SCREEN.md)
rejects a tempting generic birthday shortcut: the prime-order curve group
does not admit the small 2-group homomorphic filters it requires. The exact
base counts are target-independent; there is still no natural N131 relation,
relation rank, factor log, recovered DLP, or paired one-target rho timing.

The later [N41 overlapping-W9 comparison](N41_W9_OVERLAP_RESULT.md) found
2,522 usable points and 123 folded columns under that changed base policy.
Its exact native join recovered a new natural row and passed independent
Sage replay. Across eight paired repeats on the same toy point, W9's median
online join time was 1.673 s versus W8's 3.397 s, with a paired median
W8/W9 ratio of 2.02. The W9 public-only functional-pair SAT search still
timed out at 120 s. Thus the immediate engineering target is free-seed
joint search without a quadratic pair table, followed by a fresh ordinary
N131 relation; these toy timings do not establish a challenge-size DLP.

The [six-summand W9 follow-up](N41_W9_S6_FUNCTIONAL_RESULT.md) found and
independently replayed another natural row with an exact toy 2+4 join, but
its unspecialized functional SAT search reached the 120-second online cap
without a model. A known-row circuit passed only after seed-bit
specialization. The active method gate is now structural seed-mask pruning,
starting with joint pair-output elimination on the low-power basis; more
summands alone did not make index-free natural search viable.

The [low-power W8 six-summand screen](N41_LOWPOWER_W8_S6_RESULT.md) then
tested that structural direction on the same frozen ordinary N41 target.
Three same-rotation pairs have exact product-span rank 15, and a native
positive-control join found an independently verified six-point row.
Factoring those products reduced the formula by 3,231 variables and 5,931
clauses against the same-input generic circuit. A complete evaluated model
and checked-Sage replay prove the known row satisfies the factored formula,
yet both free-seed SAT searches reached 120 seconds without a model, even
after exact within-pair symmetry breaking. A degree-four size preflight
rules out an unfiltered dense matrix with four explicit 41-bit intermediates
under the 4 GiB toy envelope. The next search-method gate is blockwise or
sparse algebraic elimination on the low-power S3 chain, first unpinned on N41;
no N131 ordinary query is justified by these SAT results.

The subsequent [direct Boolean F4 screen](N41_LOWPOWER_W8_S6_F4_RESULT.md)
passed a seed-pinned N41 correctness control with independent Sage replay,
but its public-only 222-variable instance hit the frozen 4-GiB memory guard
after 70.061 seconds without a Groebner basis or model. The first method
gate remains an unpinned ordinary N41 relation through genuinely bounded
intermediate elimination, followed by an exact N131 planted control before
any new ordinary challenge-field point.

The [torsion-quotient follow-up](N41_LOWPOWER_W8_S6_BRANCH0_F4_RESULT.md)
proved by exhaustive checked-Sage enumeration that fixing the half-trace
branch to zero preserves all 750 projected base points and 117 folded
columns. It removed six Boolean search variables from the same public N41
F4 system, but the ordinary one-target run still hit the 4-GiB guard after
67.533 seconds without a basis or model. Both F4 timings are censored
failures, not an online speed comparison. The next method must eliminate
the 41-bit chain intermediates or bound target-coupled matrix growth before
another ordinary N41 solver run.

The [target-coupled resultant screen](N41_LOWPOWER_W8_S6_RESULTANT_RESULT.md)
then removed the entire 41-bit third leaf output from the Boolean circuit,
reducing it from 112,823 to 88,286 variables. A full known-row model and
independent Sage resultant replay passed, including the nonzero branch
coefficient. The single unpinned public-only run nevertheless reached its
120-second cap without a model. The next search mechanism must gain
substantive target-coupled pruning, not only reduce circuit size; no natural
N131 relation has been promoted.

The [inverse-free implicit-root screen](N41_LOWPOWER_W8_S6_IMPLICIT_RESULTANT_RESULT.md)
then replaced two forward pair-root circuits by three low-degree S3
constraints while retaining the final target-coupled resultant. Its complete
known-row Boolean and independent Sage controls passed. The public-only
formula fell to 12,423 variables and 24,190 clauses, but its one unpinned
attempt still reached the 120.008-second online cap without a model. This
keeps the exact N131 natural-relation gate open and points to search
propagation, rather than circuit size, as the immediate solver bottleneck.

The [full implicit S3 follow-up](N41_LOWPOWER_W8_S6_FULL_IMPLICIT_RESULT.md)
kept all four chain outputs as variables and imposed five direct degree-three
S3 links, including the target. Its complete known-row and independent Sage
controls passed, and it removed the resultant's `D=0` exclusion. The one
public-only search had 10,866 variables but exited `INDETERMINATE` under a
declared 2,000,000-conflict limit after 117.902 seconds with no model. No ordinary
N131 relation has been obtained; stronger target-coupled search remains
the first gate.

A parallel N41 candidate screen tested the exact normal-basis HW4 factor-base
policy on one frozen ordinary target. The corrected base has **B=48,626**
actual usable points and **K=593** folded columns. Both the three- and
four-summand chained-S3 formulas returned `INDETERMINATE` at 120 seconds with
no model or UNSAT proof. Removing point-order symmetry did not change the
four-summand outcome, and the seven-summand formula also reached the same cap.
Checked-Sage replay validates the target, exact base count, and timing
receipts. An earlier incomplete-orbit run is explicitly invalidated. These
results do not establish natural relation yield and do not replace the
structural joint-search gate. See
[S3](N41_ONB_HW4_S3_RESULT.md), [S4](N41_ONB_HW4_S4_RESULT.md), and
[S7](N41_ONB_HW4_S7_RESULT.md) results. A different search mechanism is needed
before this HW4 base can advance to a challenge-size ordinary query.

The exact N131 HW4 base has `B=5,838,146`. Its ordered six-summand count
`B^6/r≈58.18` falls to about **0.0808 distinct unordered tuples per fixed
target** after the solver's `6!` point-order symmetry reduction. The seven-
summand estimate is about **67,395 unordered tuples**. These are uniform
counting heuristics, not observed yields; they make S7 the better target
coverage hypothesis, while the N41 SAT screens show the current chained-S3
search still cannot find even high-coverage toy rows under the declared cap.

The historical blind N131 W27 trials used a larger full base with
17,582,648,390 points and 67,109,345 columns. The later exact overlapping
policy has a five-fixed-window base with **B=670,967,620** and
**K=33,547,983**, or full Frobenius closure with **B=8,789,571,546** and the
same K. These are different manifests and must not be conflated. Neither
policy has a natural N131 relation. The active gate remains an unpinned
structural search on the frozen ordinary N41 target. Any future N131 trial
must freeze one exact base policy and independently replay membership,
curve-point sums, the target fixture, and source encoding in checked Sage.
Earlier W18 and W20 trials are
retained in the historical experiment record below.

The next gate is ordinary-query yield and useful row rank on a frozen query
stream, including every failed attempt and a confidence interval. If that
passes, prepare and independently verify enough factor logs for the final
relation matrix, solve a separate fresh public target, and pair its complete
online interval with a verified one-target rho run. Record the five exclusive
online phases, separate cold costs, peak memory, operation boundary, exact
curve/candidate/workload/run IDs, and all status rows. A complete IC win
requires a recovered scalar and `[k]G=Q` on both sides.

## Historical experiment record

The gates below document the route to the current W27 comparison. Their
"next" instructions describe the decision at that stage; the current
decision is in [Current gate](#current-gate-2026-09-29).

### First bounded experiment: algebraic subgroup membership

The exact subgroup character already proved and independently replayed in
`../koblitz-trace-homomorphism-20260928/` is

`Tr(x)=0` and `Tr(y)+Tr(x*H(x))=0`.

In the exact binary field encoding used by the W18 table, its second term
can be compiled into a Boolean quadratic form. Test a new W18 six-summand
circuit in which each unrotated seed `u` has a field inverse witness,
`x=1+u^-1`, an actual curve `y` witness, the curve equation, and both exact
subgroup-character bits. Keep the six-summand S3 chain and normal-basis
Frobenius shifter. Frobenius preserves subgroup membership, so the character
is checked before rotation. The old exact BDD is the controlled reference.

The new Boolean domain may admit a few alternate selectors for the same
signed-Frobenius point orbit. Enumerate and verify its distinct subgroup
point set against the frozen W18 geometry before claiming an equal-base
comparison. Compare formula size on one hidden planted positive control,
then on a fresh ordinary public target. A model passes only after checking
every emitted clause/XOR row, lifting all six points to the exact curve,
verifying subgroup membership, checking their sum against the public point,
and independent Sage replay. Models outside the retained point set or with
unverified lifting fail the gate.

Freeze source/input and solver-binary hashes, one target seed, and the
following limits before solving. Use one CPU solver worker, at most 200,000
conflicts or 120 seconds internal solver time per variant, one fresh target,
and a 4 GiB child-memory ceiling with a 150-second external watchdog. The
old BDD and new algebraic circuit get the same target and limits. Save each
timeout, OOM, invalid model, and indeterminate result. If the planted
positive control fails, stop before the ordinary-target solver trial. If
the new circuit reduces the measured CNF clause count by at least 25% while
remaining correct, a single predeclared 600-second / 10-million-conflict
extension on the new circuit is allowed; this is still a stage experiment.
The ordinary-target success gate requires a verified natural decomposition,
independent Sage replay, and target-dependent wall accounting.

This protocol is a bounded engineering batch. An indeterminate or timed-out
run does not reject the mathematical decomposition method. A complete
ECC2K-130 DLP and matched rho comparison remain the active goal until their
own evidence exists.

The first bounded batch is complete; see [RESULT.md](RESULT.md). Both fresh
target attempts were indeterminate, and the 25% clause-reduction gate failed,
so no declared long extension was run. The goal remains active at the first
natural-decomposition gate.

A second frozen batch expanded the exact base to W20 with six summands on a
new public point. Its full planted control and independent Sage replay passed,
but the natural W20 attempt reached its external watchdog without a model;
the paired W18 attempt was indeterminate. The stage evidence is in
[RESULT.md](RESULT.md). Increasing this base's predicted relation count alone
did not clear the decomposition gate.

An unpinned solve attempt on W20's guaranteed-satisfiable planted formula
also timed out without a model. The current SAT search method now fails even
with coverage proved, so the next gate is a method change, not another
dimension-only search.

The smaller-field method-selection pilot found an ordinary N41 relation with
an exact pair index on the same public point where the anchored direct-
addition SAT follow-up returned no model. The full evidence and scaling
barrier are in [N41_RESULT.md](N41_RESULT.md). This does not clear the N131
natural-decomposition gate; it motivates a compact pair/root join or another
solver that avoids the explicit quadratic index.

A matched compact-oracle run then recovered the exact same N41 natural
relation with 6.32× less peak process memory, at 3.60× the online time.
Independent Sage replay passed. The existing N131 support lower bound rules
out treating this fixed-query oracle swap alone as the needed breakthrough.
The next gate is a **joint higher-arity** or other structural decomposition
that clears an unpinned ordinary toy target while keeping query and
factor-log-column growth below the recorded N131 fixed-pair bounds. Only
then freeze another fresh degree-131 point for the first natural
decomposition attempt. No current stage result satisfies the final DLP goal.

An [exact adjacent-rotation pair oracle](N131_ADJACENT_RESULT.md) now removes
first-mask enumeration for the low-power polynomial-W base on the challenge
curve. It recovered an unpinned planted pair at W23 and W30, and independent
Sage replay confirmed one complete 131-orientation ordinary pair miss for
each. W30's first gate produced only 8 or 16 candidates per orientation on
that point, but its full factor-base geometry is not enumerated, and the
two-point miss is not a five-point relation. This changes the next method
gate: use the compact adjacent-pair equations inside a **joint pair-pair
solver** on frozen ordinary toy targets, then test a fresh ordinary N131
five-point target only after the joint toy gate clears. Do not promote the
pair-stage timings to an IC candidate or speedup claim.

The first W30 geometry screen projects roughly 525 million folded columns
and 8.92 GB of bare logs under explicitly unverified non-collision
assumptions; its actual base count remains unknown. The joint-solver branch
therefore needs a dimension/cost gate as well as a blind natural-relation
gate. A faster pair oracle alone does not pay for factor logs or the final
relation matrix.

The [middle-dimension screen](N131_ADJACENT_RESULT.md#middle-dimension-frontier)
now brackets the next joint-solver input. W27 and W28 both recovered
unpinned planted adjacent pairs and had independently checked ordinary
pair misses on the same 131-orientation workload. The optimistic two-pair
support model projects about 125 versus 8.4 fixed-single probes per hit,
while projected bare logs rise from 1.13 GB to 2.26 GB. These are not
measured five-point yields or complete candidate costs. Test a genuine
joint two-pair solver on frozen ordinary toy targets at **both** dimensions'
corresponding scales, then materialize and verify the selected N131 base
before another fresh-target challenge attempt.

A fresh [ordinary N41 five-point reference](N41_ADJACENT_PAIRPAIR_RESULT.md)
now passes the **toy relation** gate: a native exact join found one raw
single plus two adjacent-Frobenius pairs on a new public point, and
independent checked Sage replay verified all selectors, five distinct
signed-Frobenius columns, the base geometry, scalar fixture, and both raw
and projected sums. The earlier Python exact join reached its 120-second
online cap with no hit; the native join found the row after 50.84 million
probes in 51.94 seconds, with the same exact pair-index counts. This is a
reference witness, not yet the required **compact joint solver**. Recover
the same point without materializing the pair index, then proceed to the
frozen W27/W28-scale N131 natural five-point gate. Factor logs, rank,
target scalar recovery, and matched rho remain open.

The [next joint-solver gate](NEXT_JOINT_SOLVER_GATE.md) freezes a concrete
method test on that public toy point: recover any unpinned five-point row
without the explicit pair table under a 600-second, 4 GiB, one-worker cap,
then independently replay it. Only a passing compact method earns a fresh
W27/W28-scale degree-131 ordinary-target trial; stage predictions and the
native toy row alone cannot satisfy the challenge goal.

The [legacy full-W27 geometry result](N131_W27_EXACT_GEOMETRY_RESULT.md)
settled one prerequisite for the earlier blind trials: that policy has
17,582,648,390 actual usable subgroup points and 67,109,345
signed-Frobenius columns after complete rational, direct-overlap, and
reciprocal scans and independent Sage replays. Its bare 17-byte logs occupy
1,140,858,865 bytes. The later [overlapping-window policy](N131_W27_OVERLAPPING_GEOMETRY_RESULT.md)
has different exact B and K counts, recorded above. Neither geometry result
is natural relation yield; the joint-solver and fresh ordinary degree-131
decomposition gates remain open.

The N41 [compact fingerprint-filter follow-up](N41_ADJACENT_PAIRPAIR_RESULT.md#compact-fingerprint-filter-follow-up)
now clears the toy compact-recovery gate: it found the same ordinary five-
point row in 175.271 s online using 7.5 MB peak RSS, and checked Sage
independently replayed it. The fingerprints cannot scale to W27, whose exact
two-pair support already contains 2.36×10^18 choices. The next method must
combine the adjacent-pair equations algebraically rather than storing a full
pair-choice list. No N131 natural five-point solve, relation logs, complete
DLP, or paired one-target rho result exists yet.

The [algebraic adjacent-pair SAT follow-up](N41_ADJACENT_ALGEBRAIC_SAT_RESULT.md)
reduced the frozen toy circuit from 41,911 to 11,564 AND gates by replacing
S6 with two pair equations and two S3 joins. A fully pinned correctness
control passed, but both blind bounded runs were indeterminate with no
five-point row. The toy algebraic-search gate therefore remains open.
An inverse-and-trace rationality gate agrees with all 64 exact N41 masks
and with 24 independently checked W27 masks on the challenge field; it
provides a scalable factor-base membership encoding, not a natural N131
relation. The next solver iteration must recover an unpinned ordinary toy
row before promoting the algebraic method to the fresh N131 target gate.

## Current gate, 2026-09-29

The exact W27 challenge-field circuit has now passed planted five-point
controls with three encodings, including independent checked-Sage point,
formula, and subgroup replay. A new scalar-known ordinary public point was
generated directly in the exact W27 field. Three public-only trials on that
same point found **no relation** under the same one-worker, 2,000,000-conflict,
600-second online, and 4 GiB peak-RSS acceptance envelope: one-hot S3 and
binary-rotation S3 timed out; the nondegenerate two-link resultant exited
`INDETERMINATE` before the wall cap. The resultant excludes the `D=0`
branch. The [paired comparison](N131_W27_JOINT_SOLVER_COMPARISON.md) and
[mechanical evidence audit](n131_w27_joint_comparison_audit.json) preserve the
failed rows and source/runtime hashes. An [encoding audit](n131_w27_pair_s3_sat/field_encoding_audit.json)
also prevents mixing an older degree-131 polynomial representation with
this W27 field.

The next measurable goal is one **unpinned, independently verified** natural
W27 five-point row on a newly frozen ordinary public point, with every failed
query and the exact target-dependent interval retained. Before spending
another challenge-size solver budget, demonstrate a structural joint-search
method on the frozen N41 ordinary witness and measure its search rather than
only its formula size. A frozen singleton-rotation partition experiment has
since covered all 41 N41 rotations but returned `INDETERMINATE` on every
branch, with no row or UNSAT proof; see
[N41_ROTATION_PARTITION_RESULT.md](N41_ROTATION_PARTITION_RESULT.md). It did
not clear the structural method gate. The adjacent-pair oracle gives a concrete starting
point: at W27, the sum and product spans have ranks 41 and 79 and its first
linear gate has 121 columns. Use those linear systems to prune or eliminate
pair choices jointly, or test a solver with a different algebraic search
mechanism; a smaller SAT formula alone does not clear the gate. Declare
coverage restrictions and resource limits before each run.

After a natural row, freeze independent ordinary queries and measure verified
yield with uncertainty, novel rank, and cost per useful row. Only then prepare
factor logs, solve a separate one-target DLP with replay, and compare its
complete online wall interval with a same-point one-target rho solve.
Candidate IDs remain null until an exact end-to-end pipeline is specified;
there is currently no N131 relation, factor-log set, recovered target scalar,
or IC/rho speedup.

The [rotation-partition follow-up](ROTATION_PARTITION_RESULT.md) ruled out
rotation fixing as a sufficient improvement under its declared budgets.
All 41 N41 singleton-rotation branches were unresolved in 156.906 seconds,
including a branch known independently to contain a five-point solution.
On the challenge field, fixing all three planted rotations while leaving
five seed masks and target-preimage choice free also returned
`INDETERMINATE` after 49.014 seconds of solver work. The fixed formula
is proven satisfiable by the prior fully pinned control and its checked-Sage
replay. The ordinary W27 follow-up was not run because the planted search
gate failed. The active first gate remains an unpinned natural N131 row;
the next method must exploit algebraic pair constraints rather than
only reducing rotation selectors.

The [lazy-rationality follow-up](N131_W27_RELAXED_SEED_RESULT.md) also
failed its planted search gate. Compiling the three rotations and
removing the five inverse/trace gates cut the W27 resultant formula
to 39,228 AND gates and 118,128 CNF clauses; the fully pinned model
and all formula rows passed independent checked-Sage replay. With
the seed masks and target-preimage choice free, CryptoMiniSat still
returned `INDETERMINATE` without a model after 41.146 seconds under
500,000 declared conflicts. No ordinary trial was promoted. This
evidence shifts the active engineering focus from circuit size to
the joint algebraic search itself.

Separately, the [fresh N53 full-pipeline panel](../koblitz-n53-fastindex3-independent-panel-20260929/panel_summary.json)
has now finalized eight independent one-target workloads for each of
fastindex2 and fastindex3, with all 16 IC/rho pairs independently
replayed in checked Sage. Each candidate won 4 of 8 paired online
comparisons. The median rho/IC online ratio was 1.107 for fastindex2
and 1.022 for fastindex3, with wide descriptive bootstrap intervals
that include 1. This validates a smaller-field full pipeline on new
targets but does not establish a general advantage for fastindex3,
the N83 scaling gate, or an N131 result. Retain fastindex2 as a
controlled reference while selecting the next challenge-size method.

Separately, the exact prepared-log candidate
`IC1N53Ckb1fb23320PDP4rootRCguidedLAgaussTDdirectISO0h0dd8fcee749a`
has an eight-target panel with eight distinct targets and eight paired
one-target rho solves. All 8/8 IC/rho pairs replayed, and the median paired
online `rho/IC` ratio was 84.23×. The audited R1 point was outside that
sample. This is secondary coverage evidence because its target-independent
factor-base/index/log setup was shared and reported separately; setup after
the retained factor-base header was 5.94 seconds, and full cold cost is
unknown. It supports generalization of the prepared-online win, not a cold
one-shot speedup. The full rows and limitations are in
[the ordinary-target panel](../koblitz-n53-ordinary-target-panel-20260928/README.md).
The N83 design audit is recorded in
[the N83 83-bit index note](../koblitz-n83-index-design-20260929/README.md).

The separate [W27/S5 blind planted-control attempt](W27_S5_RUNS_STATUS.md)
also failed to clear its gate: the corrected circuit built to 239,242
variables, but CryptoMiniSat produced no model during a 3,734.865-second
externally interrupted target attempt. Because the solver did not honor the
declared one-hour internal cap and wrote no terminal receipt, that run is not
a valid capped control. The runner now owns a hard parent deadline. Continue
with the frozen structural N41 ordinary-target gate before another W27
challenge-size search; the ECC2K-130 scalar and one-target rho comparison
remain open.

A [30-second R4 deadline smoke](W27_S5_RUNS_STATUS.md) verified that the
parent now interrupts the solver and preserves both worker and run receipts:
it charged 29.606 seconds online (29.068 seconds in SAT search) with 488 MB
combined sampled RSS, but returned no model. This verifies stop accounting,
not the planted control or a speedup. The next gate remains the structural
ordinary N41 solver.

The [N41 two-link resultant WDSat pilot](N41_RESULTANT_WDSAT_RESULT.md)
tested a different CNF/XOR search engine on the frozen ordinary target.
Both plain and XOR-Gaussian modes solved the fully pinned planted control,
with all XCNF rows and exact Sage group lifts verified. Both unpinned
ordinary trials timed out after 90 seconds without a model. A locally
resized build kept peak child RSS below 59 MB, so this trial narrows the
bottleneck to joint search rather than static solver capacity. It does not
advance the N131 natural-relation gate. The next experiment must use the
pair sum/product structure to remove or prune free choices and first
recover an unpinned N41 ordinary relation.

The latest [one-target encoding screens](ONE_TARGET_ENCODING_SCREENS_20260929.md)
tested exact product-span factoring, canonical XOR flattening, and a bounded
polynomial Karatsuba product. Product-span factoring reproduced the same N41
formula counts; capped XOR sharing reduced the W27 formula file by only 3.25%
and increased its XOR literals slightly. No SAT solve was run for these
variants. They do not clear the structural N41 gate or establish a speedup.

The [pair-output-first WDSat test](N41_RESULTANT_PAIR_FIRST_RESULT.md)
changed only branch priority on the adjacent-pair formula. Both pinned
controls passed, but both unpinned modes timed out at 90 s.

The [same-rotation pair follow-up](N41_SAME_ROTATION_RESULT.md) found a
different **natural N41 five-point row on the same public point** with an
exact native pair index in 33.235 s; independent checked Sage verified all
five distinct columns and the group sum. Its W27 sum/product spans are
27/53 rather than 41/79 for adjacent pairs, reducing the first-gate
column upper bound from 121 to 81 on the exact N131 field. This is
positive toy support and algebraic-structure evidence, not a scalable
challenge-size solve: the native method still materializes quadratically
many pairs. The index-free same-rotation resultant formula passed a fully
pinned natural-witness control, but blind CryptoMiniSat returned
`INDETERMINATE` after 257.785 s and blind WDSat timed out at 90.002 s
without models. The next gate remains an unpinned index-free ordinary
row, then a planted exact-W27 control and fresh N131 ordinary target.
The ECC2K-130 relation, logs, DLP, and paired rho comparison are open.

The [exact N131 same-rotation pair gate](N131_SAME_ROTATION_PAIR_RESULT.md)
now narrows the W27 first system to 81 columns by removing two impossible
product coordinates. Its separate planted pair passed, and independent Sage
replayed all 131 Frobenius orientations of the frozen public point: every
ordinary first gate had rank 81 and augmented rank 82. The optimized
pair-stage interval was 21.666 ms. This is a direct-pair miss on one point,
not a five-point yield estimate. It reinforces the need for a joint
two-link solver that couples pair outputs without a quadratic pair index;
the unpinned N41 method gate and the N131 DLP acceptance gate are unchanged.

## Staged N53/N83 index-calculus track, 2026-09-30

This is the small-field scaling track for the single-target IC objective above.
It has separate gates and does not replace the W27 natural-relation gate.

### N53 evidence and next run

The independent eight-target N53 panel sampled new points with seed
`20260929083`, disjoint from the earlier prepared-log panel, and paired one
rho solve to each same point. All 16 IC runs and eight rho solves passed
checked-Sage replay. The fastindex2/fastindex3 candidates had median online
`rho/IC` ratios of 1.107/1.022 and four wins in eight pairs each; the
descriptive intervals include 1. The prepared-log candidate separately
verified eight of eight targets at median online `rho/IC = 84.23x`; its 5.94 s
setup after the retained factor-base header and unknown full cold cost keep that
result in the prepared-online category. See
[`independent-panel summary`](../koblitz-n53-fastindex3-independent-panel-20260929/panel_summary.json).

The low-setup candidates still have no general-target or cold-start win. Their
fastindex2/fastindex3 median IC online times are 776/785 ms and their
cold-after-launch medians are 1,189/1,206 ms, against the paired one-worker rho
median of 860 ms. Each won four of eight online pairs; each won three of eight
cold-after-launch comparisons. These cold observations do not use an
empty-system-cache interval. The `RCguided` candidates in that fresh-target
panel differ from the exact `RCsample` pipeline behind the 356.9x five-repeat
result below, so the generalization result for that exact candidate remains
open.

The `RCsample` figure comes from five repetitions on one fixed N53 point: the
IC online median was 4.517 ms, paired rho online median was 1,580.830 ms, and
the median paired ratio was 356.86x. All five IC/rho answers passed the
independent Sage replay. The historical rho reference replay (3.66–4.01 ms
per run) was timed separately; the fresh-target freeze charges scalar replay
inside rho's online interval. The five-row ledger and independent Sage replay
are the [measurement records](../koblitz-cofactor-fiber-20260928/measurement_rows_n53_fb25864.jsonl)
and [replay receipt](../koblitz-cofactor-fiber-20260928/n53_fb25864_independent_sage_replay.json).
This is one-target N53 evidence only.

A separate fresh-target panel is frozen in the corrected pre-run successor
[`koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting`](../koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting/README.md);
its 2026-09-29 parent freeze is retained as history and must not be launched.
Candidate `IC1N53Ckb1fb25864PDP4rootRCstreamLAgaussTDdirectISO0h2317245898c5`
uses worker-completion-order relation insertion and cooperative cancellation
after the target coefficient vector enters the verified row span. The eight
workload points are disjoint from the two earlier N53 target panels. Its
protocol, code, source, binary, rho reference, factor-base geometry, runtime
record, and workload hashes all pass pre-run verification. The panel has not
started: the frozen driver requires 4 GiB free on the system volume. An earlier
preflight found about 3.5 GiB free and the N83 idle/handoff guard passed then.
Those readings were superseded by the 12:28 UTC live checkpoint below: system
space fell under 0.25 GiB and the Q1061 marker made the N83 handoff unresolved.
After both gates clear, run the frozen panel once, replay all accepted and
speculative relation witnesses and scalars with checked Sage, then finalize
the paired one-target table. Count no speedup before that replay.

### Supplementary preparation costs

The serial prepared-log run measured 8.632 s median reusable setup and 8.637 s
cold-after-launch; the 14-worker collector reduced those measurements to
3.366 s and 3.371 s. These figures are retained as supplementary
reproducibility data. Setup is excluded from the primary one-target online
comparison and is not a gate for selecting or rejecting an online candidate.

### N83 scaling gate

The N83 design audit is in
[`koblitz-n83-index-design-20260929`](../koblitz-n83-index-design-20260929/README.md).

**Completed prerequisite — N53 one-target generalization, 2026-10-02:** the
frozen RCsample panel has eight separate workloads, each pairing one unseen
public point with one IC solve and one rho solve. Independent checked-Sage
replay verified all eight scalars, all 244 factor-base columns, relation ranks,
and paired online phase sums. All eight IC online times beat their paired rho
times; the median paired online ratio was 82.2535×, with a paired-target
bootstrap 95% interval of 33.8727×–176.3844×. Median online times were
49.000 ms for IC and 2,168.141 ms for rho. Reusable IC setup (median
21.584 s) is recorded separately and excluded from the single-target online
metric. The [panel summary](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/panel_summary.json)
and [independent replay](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/validation/independent_sage_replay.json)
close the N53 prerequisite only; this F2^53 toy result does not establish an
N83 or ECC2K-130 speedup.

The query key retains all 83 bits in an unsigned 128-bit value and confirms
candidate matches with full-key and group-law checks. At `B=8,000,204`, the
M31 screen measured an 809 s table build, a 6.39 s query over 1,048,576
representatives, and 408.7 s exact rescan with zero hits. Its 59-chunk
95%-coverage estimate is prediction-only and is about 13.5 times the rho
square-root step floor before other costs. A four-times-larger base has a
separate 0.057-rho-floor query prediction for two R28 windows; memory and
unknown-log recovery remain separate gates.

The latest Q1062 full-range attempt ended in a resource abort with unknown
cumulative work and no verified DLP. It requires an explicitly frozen retry;
the Q1062 launcher requires at least 10 GiB free on the system volume. Do not
count that attempt as zero-yield evidence. A reusable snapshot prototype now
passes a synthetic 8,192-key test and exact Bloom-bit/query parity with the
current worker. Its receipt is
[`snapshot_smoke_result.json`](../koblitz-n83-index-design-20260929/bloom_snapshot_prototype/snapshot_smoke_result.json).

The B32M known-log base has 192,776 signed-Frobenius columns and 32,000,816
actual points before folding. Its independent checked-Sage verification
replayed all 192,776 fixture logs and checked all expanded orbit points; see
the [base receipt](../koblitz-n83-index-design-20260929/runs/n83_knownlog_base_b32m_20260929/final_result.json).
The separate build-and-save/map-only worker then passed a bounded M4096
planted control. Both modes found the same hit, and fresh checked-Sage replays
verified the same four points, their logs, their sum, and scalar
`559344661655771031431119`. The 79,872-byte snapshot and manifest are in
[`final_result.json`](../koblitz-n83-index-design-20260929/bloom_snapshot_prototype/runs/n83_b32m_planted_snapshot_20260929_retry4/final_result.json).
This is a planted correctness control on a known-log base, not ordinary
relation yield, an unseen-target solve, or a candidate result; `candidate_id`
remains `null`. The worker recorded 1.283 GB peak RSS. Since this macOS host
rejects `RLIMIT_AS`, the small control used a 10 ms in-process high-water RSS
watchdog with a 3 GiB stop threshold under the declared 4 GiB envelope; the
receipt labels that guard as sampled, not kernel-enforced. Earlier incomplete
control attempts remain preserved in their retry directories.

An earlier N83 check found about 3.5 GiB free on the system volume and about
24 GiB on the SSD spill volume. Those historical readings are superseded by
the live launch checkpoint below. The next N83 gate is to measure a real M31
snapshot after the 10-GiB system-volume guard passes, then run fresh ordinary
query windows. Keep the failed Q1062 range out of that workload and retain
every zero-hit and failed cell. Ordinary relation yield must pass before
unknown-log collection or a full N83 DLP comparison.

### Live launch checkpoint, 2026-09-30 12:28 UTC

The later read-only snapshot records 258,924,544 bytes free on `/` and
2,615,545,856 bytes on `/Volumes/SSD990`. The N53 streaming panel therefore
remains below its 4-GiB start guard; the N83 campaign remains below its 10-GiB
guard. The panel's frozen hashes all match, but it has no start marker or result
rows. A Q1061 run tagged `q1071` still has a start marker in the read-only
external tree and no terminal artifact. `ps` was denied with “Operation not
permitted,” so process liveness is unknown and the N83 idle handoff does not
pass. The snapshot is
[`live_gate_snapshot_20260930T122823Z.json`](../koblitz-n53-fastindex4-streaming-cert-20260929/validation/live_gate_snapshot_20260930T122823Z.json).

The frozen N53 panel pairs one rho solve with each same target; IC may use 14
workers while rho uses one inside the common 14-thread envelope. Retain that
comparison as frozen, but report the worker counts and treat its ratio as an
implementation-and-parallelism result. A claim of advantage at equal worker
count needs a separate, frozen rho comparator on the same points.

### Corrected N53 rho interval, 2026-09-30 12:49 UTC

Source inspection found that the earlier frozen panel excluded rho's
independent scalar replay from `rho_online_ms`. It also established that rho's
jump-table setup consumes `Q`, so it is target-dependent. The corrected v3
freeze charges jump-table setup, walk, and reference-curve scalar replay while
excluding only process launch and fixture target construction. It reuses the
same eight public points and fixture scalars but has a new rho reference ID and
new workload/run IDs. Its immutable protocol receipt is
[`freeze_receipt.json`](../koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting/freeze_receipt.json).
The 12:51 UTC gate snapshot records 249,925,632 bytes free on `/`, far below
the 4-GiB N53 threshold; the external Q1061/Q1071 marker still has no terminal
artifact and unverified process liveness. See
[`live_gate_snapshot_20260930T125150Z.json`](../koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting/validation/live_gate_snapshot_20260930T125150Z.json).
No measurement has started.

### One-target N53 panel gate recheck, 2026-09-30 14:50 UTC

The RCsample generalization panel's read-only preflight verified its freeze,
all eight independent workloads, and `target_count=1` for every pair. The N83
handoff returned no active or competing Q1060/Q1062 markers. Q1062 still has
one failed resource-abort attempt with unknown cumulative work and requires an
explicit retry; it has no verified DLP. System-volume free space was
1,638,309,888 bytes, below the panel's 4-GiB launch guard, so the preflight
reported `measurement_started: false`. Spill-volume free space was
2,514,264,064 bytes. The N83 M31 pilot remains further away from its 14-GiB
proposed launch threshold. No measurement was launched. The captured
[preflight receipt](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/validation/preflight_gate_20260930T1450Z.json)
has SHA-256 `29ea901f023d35df97ede679bd96731104fd859daccd29b4693801cc5244689a`.

### ECC2K-130 acceptance

After N83 ordinary-query and full-DLP gates pass, freeze the exact challenge
curve, subgroup, one public target, IC candidate, rho policy, and resource
envelope. Keep preparation and one-target online intervals separate. A win
requires the IC scalar to pass independent replay on the same public point as
rho; an N53 speedup or a planted N83 control does not satisfy this gate.

### Latest N131 search gate

The N41 [disjoint-Frobenius control](N41_DISJOINT_FROBENIUS_RESULT.md) passes
for one natural toy target with an exact 3+2 join under a changed base
policy. The W26 N131 analogue has direct-sum rank 130 and an exact planted
formula-witness replay: all emitted clauses and XOR rows, five point lifts,
distinct columns, raw sum, and target projection check. Its unpinned
public-only CryptoMiniSat and WDSat runs each returned no model at a
600-second limit. The [WDSat record](N131_W26_WDSAT_RESULT.md) includes its
passing fully fixed smoke and public-only timeout. These controls do not
clear the natural N131 decomposition gate. First demonstrate a different
algebraic formulation or search strategy on an ordinary toy target or
equivalent structural positive control. Then freeze any new N131 ordinary
target trial as a single-target workload. Full factor logs, matrix rank,
unknown scalar recovery, and the paired one-target rho interval remain
unmeasured.

The new [functional-pair N41 study](N41_DISJOINT_FUNCTIONAL_RESULT.md)
found a concrete solver improvement under the same five-disjoint-subspace
policy. Three formulations with free middle or pair-output coordinates
could not solve even a pinned-seed known row within 80–168 s; a forward
Itoh–Tsujii inverse and exact quadratic pair-root circuit reduced each
pair output to one root bit and solved that pinned-seed control in 0.306 s.
Independent Sage checked its XCNF model, both pair roots, five distinct
columns, public scalar, and raw/projected sums. The exact N131 field
inverse primitive passed nine selected controls. The **blind** N41 run
still returned `INDETERMINATE` after 161.302 s, and a public 16-branch
root/target partition found no row in 165.686 s. Free seed search is now
the tested bottleneck; this does not clear the N131 natural-relation gate.

The later [W9 overlapping-base comparison](N41_W9_OVERLAP_RESULT.md) found
and independently replayed a natural row on that same single N41 point. Its
native pair-index join was 2.0209 times faster online than W8 across eight
paired repetitions (95% paired-bootstrap interval 1.9615–2.0723), with the
base policy and memory cost changing. W9's public-only functional SAT run
still hit its 120-second cap. The exact
[N131 W27 overlapping-basis geometry](N131_W27_OVERLAPPING_GEOMETRY_RESULT.md)
now counts 67,096,762 rational seeds in each Frobenius-shifted block, with
combined rank 130; full checked-Sage replay also confirms 33,547,983
canonical rational Frobenius representatives. The reciprocal/torsion
screen found zero reciprocal memberships across the Frobenius closure of W27;
checked Sage validated the edge-coordinate membership test and all sampled
inverses. Together with the exact pairwise-overlap replay, this leaves
335,483,810 distinct rational seed values with neither direct duplicates nor
reciprocal candidates in the tested quotient. The checked exact-base receipt
now establishes B=670,967,620 subgroup-usable points before folding and
K=33,547,983 folded columns for the five fixed windows. Ordinary N131
relations, factor logs, and DLP recovery remain unmeasured. See
[the reciprocal screen result](N131_W27_OVERLAPPING_RECIPROCAL_RESULT.md).
The N41 speedup is a decomposition-stage result, not an IC-versus-rho claim.

The separate [N41 W6/S8 one-target accounting control](N41_W6_S8_ONE_TARGET_PAIR_RESULT.md)
paired one indexed 4+4 query and one signed-Frobenius rho solve on the same
public point. Checked Sage replay passed for both scalars, but IC took 930.800
ms online versus rho at 36.324 ms (`rho/IC = 0.0390`). This is a measurement
contract and toy-method control, not a speedup or an N131 candidate; its
reusable IC setup is reported separately.

### Refreshed N53/N83 launch checkpoint — 2026-09-30 17:35 UTC

The frozen N53 eight-target panel remains unstarted: its `panel_started.json`,
measurement rows, and summary are absent. The current system-volume free
space is 3,239,837,696 bytes, below the runner's 4 GiB guard. N83 Q1071 is now
terminal with zero exact-hit queries and no verified target DLP after
6,875.786 seconds of target-online work. A Q1073 start marker is present with
no terminal receipt; its process liveness is unknown. The refreshed evidence
is in the panel's
[`17:35 UTC live gate snapshot`](../koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting/validation/live_gate_snapshot_20260930T173530Z.json).
Keep the N53 panel frozen and unstarted until both its system-volume guard
and the N83 idle/handoff check pass. The staged order remains the independent
N53 target panel, N53 cold-start work, the N83 scaling gate, then the frozen
ECC2K-130 one-target comparison.

### N53 nonlaunch preflight — 2026-09-30 17:47 UTC

The new nonlaunch preflight was run through the checked Sage launcher. Its
`shutil.disk_usage("/")` reading was 5,674,545,152 bytes, so the panel's
4-GiB disk guard passes. The exact frozen N83 guard still fails because both
Q1073 start markers are listed as competing work. Its status snapshots report
Q1060 idle within the campaign (2 completed rectangles, 934 remaining, no
failed rectangles) and Q1062 with one prior failed unknown-work range; neither
has a verified DLP. The first Q1073 attempt has an interruption receipt with
unknown work, and retry 2 has a start marker but no terminal receipt. The
retry wrapper/controller PID probes return `EPERM`; preserve the run as
unresolved. The frozen panel remains unstarted. The receipt is
[`preflight_gate_20260930T174737.939065Z.json`](../koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting/validation/preflight_gate_20260930T174737.939065Z.json).

The external N83 status code treats every non-selected `n83_*.started.json`
as a competing marker. Q1073 retry 2 binds the first interrupted attempt's
receipt but writes a separate start marker; the native worker removes only
the marker for its own output. Therefore a completed retry may still leave
the first attempt marker blocking the panel. Re-run the nonlaunch preflight
after retry 2 reaches a terminal receipt, then reconcile any retained marker
from its bound interruption receipt as an unknown-work failed attempt. Keep
the marker and its coverage uncredited until that reconciliation is recorded.

### Retry and disk recheck — 2026-09-30 17:52 UTC

The latest nonlaunch preflight reports 4,017,045,504 bytes available on `/`,
277,921,792 bytes below the panel's 4-GiB guard. Q1073 retry 2 still has its
start marker and no terminal or interruption receipt. After a 30-second wait,
both its wrapper and controller PID probes still return `EPERM`. The panel
remains unstarted; see
[`preflight_gate_20260930T175254.583852Z.json`](../koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting/validation/preflight_gate_20260930T175254.583852Z.json).

### Double-resultant circuit and one-target seed-formula gate — 2026-09-30

The complete-branch double-S3 algebra audit passed 53 nested-resultant
controls across N41 and N131, including left-linear, right-linear, and
both-linear leading-coefficient cases. The first Boolean circuit receipt
compared a field-operation trace with the direct formula but did not test the
emitted clauses. Its follow-up seed formula exposed that its branch combiner
encoded AND where the trace used OR. Preserve the failed v1 formula and its
`UNSATISFIABLE` pinned control; it was never used for an ordinary search.

The corrected [v2 circuit preflight](n41_w6_s8_double_resultant/circuit_preflight_v2.json)
checks the field result, every emitted CNF clause, and every XOR row on N41 and
N131 witnesses, eight deterministic random inputs per field, and all three
exceptional linear branches. N41's target-condition block has 63,925 Boolean
variables, 60,191 AND gates, and 180,839 clauses. N131's block has 648,122
variables, 635,226 AND gates, and 1,906,484 clauses (35.48 MB CNF and 11.77 MB
XOR text) at 484 MB sampled Python peak RSS. This is only the target-condition
lower bound; it excludes factor-base masks, rationality, leaf equations,
folded-column checks, and a solver.

The [complete N41 seed formula](n41_w6_s8_double_resultant/seed_formula_n41_v2_20260930/formula_receipt.json)
adds eight valid W6 masks, distinct folded columns, four leaf S3 equations,
and a selector for the four raw preimages of the same public target. It has
77,619 variables, 72,501 AND gates, 219,479 clauses, and 4,892 XOR rows. Its
pinned known-row solver control returned SAT in 93.1 ms, and the checked-Sage
[model replay](n41_w6_s8_double_resultant/seed_formula_n41_v2_20260930/known_control_sage_replay.json)
verified all factor-base memberships, eight distinct columns, the four leaf
equations, and an exact signed group lift to the frozen public point.

The first ordinary-run wrapper (`R1`) failed before launching CryptoMiniSat
because its process-tree sampler enumerated system PIDs and received an
`EPERM`. The completed target formula is preserved; query/formula timings
were lost, and no solver work occurred. The corrected `R2` sampler inspected
only the known runner and solver PIDs. On the same single frozen public point,
the [ordinary N41 attempt](n41_w6_s8_double_resultant/ordinary_run_R2_20260930/receipt.json)
included the target preimage query, target-dependent formula generation,
serialization, and solver work. It reached the 120-second parent cap at
120.027 seconds with 468,615,168 bytes sampled peak RSS and no SAT model. The
exclusive stage totals were 3.511709 ms target query and 120.023614 s target
PDP; relation checking had no model to check. This is a censored one-target
failure, not UNSAT and not a relation-yield estimate. Do not rerun this same
formula with a longer limit. Neither this stage result nor the pinned control
is an IC-versus-rho comparison or a speedup claim.

The earlier N53 panel remains secondary and unstarted. Its latest
[nonlaunch preflight](../koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting/validation/preflight_gate_20260930T190820.788135Z.json)
at 19:08 UTC recorded 3,830,636,544 bytes free, below the 4-GiB disk guard,
and failed the N83 idle/handoff check because Q1073 start markers remained
unresolved. It records `measurement_started=false`; the eight-target wrapper
has no start marker, rows, or summary. Keep it unlaunched. The primary goal
remains one previously unseen ECC2K-130 target with online timing and a paired
single-target rho solve.

### Fresh single-target N41 W6/S8 distinct-window comparison — 2026-09-30

The N41 analogue of the W18/S8 distinct-window policy passed its exact
geometry screen with eight 64-point slots, `B=512`, `K=26`, and combined
subspace rank 40. On one fresh public target
`Q=(109873542336,1229600946914)`, the 4+4 indexed join made 338,335 right-side
probes, found seven exact sum hits, rejected six for repeated columns, and
independently replayed a valid eight-point row. Reusing the verified 26-column
factor logs recovered scalar `266838792960`; checked Sage verified the
relation, scalar replay, and validation-only fixture. The canonical candidate
is
`IC1N41Ckb1fb512PDP8mitmRCsampleLAgaussTDdirectISO0hb078ef917200`, the
single-target workload ID is `cd2effe39a2d`, and the run ID is
`IC1N41Ckb1fb512PDP8mitmRCsampleLAgaussTDdirectISO0hb078ef917200Wcd2effe39a2dR1`.

The complete IC online phases total 477.831 ms after excluding input loading,
process launch, and reusable base/log/index setup. The paired one-worker rho
solve on the same point took 149.762 ms online and recovered the same scalar.
`rho_online / IC_online = 0.3134`; IC was 3.191 times slower for this one toy
target. There is no batch panel and no ECC2K-130 speedup claim.

The exact `B=512`, `K=26` geometry supports the factor-log mapping, but the
indexed join does not transfer to N131. The
[explicit scaling rejection](n41_w6_s8_distinct_window_geometry/n131_index_scaling_audit.json) projects
262,614 points per W18 slot into about 68.97 billion cross-window pair rows
and `4,756,324,741,777,040,096,016` first-four table rows. The native 32-byte
row layout would require about `1.522e23` bytes before overhead, so this
candidate is closed for N131. The next route must avoid materializing pair or
four-sum tables, pass an unpinned N41 single-target relation with independent
replay, and provide a credible N131 work/memory bound before any fresh
challenge-target attempt. See the
[paired result](N41_W6_S8_DISTINCT_WINDOW_RESULT.md).

### Cross-pair shared-overlap N41 gate — 2026-09-30

The [target-coupled shared-overlap trial](N41_CROSSPAIR_SHARED_OVERLAP_RESULT.md)
added three exact linear equations requiring adjacent pairs 2 and 3 to share
their N41 overlap coordinate. A previously independently verified natural row
passed all equations and serialized XCNF constraints, but the public-only
one-target run reached its 120.045-second cap with no model or row. All four
branch outcomes, exclusive target-online phases, 657-MB sampled peak RSS,
and source/formula hashes are retained. This is a censored failure, not an
UNSAT proof. A uniform-overlap N131 W19 transfer would divide the predicted
one-diagonal support by `2^9`, to about 0.063 rows per point, so this
restriction alone is not a viable challenge-field algorithm. The goal remains
an unpinned, independently replayed N131 relation and complete verified
single-target DLP/rho comparison.

### Small-pair output algebra on a dense 24-slot N131 base — 2026-09-30

The [affine W6/S24 screen](N131_AFFINE_W6_S24_RESULT.md) changes the base
policy to twelve pairwise orbit-disjoint affine W6/Frob(W6) blocks. Exact
checked-Sage geometry gives `B=1,440` subgroup-usable points and `K=360`
signed-Frobenius columns. Every one of the twelve complete pair-output
x-coordinate sets has a degree-at-most-two Boolean feature rank equal to its
2,808–3,968 output count, leaving 4,679–5,839 independent quadratic
annihilators; a second checked-Sage implementation replayed all 167,744
raw pair additions and ranks. Uniform group-sum accounting predicts about
4,401.69 ordered, distinct-column 24-slot rows per public point, but no
ordinary target was queried and no target-coupled solver has been measured.
This provides a new exact local algebraic search policy, not an IC candidate
or speedup. The next gate is an unpinned small-field joint solve using these
output constraints, then a credible N131 work/memory bound before a fresh
challenge-field query.

### Affine W2/S24 ordinary N41 row existence control — 2026-09-30

The [indexed one-target control](N41_AFFINE_W2_S24_INDEXED_CONTROL_RESULT.md)
used a frozen N41 analogue with exact `B=152`, `K=38`, and the same public
target. A target-independent sample and 1,439,998-entry A+B index found a
natural 24-point distinct-column row after 7,683 target probes. The row's
online search and exact group check took 217.987 ms after 43,301.056 ms of
reusable setup, and independent checked Sage verified every seed and point.
This confirms target support but **does not pass the table-free method gate**.
The next solver must use the local equations to obtain an unpinned row with
target-coupled elimination under the same 120-second, 4-GiB, one-worker
limit. This is still a proposal with no N131 relation, target scalar, or
IC/rho speedup.

The [complete N41 raw pair-output screen](N41_AFFINE_W2_S24_PAIR_OUTPUT_RESULT.md)
independently replayed 1,344 raw additions and all twelve rank results in
checked Sage. Each pair has a 24- or 48-value output-x domain among 862
quadratic features. The first 16 lightest equations overfit pair 10's
constant-bit structure; a larger held-out selection reduced but did not
eliminate false positives, leaving six of 6,144 unseen rational curve-x
controls. The next method must couple these necessary local constraints to
the public target, then perform exact seed and group recovery. The filter
alone is not an N41 solver or an N131 runtime estimate.

### Exact local-domain joint-solver gates — 2026-09-30

The [target-coupled S3 trials](N41_AFFINE_W2_S24_JOINT_SOLVER_RESULT.md)
used the complete 24/48-value pair-output domains on the same frozen public
N41 point. Two source-bound known-row controls passed when all intermediate
coordinates or functional root bits were pinned; the corresponding
pair-selector-only controls both timed out at 30 seconds. A public-only
functional tree with a target-independent all-zero root pattern reached
120.063 seconds without a model. Replacing 336 local one-hot flags with
62 binary selector bits passed its exact known-row control, but its
public-only trial also reached 120.031 seconds without a model. Both
public failures are censored, not UNSAT. No N41 unpinned relation came
from the new solver.

The binary local domains do fit the challenge-field construction budget:
all twelve frozen N131 domains built in 28.754 seconds at 629 MB RSS, and
an eleven-node functional tree with dummy target constants built in
65.319 seconds at 1.965 GB RSS. This is source-bound **formula construction
only**. Solver memory, target-online time, and relation yield at N131
remain unknown. The next experiment must generate target-dependent
elimination or propagation before a general solver; another selector
encoding of the same S3 tree is insufficient evidence for promotion.

### 2026-10-01 N83 Q1073 terminal audit and current handoff

Q1073 retry 2 reached a terminal receipt at 2026-09-30 22:05:31 UTC. This
remains a proposal/query-stage record (`candidate_id: null`, `run_id: null`)
on `EC1N83Ckb1h876c2921cb64`, using the known-log `B=8,000,204`,
`K=48,194` base. Its frozen table had `2^33` descriptors and its query
window was `[12,348,030,976, 12,884,901,888)` (`2^29` representatives),
covering 89,120,571,392 lifted query pairs. The native receipt records zero
exact-hit queries; the independent Sage sidecar records zero replayable
natural relations and no verified target DLP. The terminal audit binds the
receipt hash `b3bb9e0cb9910fe12df6c8c2cf8f388f736bf75bfeb03e6481284ca3cf404493`
and classifies it `terminal_zero_hit_independent_sage_audited`. The measured
`10,924.534 s` target-online interval is not a clean performance comparison:
the audit notes host disk pressure, and this known-log proposal is not a
complete IC candidate. The first attempt remains separately recorded as an
interruption with unknown work and receives no coverage credit. Evidence is
retained in
`/private/tmp/koblitz-pair-claw-pr-20260929/experiments/koblitz-pair-claw-20260929/runs/`,
including the retry terminal receipt, Sage verification, terminal audit, and
first-attempt interruption receipt.

The refreshed coverage ledger credits the audited retry once: 823,190,880,256
modeled native field calls, 32 new primary cells, 32 M32-extension cells, and
64 M33-extension cells. Attempt 1 contributes no additional work or coverage;
the zero-hit retry is still not a natural relation or a DLP.

At the 2026-10-01 00:53 UTC status check, the next adjacent Q1074 window
`[12,884,901,888, 13,958,643,712)` (`2^30` representatives) already had a
start marker and live controller/wrapper handles, but no terminal receipt.
Keep that work intact and preserve both its marker and Q1073's first-attempt
marker. The Q1060/Q1062 idle checks therefore still report competing N83
markers. At that check the system volume had 2,659,557,376 bytes free, below
the N53 panel's 4-GiB startup minimum; the eight-target N53 panel remains
unstarted. After Q1074 is terminal, validate its receipt, restore the 4-GiB
system-volume margin, and rerun the frozen N53 nonlaunch preflight
before starting any panel measurement. Keep Q1073's zero-hit window as a
bounded stage observation only; it does not clear the N83 ordinary-relation,
factor-log, complete-DLP, or ECC2K-130 gates.

At 2026-10-01 01:04 UTC, `lsof` confirmed Q1074's controller, checked-Sage
wrapper, and native worker PID 15300; the native worker had four candidate
spill files open at about 48.9 MB each. Its terminal receipt was still absent.
System-volume free space had recovered to 3,677,511,680 bytes, still below
the N53 4-GiB start gate. Preserve the live run and do not start the N53 panel
while either that run or the disk guard remains unresolved.

At 2026-10-01 01:17 UTC, Q1073 attempt 1's marker was formally reconciled by
[`reconcile_n83_q1073_attempts.py`](/private/tmp/koblitz-pair-claw-pr-20260929/experiments/koblitz-pair-claw-20260929/reconcile_n83_q1073_attempts.py).
The hash-bound [reconciliation receipt](/private/tmp/koblitz-pair-claw-pr-20260929/experiments/koblitz-pair-claw-20260929/runs/n83_local_arm_m33_q1073_attempt_reconciliation.json)
keeps the attempt-1 interruption as unknown and uncredited, and preserves its
exact start-marker bytes at
`/private/tmp/koblitz-pair-claw-pr-20260929/experiments/koblitz-pair-claw-20260929/runs/reconciled_start_markers/n83_local_arm_m33_q1073.started.json`.
The Q1060/Q1062 status checks now list only Q1074 as a competing start marker.
Q1074's controller, wrapper, and native PID 15300 were live at reconciliation;
its terminal receipt is absent. The status snapshot reported 3,550,670,848
system-volume bytes free, still below the N53 panel's 4-GiB start gate. The
eight-target N53 panel remains unstarted.

### N83 representation and planted-control audit — 2026-10-01 01:28 UTC

The N83 admission records show that the >63-bit representation and bounded
planted-control steps already have evidence, with two distinct curve/method
tracks that must not be conflated. The proposed N83 S3-root index on
`EC1N83Ckb1hc1776f347753` has a packed 128-bit root-slot design, but its
estimated root-table storage is 2.95 TiB for the d15 geometry and 11.86 TiB
for d16; it is not an admissible workstation implementation. The separate
quotient-pair/Bloom query path on `EC1N83Ckb1h876c2921cb64` retains the full
83-bit x key in `unsigned __int128` and mixes both 64-bit limbs. Its current
limitation is query yield, candidate spill/exact-replay cost, and resource
pressure, not key truncation. See
[`N53_N83_NEXT_GATE_AUDIT_20260929.md`](../koblitz-cofactor-fiber-20260928/N53_N83_NEXT_GATE_AUDIT_20260929.md)
and the [N83 pair-index design](../koblitz-n83-index-design-20260929/README.md).

The M=4096 build/save/map planted controls passed for both B8M and B32M bases,
including checked-Sage witness and scalar replay. They validate snapshot and
witness transport only; they do not establish full-size M31 memory behavior
or natural relation yield. The next unpassed stage is an ordinary query on the
quotient-pair/Bloom path. Q1073 retry 2 remains an audited zero-hit observation
on that curve. At the 01:28 UTC live check, Q1074 still had controller 14342,
wrapper 14956, and native worker 15300 open, with four growing spill files and
no terminal receipt. System free space was 3,102,428 KiB, below the N53 panel's
4-GiB guard. Preserve Q1074; after its terminal audit, the N53 panel still
requires both a clear N83 idle/handoff gate and at least 4 GiB free before
measurement.

### N53 panel nonlaunch preflight — 2026-10-01 01:42 UTC

Ran the frozen RCsample runner's documented `python3 run_panel.py
--preflight-only`. It exited before any measurement in
`require_n83_idle_and_handoff_complete` with `Q1060 campaign status is not
idle and reconciled`. The contemporaneous read-only Q1060 and Q1062 status
JSON both name Q1074's live start marker as the competing work. Q1060 itself
has zero active rectangles and zero failed attempts with unknown native work;
Q1062 has zero active ranges, no completed full range, and one retained
unknown-work failure from the audited resource-aborted range that still
requires explicit retry for that Q1062 campaign. The guard reports
`system_free_bytes=3,130,273,792`, below the panel's 4-GiB threshold by
1,164,693,504 bytes. The runner has no start marker, measurement rows, or
summary; no measured process was launched. After Q1074 reaches a terminal
receipt, reconcile its competing marker, restore the disk guard, and rerun
this preflight before measurement.

### ECC2K-130 instance handoff — 2026-10-01 01:52 UTC

The companion repository already freezes the public ECC2K-130 curve and
challenge point in
[`ecc2k130-fixed.json`](/Volumes/SSD990/crypto/docs/ic/params/ecc2k130-fixed.json):
polynomial-basis `GF(2^131)`, modulus
`0x800000000000000000000000000002007`, subgroup order
`680564733841876926932320129493409985129`, cofactor 4, generator, and the
public target. The candidate catalog identifies the same source curve as
`EC1N131Ckb1h136f03e58c98` in
[`isogeny_routes.json`](../ic-candidate-catalog/isogeny_routes.json).
This is the final-stage instance source only: its existing weight-two
factor-base recipe and three-summand setting are not promoted as the eventual
algorithm. Keep the candidate and workload IDs unset until the N83 scaling
gate passes and the final method, rho policy, target law, and resource envelope
are frozen.

### Approved next-step check and panel audit — 2026-10-01 02:03 UTC

The user approved the staged roadmap. I re-audited the frozen N53 generalization
panel before launch: it has eight distinct public targets, eight one-target
workloads, one fresh RCsample solve and one single-target rho solve per point,
one worker per solver, and known scalars confined to the validation sidecar.
The paired online intervals and candidate/rho source hashes are frozen. This
measures prepared-online generalization only; it does not charge target-
independent setup or answer the cold-start question. The panel remains
unmeasured, with no start marker or measurement rows. The runner preserves the
five exclusive IC online phases, rho setup/walk/validation phases, reusable
setup, relation-attempt outcomes, verified and novel relation counts, final
rank, actual factor-base points, folded columns, peak RSS, and operation
counts. Independent Sage replay gates every reported paired speedup.

At 02:03 UTC, `lsof` still showed Q1074's checked-Sage wrapper (14956) and
native worker (15300) live. The worker retained four open candidate spill files
of about 71.4 MiB each; the terminal receipt was absent. The system volume had
3,017,756 KiB available, 1,176,548 KiB below the panel's 4-GiB gate. I found
large unrelated temporary artifacts but made no disk changes while Q1074 is
active, to avoid perturbing that query. Preserve Q1074 and rerun the panel's
nonlaunch preflight only after the N83 handoff is terminal/reconciled and the
4-GiB disk guard passes.

At 02:10 UTC, Q1074 was still live with four spill files open at about
73.8 MiB each and no terminal receipt. System-volume free space had fallen to
1,942,216 KiB, now below the Q1074 preflight's 2-GiB spill-volume floor and
the N53 panel's 4-GiB floor. The checked wrapper writes a success/failure
receipt and removes its own start marker on terminal paths; do not remove the
marker manually. Once the receipt appears, audit it and rerun the Q1060/Q1062
idle statuses before the N53 nonlaunch preflight. No disk cleanup was done
while Q1074 remains active.

At 02:19 UTC, a later sample showed Q1074 still live; its four open spills had
grown to about 76 MiB each. Free space had recovered to 2,835,200 KiB, above
Q1074's 2-GiB floor but still below the N53 panel threshold. The multi-gigabyte
temporary directories inspected for cleanup are Git worktrees or a shared Git
object database with many other worktrees attached, not disposable build
targets. I left those paths unchanged. If the 4-GiB guard remains closed after
Q1074 terminates, choose any cross-project relocation only after identifying
an artifact whose owner and use are clear.

### Literature checkpoint — 2026-10-01 02:21 UTC

The primary-source check did not reveal a reason to change the staged gates.
Galbraith, Granger, Merz, and Petit give the established Koblitz-curve route:
Frobenius-invariant factor bases reduce the number of point-decomposition
systems, with a corresponding linear-algebra improvement. The N53 candidate
already uses complete signed Frobenius orbits. The SAT-based binary-curve
study reports point-decomposition gains over Gröbner bases (up to 300x in its
tested cases), while also reporting that the complete index-calculus method
did not beat generic methods for the tested prime-degree fields. This
reinforces the requirement to measure relation yield and the full charged
online/cold costs rather than promote a PDP-stage speedup alone. Sources:
[IACR ePrint 2020/1315](https://eprint.iacr.org/2020/1315.pdf) and
[the SAT-based index-calculus study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7334981/).

At 02:25 UTC, `lsof` reconfirmed the Q1074 controller, checked-Sage wrapper,
and native worker live. The four unlinked candidate spills were about 79.7 MiB
each, and no terminal receipt existed. The system volume had 2,806,580 KiB
free, below the N53 4-GiB gate. The N53 panel remains unstarted.

### Pre-run rho identifier correction and launch recheck — 2026-10-01 02:42 UTC

Before any measurement, the cold-start candidate's protocol v1 was found to
label an RCsample IC candidate run ID as `rho_run_id`. Protocol v2 now uses
canonical `RHO<reference-hash>W<workload>R<repeat>` IDs and records
`baseline_pair_measurement_run_id` separately. The candidate ID and identity
hash are unchanged; the v1 protocol and freeze receipt remain preserved. The
[correction receipt](../koblitz-n53-targetspan-parallel-index-20260930/validation/rho_run_id_correction_receipt.json)
records both protocol and freeze-receipt hashes, all five old/new ID pairs,
the unchanged candidate identity, and the no-measurement-start state. The
independent replay now validates the canonical rho ID, baseline pair ID, and
frozen rho artifact hash. `python3 -m py_compile` passed for the freezer,
runner, and replay scripts. No candidate runs, measurement rows, panel start
marker, or independent replay artifact exists.

The nonlaunch checks remain closed on Q1074 reconciliation. At 02:37 UTC the
cold-candidate preflight returned code 2: the eight-target panel was not
finalized and its nested N83 idle check produced no parseable status JSON.
The direct panel preflight failed because Q1060 was not idle and reconciled.
The guard's `shutil.disk_usage` reading was 10,714,914,816 bytes; subsequent
root-volume samples were 9,609,424,896 bytes and then 5,791,510,528 bytes,
all above the 4-GiB minimum. At 02:42 UTC, `lsof` still showed the Q1074
controller (14342), wrapper (14956), and native worker (15300), with four open
candidate spills around 85 MiB each. The start marker remained and the
terminal receipt was absent. Preserve Q1074. Once its wrapper writes the
terminal receipt and removes its marker, audit that result, rerun the Q1060
and Q1062 idle/handoff checks, and run the frozen panel's nonlaunch preflight.
Only then launch the eight paired one-target N53 solves. The parallel-index
cold-start run remains queued behind independent replay of that panel.

At 02:45 UTC, a fresh read-only check again found Q1074's controller, wrapper,
and native worker active. All four spill files were still open and growing;
the start marker remained and the terminal receipt was still absent. Root
volume free space was 7,131,754,496 bytes, above the N53 threshold. The gate
therefore remains closed on Q1060/Q1074 reconciliation, not current disk
capacity. No N53 measurement was launched.

At 02:46 UTC, the same Q1074 PIDs remained visible in `lsof`; the four open
spills had grown to about 86 MiB each. The start marker still existed, no
terminal receipt had appeared, and root-volume free space was 7,124,992,000
bytes. Keep the N53 panel unstarted pending terminal reconciliation.

At 02:48 UTC, `lsof` again confirmed the same Q1074 controller, wrapper, and
native worker. Its four open spills had grown to about 87 MiB each. The start
marker remained, the terminal receipt was absent, and system-root free space
was 4,977,831,936 bytes, about 0.64 GiB above the N53 guard. The frozen panel
preflight still fails on the unreconciled Q1060 status; no measurement was
started.

### N83 index-design audit during the Q1074 wait — 2026-10-01 02:50 UTC

A read-only audit of the existing
[N83 design record](../koblitz-n83-index-design-20260929/README.md) confirms
that the 83-bit key-width problem is already handled: keys use `unsigned
__int128`, the hash mixes both 64-bit limbs, and Bloom hits are checked against
the full key and exact point relation. The independently replayed B32M
known-log base contains 32,000,816 usable points across 192,776 folded
columns; construction took 512.3 seconds and Sage replay checked all expanded
orbit points. This is a correct base/index control, not unknown factor logs or
a natural relation result.

The scaling model leaves relation yield as the open issue. At B=8,000,204 it
predicts 59 M31 chunks (21.03 trillion lifted pairs, 13.5 times `sqrt(r)`).
At B=16,000,408 it predicts 3.69 chunks; rounding to four gives only a 0.92
`sqrt(r)` operation-count margin. At B=32,000,816 it predicts about 0.23
chunk, and two R28 windows cost 89.12 billion lifted pairs (0.057
`sqrt(r)`). Those are model outputs, not observed relation rates. Therefore
the N83 follow-up should measure ordinary-query yield and full charged query
cost after the N53 panel; it should not spend another stage redesigning the
83-bit key encoding. The complete N83 factor-log and sparse-LA path remains
unbuilt.

At 02:50 UTC Q1074 was still live and the panel preflight still failed on
Q1060 reconciliation. Root-volume free space had fallen to 3,925,950,464
bytes, 369,016,832 bytes below the N53 4-GiB start guard. Keep both N53 and
N83 measurements stopped until Q1074 terminates and the handoff is reconciled.

### Literature screen for a one-relation alternative — 2026-10-01 02:54 UTC

A primary-source check screened the random target-dependent factor-base
algorithm of McGuire and Mueller. Their Algorithm 4.1 can avoid summation
polynomials, Gröbner bases, and global linear algebra, and is stated to apply
over any finite field. However, its own heuristic analysis gives O(p) cost and
explicitly says these algorithms are worse than Pollard rho. It is therefore
not a plausible route to the requested asymptotic advantage; retain it only
as a possible toy control if a later comparison needs one-relation recovery.
The source is [IACR ePrint 2017/1262](https://eprint.iacr.org/2017/1262.pdf).

Semaev's Boolean summation-polynomial method remains more relevant to a
subexponential advantage, but its reported comparison starts above extension
degree 310 under the stated first-fall-degree condition. The ECC2K-130 field
degree is 131, so that asymptotic observation is not evidence of a practical
win for this instance. This leaves the structured Koblitz/Frobenius route and
the unpinned target-coupled decomposition gate as the research focus; a
measured one-target result is still required. Source:
[IACR ePrint 2015/310](https://eprint.iacr.org/2015/310.pdf).

At 02:54 UTC, Q1074's controller, wrapper, and native worker remained visible
in `lsof`; the start marker existed and no terminal receipt had appeared.
The read-only process check measured 4,874,289,152 root-volume free bytes.
The frozen N53 panel preflight failed on Q1060 reconciliation before emitting
its resource snapshot. No measurement was started.

### Multi-list birthday-method applicability screen — 2026-10-01 02:57 UTC

The W6/S24 target relation can be viewed as choosing one pair-output point
from each of twelve lists whose sum is the public target. A standard
Wagner-style generalized-birthday merge is not directly available here: its
bit-prefix collisions need an efficiently computable additive projection,
but the target subgroup has prime order `r`, so every homomorphism from it to
a power-of-two group has trivial image. Low bits of canonical x or u
coordinates are not additive homomorphisms. Computing partial elliptic sums
before hashing restores correctness but incurs the Cartesian-product work
the list method was meant to avoid. Any viable multi-list successor therefore
needs a curve-specific target filter that avoids materializing those joins;
the existing S3/u constraints remain the concrete route to investigate.
This is a mathematical design screen, not an experiment or a complexity
claim for all possible list algorithms.

At 02:57 UTC Q1074's controller, wrapper, and native worker remained live;
its start marker existed and no terminal receipt was present. Root-volume free
space was 3,706,834,944 bytes, 588,132,352 bytes below the N53 panel guard.
The nonlaunch panel preflight also still failed on Q1060 reconciliation.

At 03:02 UTC, Q1074 was still live while system-root free space briefly read
1,622,843,392 bytes. Fifteen seconds later the same PIDs remained open in
`lsof`, the start marker remained, no terminal receipt existed, and free space
read 2,791,911,424 bytes. This fluctuation is not a terminal state or a reason
to alter the process; the N53 4-GiB guard remained closed at both samples.

### Exact-domain encoding reuse audit — 2026-10-01 03:04 UTC

A read-only check of the W4 quotient-mux artifacts rules out repeating a
simple exact finite-domain selector as the next solver. That trial already
represented the twelve complete even-u pair domains with 82 selector bits
and all S3 roots free; the pinned known-row control passed, but both the full
public solve and a seven-pair-fixed public slice timed out at 120 seconds.
Thus the remaining method change must use the public target to prune across
pair groups or eliminate intermediate S3 roots. See
[`N41_AFFINE_W4_U_QUOTIENT_MUX_RESULT.md`](N41_AFFINE_W4_U_QUOTIENT_MUX_RESULT.md).

At 03:04 UTC, Q1074's controller, wrapper, and native worker were still live.
The start marker remained without a terminal receipt; root-volume free space
was 2,936,631,296 bytes, below the N53 panel's 4-GiB guard. The direct panel
preflight continued to fail on Q1060 reconciliation.

### N53 panel gate recheck — 2026-10-01 03:08 UTC

The frozen eight-target one-target IC/rho panel remains unstarted. The
nonlaunch command `python3 run_panel.py --preflight-only` exited before
runtime capture or solver launch with `the Q1060 campaign status is not idle
and reconciled`. Read-only `lsof` still showed Q1074's controller (14342),
checked-Sage wrapper (14956), and native worker (15300); its start marker was
present and terminal receipt absent. The system volume reported 2,868,688
KiB (2,937,536,512 bytes) free, below the 4-GiB panel guard. No panel start
marker or paired measurement rows were created. Preserve Q1074; after its
terminal receipt and formal Q1060/Q1062 reconciliation, rerun this preflight
and require the 4-GiB guard before starting the frozen panel.

### Crypto Autoresearcher dispatch preflight — 2026-10-01 03:11 UTC

The bundled read-only harness doctor was invoked for this checkout with
`--repo /Volumes/SSD990/cryptanalysis --runtime codex --doctor`. It failed its
checkout-integrity gate because `orchestration/roles.yaml`,
`tools/research_dispatch.py`, `tools/generate_runtime_agents.py`,
`tools/check_runtime_bindings.py`, `.codex/config.toml`, and `.codex/agents/`
are absent. No dispatcher task was launched. This is an operational harness
limitation, not evidence about the ECDLP method or a change to the active goal;
dispatch requires the complete matching harness checkout and its generated
Codex bindings.

At 03:13 UTC, the Q1074 controller, wrapper, and native worker were still
live, with the start marker present and no terminal receipt. Available system
volume space had recovered to 3,912,276 KiB (4,006,170,624 bytes), still
288,796,672 bytes below the N53 panel's 4-GiB guard. The panel start marker,
paired rows, and summary were absent. Keep the panel unstarted until Q1074 is
terminal and reconciled and a fresh preflight sees at least 4 GiB available.

### Per-candidate N53 cold-phase budget audit — 2026-10-01 03:25 UTC

Recomputed paired break-even setup budgets from the three five-run N53 row
sets and checked their replay sidecars. All 15 rows report successful IC and
rho recovery with independent Sage replay. The one-worker RCsample median
setup budget is 1,576.400 ms; its recorded setup is 8,631.994 ms. For target
span, the correct paired budget is smaller because its measured online phase
is longer: median `rho_online - ic_online` is 670.542 ms. Holding non-index
setup and online costs at their paired baseline values gives a median
index-build ceiling of 363.432 ms for a win in at least three of five pairs.
The frozen 14-worker parallel-index candidate is the next cold-phase test
after the independent-target panel; it has no N53 run or result yet. The
[candidate-specific audit](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/COLD_START_AUDIT.md)
retains the per-run thresholds and explicitly labels the OS page-cache limit.
These are planning gates, not a measured speedup.

At 03:25 UTC, Q1074's controller (14342), wrapper (14956), and native worker
(15300) were still live, its start marker remained without a terminal receipt,
and its four spill files had grown to about 96.9 MB each. System-volume free
space was 3,722,316 KiB (3,811,651,584 bytes), 483,315,712 bytes below the
N53 panel guard. Keep the run untouched and leave the panel unstarted.

### N53 panel preflight after disk recovery — 2026-10-01 03:28 UTC

System-volume space then read 9,467,556 KiB (9,694,777,344 bytes), above the
4-GiB start guard. The nonlaunch `python3 run_panel.py --preflight-only`
recheck still exited in `require_n83_idle_and_handoff_complete()` with
`the Q1060 campaign status is not idle and reconciled`. `lsof` continued to
show the Q1074 controller, wrapper, and native worker; the start marker was
present and the terminal receipt absent. The N53 panel therefore remains
unstarted. Disk space met the guard at this sample; Q1060/Q1074 terminal
reconciliation remains the launch blocker. Recheck both conditions after the
receipt appears.

At 03:31 UTC, `lsof` again confirmed Q1074's controller, wrapper, and native
worker live. The four candidate spill files had grown to about 98.2 MB each;
the start marker remained and the terminal receipt was absent. System-volume
space read 6,168,696 KiB (6,316,744,704 bytes), above the 4-GiB guard. The
N53 panel still had no start marker or paired rows. Disk space fluctuates, so
the start-time guard must be sampled again after Q1074 is formally reconciled.

### Q1074 bounded-query scope audit — 2026-10-01 03:33 UTC

Read the frozen external plan, launch record, and start receipt while the
controller, checked-Sage wrapper, and native worker remained live. Q1074 is a
finite one-target query range of `2^30` representatives, corresponding to
178,241,142,784 lifted pair checks on the exact N83 `B=8,000,204` base. The
plan models 1,421,533,511,680 native field calls and a 9.98% target-hit
probability; both are predictions, not observed query cost or yield. The
proposal keeps `candidate_id: null`, and even a replayed hit would be a
query-stage relation observation, not a complete factor-log DLP. The run began
at 2026-09-30 22:11:32 UTC; at this check it was still active with no terminal
receipt. The N53 panel remains gated on its receipt and formal Q1060/Q1062
reconciliation.

At 03:37 UTC, `lsof` still showed all three Q1074 processes live, the start
marker present, and the terminal receipt absent. The four unlinked candidate
spill files were each about 99.6 MB. The frozen wrapper captures native stdout
and stderr until the subprocess exits, so there is no live query-count
counter. A rough ideal-Bloom projection is about 95 MB per worker for this
range, already below the observed spill size; that projection cannot establish
fraction complete or an ETA. Keep waiting on the process handle and terminal
receipt rather than inferring completion from spill size.

After a 30-second verified wait, at 03:41 UTC the same Q1074 controller,
wrapper, and native worker were live with the start marker present and no
terminal receipt. `lsof` showed the four unlinked spill files at about 100.5
MB each, slightly larger than the 03:37 sample. System-volume free space was
9,378,620 KiB (9,603,706,880 bytes), above the N53 panel's guard. The finite
query remains in progress; do not start the panel until the terminal result is
audited and the Q1060/Q1062 handoff is reconciled.

### Approved roadmap checkpoint — 2026-10-01 04:49 UTC

The user approved the sequence: finish the paired eight-target N53 panel,
measure cold-start separately, complete the N83 scaling gates, then attempt the
frozen ECC2K-130 target. The panel is still unstarted. The required
Crypto-Autoresearcher read-only preflight exited 2 before its doctor stage
because this checkout is missing `orchestration/roles.yaml`,
`tools/research_dispatch.py`, `tools/generate_runtime_agents.py`,
`tools/check_runtime_bindings.py`, `.codex/config.toml`, and `.codex/agents/`.
No campaign dispatch was attempted. Clear that operational gate by using the
complete matching harness checkout and rerunning preflight; the missing
bindings are not evidence about the algorithm.

At 04:48 UTC, read-only `lsof` still showed Q1074's controller (14342),
checked-Sage wrapper (14956), and native worker (15300). Its start marker was
listed without a terminal receipt. The four open candidate spill files had
grown to about 110 MB each; this is not a progress counter. Root-volume free
space was 4,272,758,784 bytes, 22,208,512 bytes below the N53 4-GiB launch
guard. Preserve Q1074. Do not launch N53 until it has a terminal receipt,
Q1060/Q1062 are formally reconciled, and a fresh start check passes the disk
guard.

An offline audit confirmed that the existing N83 index design already stores
the complete 83-bit key in an unsigned 128-bit value and uses Bloom membership
only as a prefilter before exact-key verification. The B32M known-log base
contains 32,000,816 points before folding and 192,776 columns; its planted
snapshot control is not ordinary relation yield. The base-scale script's old
ratios divided lifted-pair-test counts by Pollard-rho group-step counts despite
different operation boundaries. The generator, output model, and README now
report the rho square-root group-step count separately and explicitly forbid
interpreting that count-only reference as a speedup. The predictions remain
21,032,454,848,512 lifted pair tests at B8M, 1,336,808,570,880 at B16M after
rounding to four M31 chunks, and 89,120,571,392 for two R28 windows at B32M.
These are query-count predictions only; ordinary unknown-log relations, a
sparse log-recovery matrix, and a replay-verified DLP remain unbuilt.

### Q1071 terminal query audit and panel recheck — 2026-10-01 05:00 UTC

The old Q1071 process handle (PID 74577) is no longer present in `lsof`, and
its terminal receipt is present. The receipt hash matches the independent
Sage replay sidecar. Q1071 completed one Q1061 query rectangle on the public
N83 target using B=8,000,204 with all 48,194 folded-base logs fixture-known.
It covered 536,870,912 representatives, 89,120,571,392 lifted pair tests,
and an M32 table. Exact replay found zero hits; the Sage sidecar records zero
verified relations. The run therefore adds one measured zero-yield query cell,
not a natural-yield estimate or a DLP result. `candidate_id`, `workload_id`,
and `run_id` remain null.

The audited stage costs are 1,617.737 s for target-independent filter build
and 6,875.786 s for the target-dependent query/replay attempt, including
5,561.536 s query plus 1,314.249 s exact replay. Because it recovered no DLP,
this is not a successful one-target IC online time. Peak RSS was
11,059,445,760 bytes; candidate spill was 233,736,456 bytes. All 9,739,019
Bloom positives were false positives. The hash-checked audit is
[`q1071_knownlog_zero_hit_audit_20261001.json`](../koblitz-n83-index-design-20260929/q1071_knownlog_zero_hit_audit_20261001.json).

Fresh Q1060 and Q1062 status commands now list Q1074 as their only competing
start marker; Q1071 is no longer listed. The frozen N53 `--preflight-only`
check at 04:53 UTC still exited before runtime capture with
`the Q1060 campaign status is not idle and reconciled`. At 05:00 UTC,
read-only `lsof` still showed Q1074's controller (14342), checked-Sage wrapper
(14956), and native worker (15300) live, with no terminal receipt. System-root
free space was 7,295,066,112 bytes, above the panel's 4-GiB guard, but the
active Q1074 marker keeps the panel closed. No N53 measurement was started.

### Linearized Frobenius-subspace screen and Q1074 recheck — 2026-10-01 05:17 UTC

A primary-source review of Galbraith, Granger, Merz, and Petit's Section 4.1
checked the linearized-polynomial construction against the actual extension
degrees. Modular-order witnesses give `ord_53(2)=52`, `ord_83(2)=82`, and
`ord_131(2)=130`: for each prime divisor `p` of `n-1`, the residue of
`2^((n-1)/p) mod n` is not 1. Since each `n` is prime, `Phi_n` is irreducible
of degree `n-1`; the Frobenius-invariant subspace dimensions are only
`0, 1, n-1, n`. That construction therefore gives either a tiny coordinate
set or one of size at least `2^52`, not a tunable medium-size factor base for
these instances. This does not exclude distinct shifted non-invariant bases
or Galois-invariant sets from other algebraic groups. The calculation and
scope are recorded in
[`ALGORITHM_ROUTE_AUDIT.md`](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/ALGORITHM_ROUTE_AUDIT.md),
with the [primary paper](https://eprint.iacr.org/2020/1315.pdf). No Sage job
or experiment was run for this screen.

At 05:17 UTC, Q1074's controller, checked-Sage wrapper, and native worker were
still live and its terminal receipt was absent. The frozen cell uses an M33
table, four workers, and one R30 range of 1,073,741,824 representatives; its
9.978% hit probability is a finite-support heuristic, not measured yield.
Open spill files were about 112.7 MB each, which gives no completion estimate.
Root-volume free space was 9,036,357,632 bytes, above the N53 4-GiB guard, but
the live marker still prevents the panel preflight from passing.

### Latest single-target steering supersedes the panel roadmap — 2026-10-01 05:22 UTC

The active measurement objective is one previously unseen target, with IC and
rho solving the identical public point. Online clocks exclude process launch,
input loading, target construction, and reusable target-independent IC setup;
report preparation costs separately. Do not use multi-target throughput,
batch averages, or shared-table amortization as the acceptance gate. Earlier
approval notes about finishing an eight-target N53 panel first are superseded
by this instruction. Keep those records as historical or secondary evidence.

The N53 parallel-index v3 protocol has not started a measurement and includes
an eight-target panel as a start gate. Its controlled change is index-build
parallelism, while its own primary clock begins only after the index is ready;
that setup-only change cannot establish the requested online speedup. Preserve
the frozen artifacts, but do not launch that panel or treat this candidate as
the primary online-speedup path. Continue with a target-query or relation
method whose change can reduce target-dependent work. Any online comparison
still needs one frozen public point and an independently replayed scalar from
both arms.

Q1074 remains a separate N83 single-target query experiment, not a complete
DLP. A read-only `lsof` check at 05:21 UTC confirmed its controller (14342),
checked-Sage wrapper (14956), and native worker (15300) were still live, with
four growing candidate spill files. Preserve that active run and avoid starting
another CPU-intensive measurement until it has a terminal receipt and process
liveness is clear. The ECC2K-130 goal remains active: no challenge-target
factor logs, recovered scalar, or paired one-target rho comparison exists.

### N53 target-orbit query candidate frozen — 2026-10-01 06:04 UTC

A new target-query hypothesis is now isolated in
[`koblitz-n53-target-frob-orbit-20261001/`](../koblitz-n53-target-frob-orbit-20261001/).
Candidate `IC1N53Ckb1fb25864PDP4rootRCsampleLAgaussTDdirectISO0h30cf80c55c10`
uses the exact audited N53 `fb=25,864`, 244-column Frobenius-closed base and
the single frozen workload `dbb1afad2846`. The rank collector still uses the
fixed known-scalar targets. Only the final target extractor queries
`pi^j(Q)` at its sampled global shift and transports the recovered conjugate
scalar by `lambda^-j mod r`.

The focused Rust test passed for all 53 orbit points, checking both
`pi^j(Q) = [lambda^j d]G` and inverse scalar transport. This is a correctness
control for the orbit map, not evidence of decomposition yield or online
speedup. A subsequent [source-level equivariance audit](../koblitz-n53-target-frob-orbit-20261001/ORIENTATION_AUDIT.md)
rejected the proposed 53-fold coverage interpretation: rotating the indexed
pair and target together leaves their relative query unchanged.
`measurement_status.json` deliberately leaves every cost null. No candidate
measurement or Sage job was started. The extractor also retains exact-lift
time on unsuccessful attempts so the separate relation-check phase remains
complete rather than being folded into PDP time.

Preserve the current single-target steering: do not restart the superseded
eight-target panel. Before timing this candidate, Q1074 must have a terminal
receipt, Q1060/Q1062 must be formally reconciled, and their fresh start gate
must pass. Then use only the frozen one-target workload and pair every IC
solve with a one-target rho solve on that same public point. Include the
Frobenius orbit build in `target_query`; retain the exact relation check,
scalar transport, independent replay, and all unsuccessful rows. Any measured
N53 improvement is a toy-stage result; scaling the code past 63 bits and
clearing the exact N131 challenge remains open.

### Accepted secondary N53 generalization panel — 2026-10-01 06:09 UTC

The user has now explicitly accepted the earlier proposal to test whether the
N53 RCsample online win generalizes across independently selected targets.
This reopens that panel as a **secondary generalization experiment**; it does
not replace the primary one-target objective. Each target remains a separate
one-target IC/rho pair with its own frozen workload, exact point, seeds, and
resource record. The frozen gate and workload list are in
[`N53_HOLDOUT_PANEL_PROTOCOL.md`](../koblitz-n53-target-frob-orbit-20261001/N53_HOLDOUT_PANEL_PROTOCOL.md).
Use the audited `fb25864` RCsample candidate for this panel;
keep the newer target-Frobenius-orbit candidate as a separate method and
measurement.

Q1074 is still live, so do not start the panel, cold-start measurements, or
other CPU-intensive runs until its terminal receipt exists, Q1060/Q1062 are
formally reconciled, and the fresh preflight passes. After the panel, continue
with the N53 cold-start bottleneck and the N83 scaling gate before any N131
challenge attempt. Preserve failures, timeouts, and zero-yield targets.

### N131 order-four coordinate identity audit — 2026-10-01 06:23 UTC

The exact N131 curve now has a checked-Sage audit for the degree-four
coordinate `t=(x+1)^2/(x^2+x+1)` and invariant `eta=t^2+t`. On the frozen
generator and public point plus 132 additional listed points, the audit
verified the repository's polynomial-basis decoding, scalar fixture replay,
`T2=(0,1)`, `T4=(1,0)`, `t(P+T4)=t(P)+1`, `eta(P+T4)=eta(P)`, and
`eta(pi(P))=eta(P)^2`. The `w=u^2+u` frame already used locally satisfies
`w(P+T4)=1/w(P)`; `t=1/(w+1)` conjugates that reciprocal action to a
translation. See [the audit note](N131_ORDER4_COORDINATE_AUDIT.md) and its
[source and receipts](n131_order4_coordinate_audit/).

This supplies a verified coordinate identity, not a new candidate. Exact
N131 factor-base counts in the new `t`/`eta` policy, a complete five-point
invariant relation equation, branch handling, and an unpinned ordinary row
are still absent. Existing N41 small-symmetry tests remain negative, so the
next method must first pass the frozen one-target toy gate with a materially
new relation equation before any ordinary N131 attempt. No Sage performance
measurement, relation search, factor-log run, or rho comparison was started.
The existing W27 reciprocal/Frobenius scan found no reciprocal collisions,
so deduplicating its current base by `eta` cannot reduce its measured
columns; any gain must come from a new invariant-space base and solver. The
audit now gives a concrete `V29=span(1,X,...,X^28)` proposal with a predicted
`~2^26` one-representative base before Frobenius expansion under a balanced
trace gate. This is not an exact count; the next gate must enumerate it and
verify the point-lift quotient before assigning a proposal or candidate ID.

Q1074 finished at 06:17:32 UTC, before this checkpoint. Its frozen result
receipt records one target, `2^30` representatives, zero exact hits, 25,563.479
seconds target-online, and 21,796,798,464 bytes peak RSS. The independent
checked-Sage sidecar hash-matches the receipt and confirms zero verified
relations. The worker and controller processes were absent on the 06:23 UTC
check. Its detached controller JSON still says
`launched_process_not_terminal`, so the launcher-level terminal handoff is
not formally closed even though the result and independent replay exist.
Do not count this N83 zero-yield stage as an IC result or speedup. The N53
secondary panel remains gated on formal Q1060/Q1062 reconciliation; no
CPU-intensive N131 workload was started from this checkpoint.

### Fixed-target relative-orientation N53 candidate — 2026-10-01

The rejected common-shift query now has a mathematically distinct successor:
[the fixed-target relative-batch candidate](../koblitz-n53-relative-batch-20261001/README.md).
It keeps `Q` fixed, tries eight distinct pair shifts per quotient S3 root,
and batches the generic S3 inversions. Its exact serial-collector identity is
`IC1N53Ckb1fb25864PDP4rootRCsampleLAgaussTDdirectISO0ha70409b4797d`,
with `B=25,864`, 244 folded columns, and one-target workload `dbb1afad2846`.
The source and executable are frozen. Focused N53 root arithmetic and N13
exact-group controls pass. A timing-accounting correction ensures failed
exact lifts are charged to the relation-check phase even when no row is
found. This is **correctness-only** evidence; its ordinary N53 relation yield,
online time, scalar recovery, and same-point rho ratio remain unmeasured.
There is no N131 transfer claim from the 63-bit implementation.

The N83 Q1086 worker had a live wrapper at the latest read-only check and no
terminal result file, so the N53 candidate measurement and secondary panel
were not launched. Once that worker has a terminal receipt and the campaign
preflight passes, the next useful comparison is one frozen N53 public target
against the one-orientation serial parent, with failures preserved and a
matched one-target rho reference. Even a verified N53 win would only select
a method for a separately bounded N131 design. The active challenge goal
still requires the first ordinary unpinned N131 row, useful rank, base logs,
a verified target scalar, and paired online timing.

### Direct N131 order-four projection identity and bounded base geometry — 2026-10-01

The existing invariant `eta=t²+t` now has the exact identity
`x([4]P)=eta(P)^(-4)` on the nonexceptional curve locus. The
[source-bound audit](N131_ORDER4_PROJECTED_X_RESULT.md) checked it on 134
points on the exact N131 curve, and checked the complete rationality/subgroup
branch classification for the V8 toy subspace. A separate ARM64 native
batched-inversion counter matched the V8 Sage counts and completed V16 and
V24 trace-branch counts; V24 has 2,096,519 accepted `eta` values in its `11`
branch. This gives a direct way to generate subgroup x-coordinates for a
future invariant-space factor base, without first solving the original
quadratic for x and y. Exact Frobenius-intersection ranks bound its V24
folded seed columns to 2,094,433–2,096,519; for V29, folding can remove
at most 16,544 accepted seed representatives. This means the invariant
coordinate alone does not produce a small relation matrix. It is geometry
evidence, not an IC candidate or a measured target relation. V29
enumeration, exact usable base and folded
columns, a target-conditioned five-point solver, an ordinary N131 row, and
the full DLP comparison remain open. The live N83 Q1086 worker was preserved;
no large V29 enumeration or target search was launched.

### Exact N131 transformed S3 pair primitive and W7 linear-rank screen — 2026-10-01

The direct projected coordinate gives the local equation
`(z1+z2+z3)^2+p+p^2=0`, `p=z1*z2*z3`, for
`z=x^(-1/4)` on subgroup points. A checked-Sage audit on the exact curve
matched both pair-addition x branches for 64 distinct pairs, rejected 64
wrong-third-point controls, and checked 16 equal-input identity branches.
The [result note](N131_ORDER4_PROJECTED_X_RESULT.md) records the derivation.
Applying this z-coordinate to every distinct projected x in the twelve
selected-W7 pair domains gave rank and affine dimension 130 in **every**
block: only the universal `Tr(z)=0` constraint remains. The local quadratic
is complete as an x-coordinate pair primitive, but it supplies no
block-specific linear pruning and no bounded ten-block public-target join.
Sign lifts, distinct folded columns, an ordinary N131 row, factor logs, and
the single-target DLP/rho comparison remain unmeasured.

### Exact order-four invariant-base geometry update — 2026-10-01

The ARM64 native counter completed the trace-branch enumeration for V20 and
V29 as well as V24. V29 has 67,103,575 trace-11 eta seeds; exact overlap
enumeration and independent checked-Sage orbit replay now give
**K=67,099,484** folded columns and **B=17,580,064,808** actual subgroup
points. The [V29 exact audit](n131_order4_projected_x_audit/v29_exact_audit.json)
binds these cardinalities. It saves only 9,861 columns (0.0147%) against
the exact W27 geometry.

An exact V20 signed-Frobenius orbit pass found **B=34,152,486** actual usable
points and **K=130,353** folded columns from 130,487 eta seeds. It checked
all 524,287 t-pair representatives, and all 130,353 nonzero eta orbits have
length 131. The [geometry result](N131_ORDER4_SUBSPACE_GEOMETRY_RESULT.md)
records the native source and binary hashes, seed/orbit-set digests, stage
time, and peak memory. The result is geometry only; no relation equation,
candidate ID, natural relation, factor logs, target scalar, or single-target
IC/rho timing exists for this policy.

The [corrected support screen](n131_order4_projected_x_audit/support_screen.json)
uses `binomial(K,m)*262^m` choices with distinct folded columns and any
signed-Frobenius point in each column. Its representation mean over all
subgroup targets is exact: V20 first exceeds one at six points (about 3,238
choices per target on average); V29 reaches about 5.848 at four points but
has roughly 67 million columns. These are group-wide averages, not fixed
target relation-yield measurements or solver costs. Earlier estimates based
on `K` alone apply only to a solver restricted to canonical representatives;
they do not model a solver that can use the full signed-Frobenius base. The
next gate is a complete target-conditioned equation for an explicitly
declared search domain, first tested on one toy target. Do not launch a
multi-target measurement or treat these geometry counts as a single-target
speedup.

### Q1086 single-target N83 query ended without a result — 2026-10-01

The previously live Q1086 process is now terminal. Its native worker received
`SIGINT` at 07:35:09 UTC after a 06:22:37 UTC start; the terminal receipt has
null phase counts, `cumulative_work_known=false`, and no independent Sage
replay. Keep the cell as failed/censored and do not infer a zero hit. This
does not clear the separate Q1060/Q1062 reconciliation and storage preflight
gates for any later single-target toy measurement. See
[`Q1086_MODEL_INTERPRETATION.md`](../koblitz-n83-index-design-20260929/Q1086_MODEL_INTERPRETATION.md).

### Exact V20 compact base membership — 2026-10-01

The [compact membership oracle](V20_COMPACT_MEMBERSHIP_RESULT.md) now maps a
verified nonidentity subgroup point to its V20 signed-Frobenius column by
forming `z=x^(-1/4)`, taking the minimum of its 131 Frobenius conjugates,
and searching the 3,128,472-byte orbit-representative index. The source-bound
Darwin ARM64 control passed 1,024 checked-Sage positive and 1,024 negative
subgroup x queries; 64 positive x-lifts were independently replayed. Its
2,048-query native membership interval was 7.608 ms with 4,734,976 bytes
process peak RSS. This removes the need to materialize all 34,152,486 V20
points merely to test membership or assign a folded column. It is a stage
diagnostic on frozen controls, not an ordinary relation or target-online IC
result. The six-summand target-coupled solver, natural yield, factor logs,
challenge scalar, and paired rho result remain open.

A [six-leaf transformed-S3 gate](v20_sixleaf_s3_gate/receipt.json) also
passed 16 planted exact-curve trees, 80 positive local equations, 16
wrong-target root controls, and exhaustive 64-way sign decoding for each
target. It defines the nonexceptional target equation but does not supply a
public-only solver or ordinary relation yield.

### V20 rotation-collision-cover design — 2026-10-02

The fixed-slot V20 six-leaf circuit suggests a target-coupled support
expansion: let any pair with equal Frobenius shifts occupy the shared-rotation
slots, using commutativity to relabel the six leaves. From the exact
`K=130,353` support count, six independent shifts collide with probability
`1-(131)_6/131^6 = 0.1096498831...`. The exact group-wide six-point mean
therefore rises from `24.71785175...` for one fixed pair to
`355.05055182...` for any colliding pair, a `14.3641...`-fold count increase
over the fixed-slot restriction. The [design note](v20_factored_sixleaf/ROTATION_COLLISION_COVER_DESIGN.md)
specifies the symmetry constraints, exact-column filtering, equation tree,
and replay gate. These are representation counts averaged over the subgroup;
they do not establish support for the frozen target or solver speed. The
any-pair circuit is not implemented, and its `candidate_id`, `run_id`, and
costs remain null. The agreed N83 ordinary-query and DLP gates still precede
any new N131 search.

The frozen N53 holdout-panel preflight was rechecked on this date and again
stopped before Sage startup: the pinned `/private/tmp/koblitz-pair-claw-pr-20260929`
worktree and Q1060-to-Q1062 terminal handoff are absent. No panel process or
measurement row was started. Restore and reconcile that external campaign
state before retrying the panel; do not bypass its guard.

### Pair-inverse joint-target core proposal — 2026-10-02

The complete fixed-orientation V20 pair inverse and its exact composition
bound sharpened this historical solver proposal. Blind target-independent residual
probes have a 600-second union bound below `3.62e-25` for one orientation;
the idealized all-orientations bound is below `4.75e-23`. They are not a
viable composition. The original
[joint-core proposal](v20_factored_sixleaf/PAIR_INVERSE_JOINT_CORE_DESIGN.md)
instead uses four factor-base leaves and the public target equations to
generate a normalized pair-output coordinate `c`, then calls the complete
local inverse only for that coordinate. Exact curve replay and
distinct-column checks remain mandatory. The subsequent
[structural audit](N41_N131_FREE_PAIR_CORE_STRUCTURE_RESULT.md) proved that
`c` can be set to the exact residual of **any** nonexceptional four leaves;
the core therefore does not prune leaf choices. It is parked. A replacement
must integrate pair realizability into target-dependent selection and clear
an N41 ordinary-row gate plus an N131 work/memory preflight before another
challenge-width query. `candidate_id`, `run_id`, and all costs remain null.

### V20 six-leaf ordinary N131 query — 2026-10-02

The V20 planted relation circuit passed complete CNF/XOR evaluation with
161,271 variables, 253,811 clauses, 75,346 XOR rows, 83,387 AND gates, and an
8,355,069-byte ordinary-target formula. A separate exact decoder control
replayed the planted sum over six distinct folded columns. The frozen ordinary
N131 point was then searched alone with one CryptoMiniSat worker, a 1,800
second limit, and a 4-GiB process RSS guard. The supervisor stopped it after
1,815.126 seconds at 586,907,648 bytes sampled RSS; stdout and stderr were
empty, with no model. Treat the attempt as censored, not UNSAT or zero yield.
The runner/result are in
[`v20_sixleaf_public_search/ordinary_attempt_1800s/`](v20_sixleaf_public_search/ordinary_attempt_1800s/)
and the full gate is documented in
[`N131_V20_SIXLEAF_RESULT.md`](N131_V20_SIXLEAF_RESULT.md). `candidate_id`
remains null; no factor logs, relation matrix, target scalar, or rho comparison
exists. The next algorithm attempt should use the already audited fixed-sum
pair inverse to replace whole-system Boolean search.

### Pair-inverse equation audit — 2026-10-02

The pair-inverse joint-core design now has a separate field-algebra check:
all 64 stored positive controls satisfy `q^2+q=(s+c)^2`, and all 64
mismatched-`s` controls have no accepted pair. See
[`pair_equation_design_audit.json`](v20_seed_pair_z_quadratic/pair_equation_design_audit.json).
This confirms the local equation used by the proposed core; it does not test
target-coupled search or curve-group recovery.

### V14 eight-leaf ordinary N131 query — 2026-10-02

An independent checked-Sage replay matched the exact 2,033 V14 trace-inverse
eta seeds, checked all 4,066 sign lifts for prime-subgroup membership, and
confirmed all 2,014 Frobenius orbits have length 131. This gives
`B=527,668` usable points before folding and `K=2,014` columns for the hashed
base set. The eight-distinct-column support mean is about 216 over all
subgroup targets, not a fixed-target yield estimate.

The seven-node eight-leaf `S3_z` formula has 159,566 variables, 308,182 CNF
clauses, 73,708 XOR rows, and 84,904 AND gates in 12,432,308 bytes. The
planted formula and exact decoder controls both pass. Its single ordinary
target search used one CryptoMiniSat worker with a 1,800-second / 4-GiB cap;
it was stopped at 1,815.130 seconds with 628,817,920 bytes sampled peak RSS
and no model/status line. Preserve this as censored, not UNSAT or zero yield.
The full [result note](N131_V14_EIGHTLEAF_RESULT.md) and run artifacts are
recorded. No natural relation, factor logs, matrix solve, target scalar, or
paired rho comparison exists. The current gate calls for a materially
different target-driven join or elimination that first returns an unpinned
N41 row. The latest method gate rules out repeating this full Boolean tree
or the already-censored SAT four-leaf core; complete the staged N83
ordinary-query and DLP prerequisites before another N131 relation search.

### Six-leaf Riemann–Roch norm screen — 2026-10-02

An exact global equation for six V20 abscissas and the target was derived
from a monic degree-seven curve function. It eliminates the S3 intermediate
coordinates and passed complete N41/N131 planted Boolean replay plus an
independent checked-Sage norm/determinant audit. Its N131 circuit is
15,921,549 bytes with 295,421 variables, about 1.91 times the bytes and
1.83 times the variables of the existing V20 S3 tree. The unpinned N41
public-target solver diagnostic reached its 120-second cap without a model,
despite the already verified row on that same point. This is censored search
evidence. The [result](SIXLEAF_RR_NORM_RESULT.md) parks the monolithic RR
encoding. The next method gate is unchanged: target-dependent pruning before
a three-leaf prefix is fixed, an unpinned N41 row, then a bounded N131
preflight before any new challenge-width query. No candidate ID, ordinary
N131 relation, scalar, or single-target IC/rho speedup exists.

An exact nine-seed N41 table then removed the trace-inverse witness gates and
passed a 0.120-second externally pinned control, but its unpinned search of
the same public point also hit the 120-second cap without a model. This
narrows the failure of the monolithic RR approach beyond its inverse gate;
the full receipt and size comparison are in the same result note.
The follow-up rank argument makes the limitation structural: on the
nonexceptional chart, any five distinct signed leaves whose partial sum is
not the target admit a unique monic RR witness through `-Q`. The target
relation first constrains the sixth leaf. All 256 frozen N41 five-leaf
prefixes had full interpolation rank, consistent with that exact divisor
argument. A subsequent solver should couple a realizable missing leaf or
pair to the target *during* earlier selection, rather than add another
existential global function witness.

### W16/S7 factored-S3 long single-target follow-up — 2026-10-02

The algebraically factored S3 circuit was run on the same frozen ordinary
N131 point with one CryptoMiniSat worker, a 20-million-conflict / 3,600-second
limit, and a monitored 4-GiB parent-plus-solver RSS cap. Its charged
target-dependent PDP interval was 3,662.771 seconds; the process guard stopped
it without a model or solver status line at a 1.55-GiB observed peak. The
attempt is `INDETERMINATE`, not UNSAT or zero yield. The detailed
[result and receipt](../koblitz-cofactor-fiber-20260928/N131_W16_S7_FACTORED_LONG_RESULT_20261002.md)
record the exact phase accounting and the separately censored first attempt.
No relation, scalar, candidate ID, or IC/rho speedup follows. This longer run
does not change the active gate: develop target-adaptive pair realizability,
prove pruning on N41, then preflight before any further challenge-width search.

## Staged N53-to-N83 continuation — 2026-10-03

The user approved the staged sequence: validate N53 generalization, reduce
cold-start cost, establish an N83 gate, then revisit the challenge. The N53
RCsample holdout panel has now completed eight independent one-target IC/rho
pairs. All eight scalar replays pass and all eight prepared-online IC times
beat rho; the median paired ratio is 82.2535x, with a target-bootstrap 95%
interval of 33.8727x–176.3844x. These CPU ratios remain exploratory because
the host has no isolation receipt. See the
[panel summary](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/panel_summary.json)
and [independent replay](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/validation/independent_sage_replay.json).

The cold-start audit found no one-shot win. The RCsample one-worker median is
8.632 s setup plus 4.517 ms online against 1.581 s paired rho; setup would
need to fall to about 1.576 s (5.48x below this run) to break even. The
14-worker setup is 3.366 s, also above rho. The complete accounting and
limitations are in the
[cold-start audit](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/COLD_START_AUDIT.md).
The frozen sharded-index follow-up targets the 821 ms serial root-table
insertion. Its five saved candidate runs, R1–R5, all failed with a Rust
capacity-overflow panic and have no valid IC timing. On the fresh 2026-10-04
preflight, the exact pinned Q1060→Q1062 N83 idle handoff was restored from its
verified sibling snapshot and passed. Preflight then stopped because the
current Rust source and executable hashes differ from the frozen candidate;
no new candidate or rho process was launched. The system volume now has about
1.30 GiB free, below the candidate's 4 GiB guard. The next cold-start attempt
needs the frozen artifacts or a newly frozen implementation after fixing the
panic, plus disk space above the guard. See the
[sharded-index README](../koblitz-n53-targetspan-sharded-index-20261003/README.md).

The N83 scaling gate now has exact ONB-to-polynomial-basis bridges and a
bounded native four-point S3-root stage. Checked Sage replays passed for both
bridges and all 227 / 186,612 factor-base representatives; check-only
validation of both bridge receipts, both native-input exports, and the native
stage receipts passed through the checked repository launcher. The mapping
preserves each curve ID and has no isogeny. The native path uses `Gf2_128` for
degrees above 64; it is not limited to the `u64` `Gf2` implementation.

Q1327 reused the exact Q1301 N53 base (B=24,062, K=227) and frozen ordinary
target. Its complete 2,731,037-state index found one unpinned four-point
relation. Independent checked-Sage replay verified all four exact-base
subgroup points, their sum to the public target, and a nonzero relation row;
paired with the existing matched pair-table row, rank is 2. Index build was
2.779 s, target-dependent search and native relation check 0.106 s, and peak
RSS 285 MB. These are exploratory stage timings on an unisolated host, not a
complete DLP or an IC/rho speedup. Q1327 retains `candidate_id: null` and
`run_id: null`.

Q1328 reused the exact Q1325 N83 base (B=30,977,592, K=186,612) and its frozen
ordinary target. It sampled 2,000,000 states from a total of 2,890,395,199,152
(about 6.92e-7), found no relation, and reached its cap. The checked-Sage
receipt validates the native generator/target S3 control and the capped run;
the no-hit is censored and does not imply that the target has no decomposition.
Index build was 4.565 s (4.849 s including 0.284 s setup), target search
9.355 s, and peak RSS 755 MB, again exploratory. Q1328 also has no candidate
or run ID.

Q1329 extends the native target query to test all 83 Frobenius orientations
per state. It used the same Q1325 base and two-million-state sample to solve a
known-satisfiable planted target built from the first two sampled states. The
solver did not receive the witness or those state positions. It found a
four-point decomposition after one state and 34 orientations. An independent
checked-Sage replay verifies the four exact-base subgroup points and their sum
to the planted target. This is a correctness control, not a natural-yield or
online-speed measurement; setup plus index was 4.959 s and peak RSS 691 MB on
an unisolated host. Q1329 also has no candidate or run ID. See the
[N83 stage audit](../koblitz-n83-index-design-20260929/N83_COMPACT_S3_STAGE_AUDIT_20261003.md)
and [Q1329 replay receipt](../koblitz-n83-index-design-20260929/Q1329_PLANTED_SAGE_REPLAY_20261004.json).

Q1330/Q1331 changed only the S3 root kernel to Montgomery batch inversion
over 4,096-state blocks. On matched inputs, N53 index/target times changed
from 2.779/0.106 s to 1.281/0.052 s and the same ordinary relation replayed.
On N83, index/target times changed from 4.565/9.355 s to 1.509/3.251 s, but
the same 2,000,000-state, one-orientation ordinary query still found no
relation. Checked-Sage replay receipts pass for both batch rows. These single
run timings are exploratory, not controlled CPU speedups.

Q1332 is the all-83-orientation batch planted control on the exact Q1325 N83
base. It found the unpinned four-point relation at state 1, orientation 34,
while preparing 4,096 states and 339,968 orientations; independent checked
Sage replay passes. It proves the batched orientation path on a known
satisfiable target and says nothing about ordinary-target yield.

For the N83 bases, exact uniform-target four-point means are 0.241 (Q1302),
4.412 (Q1324), and 15,869.003 (Q1325). They are combinatorial averages, not
fixed-target relation-yield measurements. A full Q1325 quotient pair search
has `K^2*n = 2,890,395,199,152` states (`2^41.394`). A separate packed
point-pair design estimate is 40–64 bytes/state, or about 105–168 TiB; this
is not the measured allocation or layout of Q1327/Q1328's S3-root hash table.
The subgroup rho square-root floor is `2^40.5` group steps, before query,
matrix, and recovery costs. A native implementation or streaming storage
alone is not a breakthrough; the N83 method still needs target-dependent
pruning or a join that lowers charged work. Detailed arithmetic and the
separate memory estimates are in the
[N83 compact-S3 stage audit](../koblitz-n83-index-design-20260929/N83_COMPACT_S3_STAGE_AUDIT_20261003.md).

The next proposed query is one ordinary N83 target on the exact Q1325 base
and Q1328 target, using Q1331's 2,000,000-state coprime-stride sample and
Q1332's all-83-orientation batch query. Q1331 measured 3.251 s for one
orientation per state, so linear scaling estimates about 270 s for 83
orientations; freeze a 600 s target-stage cap, 1,024 MiB peak-RSS cap,
source/binary and input hashes, orientation order, and operation accounting
before launch. This estimate is planning only. If the query returns a
relation, independently replay all four points and their sum. A no-hit stays
censored. Run a natural-target panel only after this same-target gate.

The cryptanalysis tree fails the Crypto Autoresearcher preflight because it
does not contain orchestration/roles.yaml, tools/research_dispatch.py,
tools/generate_runtime_agents.py, tools/check_runtime_bindings.py,
.codex/config.toml, or .codex/agents. The other available ECDLP campaign
checkout has a generic prime-field objective, so it does not authorize this
binary-field query. No all-orientation ordinary N83 query has been launched.
Clear the matching campaign dispatcher/runtime gate, then freeze and dispatch
this exact one-target stage. The N83 proposal-stage results still have null
candidate and run IDs. None supplies factor-base logs, a final matrix solve,
target descent, a DLP scalar, or an IC/rho comparison. Keep the ECC2K-130
challenge gate closed until the full measured cost is credibly below the
paired rho cost and the recovered scalar passes independent replay.

**N83 compact-S3 scaling update (2026-10-04; supersedes the preceding
unlaunched-query status):** the adaptive planted four-point control passed an
independent checked-Sage replay. A frozen single-target ordinary query then
tested 2,000,000 index states against the same Q1325 public target with all 83
target Frobenius orientations. It completed with no relation after
166,000,000 orientation checks, 245.251 s of target-stage work, 1.514 s of
index construction, and 810,369,024 bytes peak native RSS. The no-hit is
censored at the sample cap; it does not prove the point has no decomposition.
This stage has no factor logs, matrix solve, scalar, rho pair, or CPU-isolation
receipt. See the
[stage record](../koblitz-n83-index-design-20260929/adaptive_all_orientations_20261004/README.md)
and [updated N83 audit](../koblitz-n83-index-design-20260929/N83_COMPACT_S3_STAGE_AUDIT_20261003.md).

The 130-bit challenge gate remains closed. The next N83 step is target-
conditioned pruning or algebraic elimination that reduces charged work and
storage, followed by ordinary-target testing and a complete path through
factor logs, final matrix solving, target descent, and independent scalar
replay. Q1333 is already assigned to the N131 W2 quotient gate, so the N83
adaptive stage deliberately has null proposal, candidate, and run IDs.

## Approved staged continuation update — 2026-10-04

The approved order is N53 generalization, N53 cold-start reduction, an N83
scaling gate, and only then another ECC2K-130 challenge attempt.

**N53 online generalization is complete.** The eight-target
[`RCsample` panel](../koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix/README.md)
uses candidate
`IC1N53Ckb1fb25864PDP4rootRCsampleLAgaussTDdirectISO0hc12e132cec54`, the same
candidate ID as the five repeated-target measurements whose median paired
online ratio was 356.9×. Each independently selected target has its own
one-target IC row paired to one rho solve. All eight recovered scalars passed
independent checked-Sage replay; the median paired online ratio was 82.2535×
(target-bootstrap 95% interval 33.8727×–176.3844×). Thus the prepared online
advantage generalizes on this N53 candidate, while 356.9× is not a
representative magnitude. Reusable setup remains separate, and these
unisolated-host wall ratios are exploratory rather than a controlled CPU
speedup claim.

**N53 cold-start reduction has a one-target result, with generalization still
open.** The sharded-index candidate
`IC1N53Ckb1fb25864PDP4rootRCguidedLAgaussTDdirectISO0h7d28b4e6557e` completed
five independent scalar replays on one frozen target. Median reusable setup
was 137.073 ms, prepared-online time 771.852 ms, and fully charged
post-launch cold phase 910.070 ms. The paired one-worker rho median was
1,580.830 ms, giving a 1.743× cold-phase ratio on this target. The measured
candidate used 14 workers for index and relation collection while rho used
one; the host has no qualifying isolation receipt, and IC operation counts
are unavailable. These rows are exploratory and do not establish an
algorithmic or controlled CPU speedup. The five repetitions also do not
estimate cold performance over independent targets. See the
[`R2 sharded-index result`](../koblitz-n53-targetspan-sharded-index-20261004-r2/README.md),
[verified rows](../koblitz-n53-targetspan-sharded-index-20261004-r2/measurement_rows_verified.jsonl),
and [paired summary](../koblitz-n53-targetspan-sharded-index-20261004-r2/paired_summary.json).

**N83 remains the scaling gate.** The exact 83-bit path uses unsigned 128-bit
field keys; the design audit records memory estimates for the existing N83
bases, and the planted Q1335 decomposition passes independent checked-Sage
replay. The subsequent ordinary-target attempt tested all 83 orientations for
2,000,000 of 2,890,395,199,152 pair states and found no relation. This is a
censored sample, not evidence that the target has no decomposition. The next
method must change the target-conditioned search or algebraic elimination and
reduce charged work as well as storage; extending the same all-pairs sample is
not a supported next step. A planted positive control and an unpinned
small-field ordinary-row control must pass before a new N83 ordinary run. A
complete N83 gate still requires unknown factor-base logs, final sparse
linear algebra, an independently replayed target scalar, and a paired
one-target rho solve.

**The already-running official N131 R2 setup query is still active.** A
creation-time-verified sample at 10:17:40 UTC confirmed the direct parent and
CryptoMiniSat on `precomputation/attempt_001/query.xcnf`. The solver log kept
advancing and reached restart 9719 at 10:22:48 UTC; no terminal result or
failure record exists. The latest rank observation remains 0/14 from 09:51
UTC and is stale. The latest resource point sample, at 10:18:49 UTC, measured
1,548,845,056 combined parent-plus-solver RSS bytes under the 4-GiB cap. It is
a point sample, not a peak, and uses psutil rather than the earlier macOS
libproc method. See the [10:17 process/resource
receipt](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T101740Z_psutil.json)
and [10:18 resource
receipt](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T101849Z_psutil.json).
This is target-independent factor-log setup; the published Q online interval
has not started. A separate single-target n=73 diagnostic in the sibling
`/Volumes/SSD990/crypto` checkout is also active on this host: its rho arm
finished before its IC arm began, and its IC is still in setup with no result
row. The two jobs share the host, so neither run supports a controlled CPU
speedup claim without an isolation receipt.

No new N83 solver run was dispatched in this update. The available checkout
still fails the Crypto Autoresearcher preflight because the dispatcher,
runtime bindings, and agent configuration are absent, so the exact campaign
checkout requested earlier is still needed before dispatching another
experiment. The N83 method design and resource analysis can continue offline;
the challenge gate stays closed until the full N83 relation-to-scalar path
passes its correctness and paired-cost gates.

**N131 R2 live recheck (2026-10-04 10:18 UTC):** the same verified solver
and direct parent remain live on the first target-independent
`attempt_001/query.xcnf`; the log has advanced to restart 9715. A psutil point
sample measured 1,548,845,056 combined RSS bytes, with 2,746,122,240 bytes
below the 4-GiB cap. The last saved rank is still 0/14 from 09:51 UTC and is
stale, so current rank is unknown. No terminal run record exists, and the
published-target online interval has not begun. The [10:18 resource
observation](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T101849Z_psutil.json)
and [progress observation](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_progress_observation_20261004T101849Z.json)
retain the live commands, counters, and stale-rank qualification.

**N131 R2 live recheck (2026-10-04 10:37 UTC):** the creation-time-verified
solver and parent remain live on the first target-independent setup query.
CryptoMiniSat has advanced to restart 10,549. The latest psutil point sample
records 1,499,381,760 combined RSS bytes under the 4-GiB cap; it is not a
peak. Rank is still unknown: the last recorded rank observation was 0/14 at
09:51 UTC, and `precompute_progress.json` itself has not refreshed since
05:58 UTC. No terminal relation or failure record exists, and the published-Q
online interval has not begun. See the
[10:37 process/resource observation](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T103734Z_psutil.json).

**N131 R2 live recheck (2026-10-04 11:10 UTC):** the same creation-time-
verified parent and solver remain on the first target-independent setup
query. CryptoMiniSat has advanced to restart 10,653. A fresh psutil point
sample records 1,592,557,568 combined RSS bytes, leaving 2,702,409,728 bytes
under the 4-GiB cap; this is a point sample, not a peak. The recorded rank is
still stale at 0/14, no verified setup relation or terminal record exists,
and the single published-Q online interval has not begun. The
[11:10 process/resource observation](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_resource_observation_20261004T111047Z_psutil.json)
preserves the exact PIDs, command lines, creation times, counters, and cap.

The sibling `/Volumes/SSD990/crypto` checkout's current n=73 diagnostic is
also one target: its one-target rho arm completed, and its paired IC arm is
still computing that same frozen point. At 11:09 UTC the IC process had run
4,994 seconds, used one running thread, and had a 5,093,097,472-byte RSS point
sample, with no finite memory cap. This and N131 share an unisolated host;
neither supports a controlled wall-time ratio. No multi-target or batch job
was started.

**Q1355 N41 persistent-SAT gate (2026-10-04 11:48 UTC):** the corrected
full-input planted control pins all eight factor-base leaves and all six S3
prefix intermediates; CryptoMiniSat returned SAT and the producer replayed
the lifted two-column row in 31.089 ms. The frozen formula has 71,951
variables, 92,911 clauses, and 42,418 XORs. All four target-independent
known-scalar factor-log queries reached their 60 s caps after three 20 s
`UNDEF` calls each, with zero models and rank 0/2 after 240.781 s total query
time. Sampled combined RSS peaked at 445,513,728 bytes, below the 4-GiB cap.
Because logs were unavailable, Q1355 withheld its single frozen public
target: both online costs remain null, no target-online timer started, and no
speedup was measured. The accounting audit passes, but `progress.json` stayed
at `RUNNING_SETUP` after the terminal `SETUP_INCOMPLETE` result; the result
and supervisor receipts are the terminal records. See the
[Q1355 result](N41_INCREMENTAL_SAT_Q1355_RESULT.md),
[protocol](n41_incremental_sat_gate_q1355/protocol.json),
[producer result](n41_incremental_sat_gate_q1355/run_r1/result.json),
[supervisor](n41_incremental_sat_gate_q1355/run_r1/supervisor.json), and
[accounting audit](n41_incremental_sat_gate_q1355/run_r1/accounting_audit.json).

**N131 W2 quadratic x-only boundary (2026-10-04):** the Frobenius-rotated
pair-output screen reached rank 8,516 of 8,647 Boolean degree-at-most-two
features; the 131 null vectors were exactly `x_i * Tr(x)`. A held-out set of
100,000 outputs had no violations, and a complete scan of 20,129,592 index
records found no odd-parity key. Together with the existing trace-zero
subgroup proof, this rules out any additional x-only quadratic equation for
this exact pair-output domain. It does not rule out mixed seed/output,
y-coordinate, higher-degree, or target-coupled constraints. This screen has
no relation, factor logs, target scalar, or speedup result. See the
[complete result](N131_W2_PAIR_QUADRATIC_COMPLETE_RESULT.md) and its
[frozen rank protocol](n131_w2_pair_quadratic_orbit_q20261004114501/protocol.json).

**N131 R2 solver-log observation (2026-10-04 11:57 UTC):** the first
target-independent known-scalar setup query's log had advanced through CMS
restart 11,130. The saved progress record is older than the log and still
reports rank 0/14, so the current rank remains unknown. There is still no
terminal result or published-target online interval. This receipt records
log progress only; it does not reverify process identity or current RSS:
[11:57 log observation](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_log_observation_20261004T1157Z.json).

**Same-point N41 target-search gate (2026-10-04):** Q20261004120001
transferred Q1330's independently verified factor logs into Q1355's exact
eight-leaf SAT formula, allowing its previously withheld public point to
be queried without SAT factor-log setup. Six solver calls returned `UNDEF`
over 120.162 target-dependent seconds, with no model. Q20261004120901 then
searched the **same point** through the exact indexed `4+1+3` continuation:
an eight-point row and scalar `308783488310` were independently replayed
after 10,077 prefixes and 48.130 target-dependent seconds. The
[paired method result](N41_W2_SAME_TARGET_SEARCH_RESULT.md) proves this SAT
timeout was search failure on a satisfiable point. The indexed table's
21.488-second build was outside target time; its literal N131 transfer
exceeds the resource gate and eight-leaf N131 support is tiny. The next
method must provide compact target-dependent continuation for a longer
challenge-width relation, rather than merely reuse this SAT formula.

**N131 R2 live process observation (2026-10-04 12:19 UTC):** the verified
one-worker CryptoMiniSat process remains on the first target-independent
known-scalar factor-log query. Its log advanced to restart 11,141. The direct
parent-plus-solver RSS point sample was 1,488,306,176 bytes under the 4-GiB
cap; this is not a peak. The saved setup rank remains stale at 0/14, no
terminal result exists, and the published single target's online interval has
not started. See the [process and log receipt](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_process_observation_20261004T121919Z.json).

**N41 SAT follow-up controls (2026-10-04):** the
[result note](N41_S3_RATIONALITY_AND_PREFIX_CONTROLS_RESULT.md) records
three frozen proposal gates on Q20261004120901's independently verified
ordinary eight-point row. An inverse-and-trace circuit for six intermediate
x values accepted the row in 0.0385 s only when the six inverse witnesses
were also pinned; with those witnesses free it returned `UNDEF` at 30.304 s.
On the original formula, pinning the first four, five, or six row leaves and
their exact prefix sums still returned `UNDEF` at each 30-second cap. Every
finite S3 intermediate of subgroup leaves is already a subgroup-point x
coordinate, so both trace conditions are logically redundant. **The next
goal is a target-coupled search primitive with compact exact pair-output
realizability, rather than more trace gates or a free SAT suffix.** It must
first produce an unpinned ordinary row under a frozen smaller-field gate and
pass a source-bound N131 one-worker 600-second/4-GiB preflight; then seek
one fresh ordinary N131 relation with independent checked-Sage replay.
The active single-target online IC/rho objective remains downstream of that
relation and verified factor logs.

**One-hot W2 leaf gate (2026-10-04):** Q20261004124101 changed the exact
N41 eight-leaf SAT formula to select each leaf from the 82 usable x masks
with one-hot variables. The [result](N41_W2_ONEHOT_BASE_RESULT.md) records a
passed known-row model/group control, 3,912 fewer CNF clauses, and a
120.268-second unpinned public query with six `UNDEF` calls and zero models.
The public run stayed under the frozen 4-GiB RSS guard; the control
supervisor's process-list permission failure is retained separately.
This leaf-variable reformulation does not clear the ordinary-row gate.
The frozen six-leaf prefix follow-up also returned `UNDEF` at 30.311 s.
Do not advance it to N131 on formula size alone; the next implementation
must obtain target-dependent pruning of pair realizability or a different
joint algebraic elimination method.

**One-target accounting calibration (2026-10-04):** Q20261004123001 paired
the successful N41 indexed IC query and a single-worker rho solve on the same
public point. Both independently replayed scalar `308783488310`. IC online
time was 48.130 s and rho online time 4.257 s (`rho/IC = 0.08845`); this
unisolated toy-field observation is unfavorable to IC and is not an ECC2K-130
speedup claim. It confirms that subsequent IC and rho comparisons use exactly
one target and exclude target-independent IC setup. The controlled goal
remains open pending a verified N131 IC solve and isolated same-point rho
comparison. See the [paired result](N41_SINGLE_TARGET_IC_RHO_PAIR_RESULT.md).

**N131 R2 live recheck (2026-10-04 12:48 UTC):** the same one-worker setup
query remains active. Process identity and the exact solver input match the
prior verified receipt; CryptoMiniSat advanced from restart 11,141 to 11,230.
The current parent-plus-solver RSS point sample is 1,681,375,232 bytes under
the 4-GiB cap. The saved rank record is stale at 0/14, so current rank remains
unknown; no target-dependent online interval has begun. The
[12:48 process/log observation](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/live_process_observation_20261004T124852Z_psutil.json)
records process identities, command lines, point-sampled resources, and the
updated solver-log hash.

**One-target PDP arithmetic optimization (2026-10-04):** Q20261004125320
replayed the same N41 target and same 10,077-prefix/1,571,858-probe path as
Q20261004120901. Reusing one field inverse across the two signs of each
suffix x reduced the query from 48.130 s to 37.879 s online, a 1.271×
same-point method improvement; both runs independently recovered the same
scalar. The inverse-call count fell by about 156×, but total wall time fell
only 21.3%, and optimized IC remains about 8.90× slower than the 4.257-second
same-point rho reference. This is unisolated N41 evidence, not a dramatic
challenge-width gain. The [result and replay](N41_SHARED_DENOMINATOR_RESULT.md)
retain one target, with the 21.497-second reusable triple-table build outside
the online clock.

**One-target x-only/sparse-operand follow-up (2026-10-04):** Q20261004130506
computed suffix x values only and performed full group additions only on an
exact index hit; it recovered the same scalar in 26.053 s. Q20261004131203
then used the existing ONB sparse-right-multiplication path for the W2 x
coordinates and reduced that same-point online time to 23.073 s. Against the
original indexed query this is 2.086× faster, but still 5.42× slower than the
same-point rho reference. The target count is one in every arm; these
unisolated N41 kernel diagnostics do not constitute an ECC2K-130 speedup. See
the [sparse-operand result](N41_SPARSE_OPERAND_RESULT.md).

**N131 W2 four-output join preflight (2026-10-04):** the
[source-bound result](N131_W2_FOUR_OUTPUT_JOIN_RESULT.md) closes a direct
`2+2` group table over the exact 5,223,254,008-point Q1343 indexed
macro-output domain:
even a packed x-plus-sign record needs 402.283 EiB for all ordered pair
sums. Fixed equal sublists large enough for an ordered mean of one need
97.79% of the domain; the 4-GiB table limit shrinks their uniform-target
support upper bound to `9.377×10^-23`. Since the odd-order subgroup has
no nontrivial binary additive projection, x-coordinate XOR prefixes are
not a valid Wagner-style group bucket. The independent arithmetic audit
passes. This is not a lower bound on target-coupled algebraic search or a
result on the fixed published target. It reinforces the next constructive
gate: restrict exact pair realizability *using* target equations before
materializing group-pair combinations, or choose a different base/arity
with an equally explicit resource preflight.

**N131 W2 unordered support correction (2026-10-04):** the
[independently audited screen](N131_W2_UNORDERED_ARITY_RESULT.md) counts
commutative multisets of the complete Q1343 indexed macro-output set. It improves
the previous four-output ordered-tuple bound from trivial to a **4.5571%
uniform-target support upper bound**. Five outputs have a large multiset
mean, but coverage and solve cost are unmeasured. A four-output method
must either charge randomized target-dependent queries (at least 11 even
for its union-bound ceiling to reach 50% success), or accept a thin
one-shot input law; Frobenius rotations of the same target cannot create
new support. Candidate selection should therefore compare a complete
charged four-output randomized descent with a target-coupled five-output
solver or a different factor base. This screen does not answer whether
the fixed published point lies in either sumset. These bounds are for the
restricted indexed macro family, not arbitrary W2 four-leaf sums or the
official m15 SAT system.

**Alternative N131 four-summand gate (2026-10-04):** the exact W27 projected
base on its own field representation has `B=17,582,648,390` actual points
and `K=67,109,345` folded columns. The independently audited
[Q20261004132901 arity screen](N131_W27_FOUR_SUMMAND_GOAL.md) counts
`2^m C(B/2,m)` distinct-x signed rows: three summands give only
`1.3312×10^-9` rows per uniform subgroup target, while four give
`5.8514` and five give `2.0576×10^10`. The four-summand mean makes it a
concrete alternative to another blind W2/m15 or W27/m5 solver trial, but
it provides no coverage guarantee or fixed-point relation. The next gate
is to use the newly frozen published-generator polynomial-basis curve ID
`EC1N131Ckb1h8c8abf234d60` (the checked official bridge validates G and Q),
then run an unpinned
four-summand search within one worker/600 seconds/4 GiB with independent
checked-Sage replay of any ordinary row. Only after that should the
67-million-column log/rank cost be assessed. Complete IC candidate/run IDs,
target recovery, and isolated same-point IC/rho timing remain open.

**W27 four-summand method correction and D16 gate (2026-10-04):** the
`5.8514` uniform-target mean above counts the *unrestricted* four-point
W27 base. The initial adjacent-pair circuit permits just one relative
Frobenius offset per pair and has a rigorous uniform-target support ceiling
of `0.00409262`. Its official-Q run returned `INDETERMINATE` without a
model after 269.551 seconds. A broader circuit with 16 frozen relative
offsets per pair has a trivial counting ceiling and a 19.1 MB planted
XCNF; its pinned CryptoMiniSat model and full independent checked-Sage
replay pass. See the [corrected method gate](N131_W27_FOUR_SUMMAND_GOAL.md).
The D16 public-only query returned `INDETERMINATE` without a model after
599.417 seconds, at 1.065 GB sampled combined peak RSS. This is a censored
row, not a support or UNSAT proof. The separate unpinned planted-target
search also returned `INDETERMINATE` without a model after 116.158 seconds,
although that same D16 target has a fully replayed pinned SAT witness. The
runner read only its public Q, not the validation sidecar. The next method
goal is a target-conditioned pair-realizability propagator that finds this
known satisfiable row while all four leaves and both relative offsets
remain free, before another published-point query. Measure where it rejects
partial states and keep the same resource/accounting rules.

**Four-summand factor-log feasibility correction (2026-10-04):** the
[exact column-floor screen](N131_ARITY_COLUMN_FLOOR_RESULT.md) shows that,
under distinct-`x` four-point counting and sign/Frobenius folding, even a
base whose row count first reaches the subgroup order needs at least
43,148,816 folded columns. Exact W27 has 67,109,345. A single W27 row is
therefore a stage milestone, not by itself a credible full-pipeline IC
candidate. The W18 four-pair/eight-summand policy has 131,068 columns, but
still lacks a scalable unpinned solver. The one-target DLP and matched-rho
objective remains unchanged.

**Target-coupled quadratic-filter gate (2026-10-04):** the
[N41 exact rank result](N41_TARGET_PAIR_QUADRATIC_RANK_RESULT.md) and
[N131 W18 checked-Sage transfer](N131_W18_TARGET_PAIR_QUADRATIC_RANK_RESULT.md)
close one proposed shortcut. On the exact N131 four-pair geometry, 10,795
independent valid planted rows span all target-`x,y` linear and
first-pair/target bilinear features left after 126 equations of the
restricted source-mask sample and 39 multiples of the known subgroup
trace equation. Both group and rank replays pass. Hence no additional
**universal** target-dependent equation exists in that declared
mixed-quadratic family. This does not rule out target-specific higher-degree
or intermediate-pair constraints. The next constructive gate is still an
index-free, unpinned N41 ordinary eight-slot row with independent replay,
then an exact bounded N131 planted preflight and one fresh ordinary N131
relation; planted rank controls are not ordinary yield or speedups.

**Partial pair-output propagation gate (2026-10-04):** the exact N131 W18
[prefix relaxation](N131_W18_PARTIAL_OUTPUT_LINEAR_GATE_RESULT.md) is sound
and independently checked in Sage. With 24 low coordinate bits still free,
it passed all eight planted raw pair outputs and rejected all 64 balanced
field-coordinate controls; with 36 bits free it rejected none. It is
therefore a late pair-output filter, not the missing target-coupled output
generator. The next method goal is a joint pair/target eliminator that
retains the bilinear unknown-output/product coupling and demonstrates
pruning before near-complete outputs on an unpinned N41 ordinary row. A
frozen N131 memory/work bound, exact planted replay, and fresh ordinary
relation are required before any full-pipeline or speedup claim.

**Seed-sum-conditioned pair propagation (2026-10-04):** the stronger
[exact-field gate](N131_W18_SEED_SUM_PREFIX_GATE_RESULT.md) fixes only the
XOR of a pair's W18 masks and uses `w1*w2=w1²+s*w1`. Eight full-width real
pairs passed at every tested prefix depth. With 36 low output bits free,
the gate rejected all 64 balanced field coordinates under each of eight
distinct seed sums; the unconditioned gate accepted all 64 coordinates.
Independent checked Sage replayed the raw pairs and all 4,680 systems.
The [N41 occupancy control](N41_W6_PAIR_PREFIX_OCCUPANCY_RESULT.md) shows
why the output-only relaxation was too loose. These are local constraints:
no public-target solver yet supplies the seed sum and long output prefix.
The next gate is a target-coupled blockwise search using them before both
pair leaves are fixed, followed by the unchanged unpinned N41, bounded
planted N131, fresh ordinary N131, complete DLP, and paired-rho gates.

**Exact known-sum pair eliminant and inverse (2026-10-04):** the
[N131 additive-polynomial result](N131_W18_SUBSPACE_POLYNOMIAL_RESULT.md)
eliminates one W18 leaf from the local pair equation once its sum is fixed.
An independent checked-Sage replay passed 32 full-width raw positive sums,
all 1,088 positive/control parity decisions, and image-rank checks; none
of 512 fixed control coordinates passed either parity. The
[cached inverse](N131_W18_KNOWN_SUM_INVERSE_RESULT.md) recovers both leaf
masks from a proposed output and fixed sum using a reusable rank-17 binary
map; a separate Sage matrix/group audit passed. Its Python binary-solve
kernel was much cheaper than rebuilding the map on every query, but that
exploratory local timing excludes output generation, inversion, and all
target search. The [N41 fixed-sum circuit preflight](N41_W6_SUBSPACE_CIRCUIT_PREFLIGHT_RESULT.md)
found 8,405 AND gates per eliminated pair versus 240–360 for the direct
one-leaf equation. A full bit-blasted eliminant is therefore not promoted
from this size evidence. The constructive route is a target-coupled search
that exposes useful seed-sum/output prefixes early and calls the conditioned
gate or cached inverse as a theory check; it must first return an unpinned,
independently replayed ordinary N41 row, then pass the frozen N131 resource
and ordinary-row gates. No fresh N131 relation, factor logs, target scalar,
or paired IC/rho online speedup has been measured.

**Exact early known-sum prefix domain (2026-10-04):** the
[N131 W18 fixed-sum result](N131_W18_EXACT_PREFIX_DOMAIN_RESULT.md) exhausts
one fixture sum mask `54209` with native field arithmetic and an independent
full checked-Sage replay. It finds 32,905 rational unordered source pairs,
131,620 distinct nonexceptional raw outputs, and only 65,667 occupied
24-bit high prefixes out of `2^24`; all four fixture positives pass while
0/64 fixed controls pass. Native local preparation took 0.256 s and this
sum's domain 0.136 s, with 10.2 MB reported peak RSS. These are exploratory
stage costs; the host rejected hard address-space limiting, and no
target-coupled search or controlled speedup is claimed. The exact gate can
reject after 24 output bits **once the seed sum is known**, far earlier than
the 91–103 fixed bits needed by the tested affine relaxation. The immediate
algorithm task is now concrete: make the public target constrain `(sum,
output-prefix)` states early enough that on-demand exact domains fit the
frozen one-worker 600-second/4-GiB query envelope. Require an unpinned,
independently checked ordinary N41 row before the N131 planted and fresh
ordinary gates. The complete DLP and paired-rho objective remains open.

**Target-coupled degree-two rank check (2026-10-04):** the
[N41 sum/output-prefix result](N41_SUM_OUTPUT_TARGET_RANK_RESULT.md) fixes
the first pair's seed sum and progressively more of its exact raw output
in the selected public-target quadratic S3 system. All five known
branch-0 extending states stayed consistent, but **none of 32 locally
valid nonextending states was rejected**, even when the entire 41-bit
first-pair output was fixed. This closes only the tested degree-two
linearization on the frozen controls. It explains why the fast exact N131
known-sum prefix domain cannot simply be coupled to Q by a cheap rank
check: local exclusion is strong, while target selection still needs
nonlinear cross-pair constraints or a search that preserves products.
The immediate constructive gate remains an unpinned, independently replayed
ordinary N41 row from such a method, then a bounded planted and fresh
ordinary N131 relation query, followed by full logs, target DLP, and
paired one-target rho measurement.

**Native W18 pair-inversion diagnostic (2026-10-04):** a one-target,
same-coordinate comparison exercised the exact division-free pair oracle
through the existing Python implementation and a new native C++ path. The
target-dependent call was 9.281 ms in Python and 0.264 ms in C++ (35.12×),
with context construction, native half-trace setup, compiler, process launch,
and Sage replay accounted separately. The recovered masks and raw/projected
group equations passed an independent checked-Sage replay. This is one
ordinary-host stage sample, not an isolated speedup claim; more importantly,
it does not address the sparse-image barrier or recover an eight-point row.
The table-free, target-coupled W18/N41 solver gate and the single-target
ECC2K-130 IC/rho objective remain open. See the
[full local-stage receipt](n131_w18_native_pair_oracle/RESULT.md).

**Exact-prefix SAT theory-proxy gate (2026-10-04):** the
[N41 W6 four-pair proxy](N41_W6_EXACT_PREFIX_THEORY_PROXY_RESULT.md)
added exact `(six-bit seed-sum, top-16 pair-output)` domains to the full
seven-link public-target S3 circuit. An ordinary known-row assignment
passed every emitted clause and independent checked Sage replayed all
256 source points, 8,064 unordered pair cases, four domain digests, and
the row. The unpinned solver nevertheless hit its 120-second parent cap
without a model; sampled combined RSS peaked at 109,428,736 bytes. The
failure is in target-coupled search, not missing N41 support. Do not scale
this static selector-table encoding to N131. The next constructive goal is
a target-conditioned cross-pair propagator that rejects nonextending
partial states before all four pair outputs are fixed and obtains an
unpinned, independently replayed ordinary N41 row within 120 s/4 GiB.
Only then freeze an on-demand N131 W18 preflight and seek one fresh
ordinary N131 relation within 600 s/4 GiB. Full logs, a target scalar,
and paired isolated one-target IC/rho timing remain open.

**Degree-four first-pair rank gate (2026-10-04):** the next-leaf Boolean
Macaulay lift multiplied the exact N41 public-target equations by `1`, all
six next-leaf mask bits, and all 15 bit-pairs, producing 10,956 lifted
equations. Its 227,048 first-pair-independent columns have rank 9,086,
exactly the maximum allowed by 1,870 lifted copies of the 85 independently
checked source syzygies. An independent integer-bitset audit reproduced the
rank and syzygies, so every one of the 4,096 first-pair mask assignments is
consistent in this degree-at-most-four relaxation. The job completed in
9.70 seconds at 1.32 GB sampled peak RSS under its 120-second/4-GiB cap; the
independent audit used 0.50 GB. This closes only that stated multiplier
family, not the exact Boolean system or target. The next algebraic gate must
couple two later leaf masks with cross-pair products, or use a target-focused
nonlinear solver with exact pair-domain checks. There is still no ordinary
N131 relation, candidate/run ID, factor-log solution, recovered target
scalar, or verified single-target IC-over-rho speedup.

**Full pair-domain SAT discriminator (2026-10-04):** the
[N41 W6 exact-domain result](N41_W6_FULL_PAIR_DOMAIN_RESULT.md) replaced
all four leaf S3 equations with 978 exact `(low_mask, high_mask, full
output-u)` choices per same-rotation pair, while retaining the three
cross-pair S3 links and all column/target checks. A known ordinary public
row passed the full formula; independent checked Sage re-enumerated all
8,064 unordered pair cases, matched every domain digest, and replayed the
row. The unpinned one-worker public-target search again hit its 120-second
wall cap without a model, at 220,528,640 bytes sampled combined peak RSS.
The full-output domain reduces arithmetic relative to the top-16 prefix
proxy but does not clear target-conditioned selection. Stop extending
this static-table SAT family without a new cross-pair propagation result.
The constructive gate is now a native target-driven join or elimination
that chooses cross-pair states under the same N41 cap and has an explicit
on-demand N131 W18 work/memory bound, followed by the unchanged planted
and fresh ordinary N131 relation gates. There is still no N131 relation,
factor logs, target scalar, or paired isolated IC/rho online result.

**Degree-four cross-pair rank gate (2026-10-04):** the next lift added all
36 Boolean cross-products between the next two six-bit leaf masks to the
constant and 24 single-bit multipliers. The dense projection preflight
estimated 7.17 GiB and correctly refused that allocation. A sparse GF(2)
matrix completed the one-target N41 rank in 34.4 seconds at 1.28 GB sampled
peak RSS; a separately reconstructed integer-bitset elimination reproduced
the rank in 50.3 seconds at 2.02 GB. Across 30,378 rows and 628,845
invariant columns (5,829,910 nonzeros), both ranks equal the exact 25,193
upper bound from 5,185 lifted source syzygies. Thus all 4,096 first-pair
assignments remain consistent even after these inter-pair degree-four
products. The [protocol and independently audited sparse rank](n41_w6_s8_quadratic_joint/degree4_cross_pair_lift/sparse_rank_protocol.md)
close this multiplier family only. Further blind Macaulay degree growth is
not the next gate: the target needs exact factor-base membership in the
search, with the W18 pair oracle used as an online predicate. There is still
no ordinary N131 relation, factor-log solution, target scalar, or verified
single-target IC-over-rho speedup.

**Corrected native W18 pair predicate and random-residual boundary
(2026-10-04):** a [frozen 352-coordinate batch](N131_W18_BATCH_PAIR_ORACLE_RESULT.md)
found that the archived native inverse aborted on a valid odd-parity
source pair. The versioned fix flips one leaf's half-trace root according
to the recovered parity before replay. A direct regression reproduces the
old failure and new exact masks; independent checked Sage replays all 96
positive coordinates (64 even and 32 odd) and all 256 uniform-control
first-system decisions. The corrected batch spent 14.4625 ms in 352
inversions with reusable setup outside that interval; host timing is
exploratory. Exact W18 B and subgroup order bound a uniform subgroup
residual's two-point membership probability by `5.06681×10⁻²⁹` per
query. This rules out an independently sampled last-pair repair strategy
under the frozen resource cap, while leaving target-correlated native
generation or algebraic elimination open. The corrected predicate is
ready for such a generator, but it has not produced an ordinary N131
eight-point row, logs, scalar, or verified single-target IC/rho result.

**Selector-first exact pair-state SAT follow-up (2026-10-04):** this was a
strengthening follow-up to the earlier [full exact pair-domain SAT
gate](N41_W6_FULL_PAIR_DOMAIN_RESULT.md), not a new exact-domain method. It
reused the same four 978-state domains from 1,956 valid raw witnesses per
pair, then placed the 3,912 state selectors before circuit variables and
added redundant support clauses for the mask and output bits. Its formula
passed a complete known-row control across all 225,222 CNF clauses and 4,104
XOR rows. The unpinned SAT solve still returned no model at the 120-second
cap, with 249 MB peak RSS. Exact-domain preparation was 0.354 seconds and
excluded; the charged query/formula/search/relation-check interval was
120.019 seconds. Selector ordering and support channeling did not resolve
target-coupled search, so further static SAT-table variants are not the next
method. The next method must join or propagate pair states directly through
the target equation. There is no ordinary N131 relation, factor-log solution,
target scalar, or verified single-target IC-over-rho speedup.

**N131 official single-target R2 setup interruption (2026-10-04):** the
target-independent known-scalar factor-log query in attempt 1 ran for
32,124.180 seconds, then CryptoMiniSat exited with `-15`, well before its
604,800-second query limit. The raw runner labeled this `budget`, but its
record has no stop reason and no SAT/UNSAT terminal line, so the separate
[process-loss receipt](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/precomputation/attempt_001/process_loss_observation.json)
classifies it as `INTERRUPTED_UNCLASSIFIED`: rank stayed 0/14, no relation was
verified, and peak combined RSS was 2,913,779,712 bytes. Attempt 2 then
started a new known-scalar setup query and its existing
[process-loss record](n131_w2_m15_official_single_target_4g_r2_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR2/precomputation/attempt_002/process_loss_observation.json)
records an unclassified interruption without a terminal result. Both were
target-independent setup work; the frozen primary target's online interval
has not started. No restart is counted as a solve or speedup.

**Independent pair-list native-join frontier (2026-10-04):** the
[exact N41 / modeled N131 frontier](N41_N131_FOUR_PAIR_SAMPLING_FRONTIER_RESULT.md)
uses all twelve independently replayed rows on the fixed public N41 point
to compute exact survival probabilities under four independently sampled
pair lists. The first per-list sizes reaching 50% and 90% fixed-target
coverage are 952 and 1,264 of 1,956 states. For the exact N131 W18
geometry, the optimistic uniform-target four-list model needs about
4.66 billion pair states per list for 50% coverage, or 391 GB of bare
21-byte records across four lists. A 4-GiB raw ceiling holds at most
51.13 million per list and has only about `1.00×10⁻⁸` modeled success
probability. Independent rational arithmetic audited the fixed-target
calculation and N131 integer counts. This rules out independently
sampled, stored pair-list joins under the declared memory envelope;
it does not rule out adaptive, streamed, or algebraic methods. The next
constructive gate must couple at least two pair domains to the public
target before list materialization and demonstrate that pruning on an
unpinned N41 row, then a bounded N131 ordinary relation. No N131 row,
factor logs, target scalar, or paired isolated IC/rho result exists.

**N131 official one-target R3 restarted target-independent log setup
(2026-10-04):** after R2's two censored setup attempts, R3 froze the same
`PDP15sat` candidate and exact one-public-Q workload with new run and solver
seeds. The checked runtime and
[R3 freeze receipt](n131_w2_m15_official_single_target_4g_r3_20261004/run_R3_freeze_receipt.json)
are saved before launch. At the
[20:07 UTC process sample](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T200740Z_psutil.json),
its first one-target known-scalar setup query was active at restart 820 and
2,042,544,128 bytes combined RSS of the 4-GiB cap. The accompanying
[snapshot correction](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T200740Z_psutil_correction.json)
retains and fixes one incorrectly computed parent-path boolean. This is setup
progress only: no factor log has been added, the primary Q online interval has
not started, and there is no speedup result. See the
[R3 record](n131_w2_m15_official_single_target_4g_r3_20261004/README.md).

**R3 setup progress (2026-10-04 20:13 UTC):** the same single known-scalar
setup query remained active at restart 1,538, with 2,060,845,056 bytes
combined parent/solver RSS under the 4-GiB cap. Its matrix rank is still
0/14. The
[process sample](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T201350Z_psutil.json)
is a setup-health observation only; the challenge-target online stage has
not begun.

**R3 setup progress (2026-10-04 20:18 UTC):** a later process sample records
the same one-target setup query at restart 1,895 and 2,147,500,032 bytes
combined parent/solver RSS under the 4-GiB cap. Rank remains 0/14; see the
[20:18 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T201832Z_psutil.json).

**R3 setup progress (2026-10-04 20:21 UTC):** the live setup query advanced
to CMS restart 2,229; combined parent/solver RSS was 1,660,911,616 bytes.
Rank remained 0/14 and no relation was returned. The
[process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T202131Z_psutil.json)
confirms the one-target setup query is still active; the official Q online
clock has not started.

**Shared seed-sum bit screen and next constructive gate (2026-10-04):**
the [exact support screen](CROSSPAIR_SEED_SUM_SCREEN_RESULT.md) predeclared
equality of the lowest seed-sum mask bit across four same-rotation pairs.
It retains two of twelve verified rows on the fixed ordinary N41 public
point. Checked Sage and an independent native scan agree that exact N131
W18 rational-seed parity counts are 65,600 and 65,707; the corresponding
unordered seed-pair classes are 4,310,319,271 and 4,310,379,200. The
uniform independent-pair-bit model retains about 259.69 expected N131
rows, but one literal bit bucket alone exceeds 361 GB at 21 bytes per
state even after a conservative same-column exclusion. This is a modest
static filter, not a target-coupled solver or observed N131 yield. The
[next goal](NEXT_TARGET_COUPLED_BLOCK_GOAL.md) freezes the N41 public
target, requires unpinned target-dependent pruning across at least two
exact pair domains without a 4+4 index, and requires a 4-GiB/600-second
N131 work bound and planted replay before a fresh ordinary query. No
ordinary N131 relation, factor logs, target scalar, or paired isolated
IC/rho speedup exists.

**R3 setup progress (2026-10-04 20:25 UTC):** the checked parent/solver
identity was revalidated while the first known-scalar setup query remained
live. CryptoMiniSat advanced to restart 2,490; combined RSS was
1,129,496,576 bytes under the 4-GiB cap. Rank is still 0/14, and the official
Q online interval has not begun. See the
[20:25 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T202520Z_psutil.json).

**R3 setup progress (2026-10-04 20:35 UTC):** the same identity-checked
solver remains active and advanced to restart 3,014. Combined RSS is
1,215,365,120 bytes; rank remains 0/14. The
[20:35 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T203551Z_psutil.json)
records setup progress only; the public Q online interval has not started.

**R3 setup progress (2026-10-04 20:52 UTC):** the identity-checked query
remains active at restart 4,009 with 712,278,016 bytes combined RSS. Rank is
still 0/14 and no factor log has been returned. See the
[20:52 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T205207Z_psutil.json).

**R3 setup progress (2026-10-04 21:04 UTC):** process identity still matches
the frozen one-target run; CryptoMiniSat reached restart 4,153 with
670,171,136 bytes combined RSS. Precomputation remains rank 0/14 with no
relation. The
[21:04 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T210420Z_psutil.json)
records setup progress only.

**First-pair generation and exact-completion gate (2026-10-04):** the
[same-policy frontier](FIRST_PAIR_GENERATION_FRONTIER_RESULT.md) uses the
complete replayed N41/W6 public-target census: 12 of 1,956 first-pair
states have any eight-point completion. For N131/W18, at least
34,448,654,064 distinct-column first-pair states remain, so a literal
full scan within 600 seconds needs 57,414,424 target-dependent checks per
second. For one target-independent first pair under the uniform
nonidentity target law, a cardinality bound limits three-pair completion
probability to `6.0248031×10^-8`. The union bound then requires at least
8,299,027 distinct exact-completion probes for 50% success, or 13,832
probes per second in 600 seconds; that necessary count does not establish
sufficiency or apply to target-adaptive generation. This sharpens the
constructive gate to a target-coupled symbolic generator **or** a cheap
exact three-pair completion oracle with a measured work/memory bound.
It is a work frontier, not an ordinary N131 relation or speedup.

**DPLL_ANF solver-family gate (2026-10-04):** the
[N41 result](N41_W6_S8_DPLL_ANF_RESULT.md) preserves a first invalid
UNSAT trial caused by the solver's `polynomial = 1` input convention and a
separate corrected trial. The corrected converter rebuilt the frozen
public-target XCNF exactly and a separate known-row-pinned solver input
returned SAT; its complete model passed ANF and original-XCNF replay.
The unpinned one-worker ordinary query then hit its 120-second wall cap at
88,129,536 bytes peak sampled combined RSS with no model. Its charged
target-dependent stage sum was 121.828 seconds including formula build and
conversion. This is zero verified N41 rows, not UNSAT, and remains a
proposal-stage diagnostic with null candidate/run IDs. Alongside the
native-XOR SAT and generic F4 failures, it supports the
[target-coupled pair-block method gate](NEXT_TARGET_COUPLED_BLOCK_GOAL.md)
as the next experiment; no N131 relation, factor logs, target scalar, or
paired isolated IC/rho speedup exists.

**Four-pair seed-sum/target quadratic rank gate (2026-10-04):** the
[exact N41 witness](N41_FOUR_PAIR_TARGET_QUADRATIC_RANK_RESULT.md)
uses 8,192 distinct-column eight-point tuples and their actual group-sum
targets. Its 2,146 degree-at-most-two Boolean features comprise the four
six-bit pair seed sums and all 41 target-x bits. Producer row rank and an
independent checked-Sage replay of every tuple plus column-rank computation
both give **2,081**. The 65 missing dimensions are exactly `x_0=0` and
its multiples by the other 64 bits. This proves that no further universal
quadratic equality in that feature family can prune the target-coupled
pair search; pair outputs, leaf products, higher degree, or another exact
method remain open. It is a structural method-selection result only: the
fixed N41 target was not solved by this screen, and no N131 relation,
factor logs, scalar, or paired isolated IC/rho speedup exists.

**Adjacent two-pair F4 feasibility gate (2026-10-04):** the
[N41 public-only planted control](N41_ADJACENT_TWO_PAIR_F4_RESULT.md)
compressed the exact four-leaf target-coupled equations to 142 Boolean
variables and 155 degree-at-most-two functional equations. The known-row
preflight and independent Sage group replay passed, while the unpinned
one-worker Msolve attempt hit its 120-second cap with no Gröbner basis or
verified row; peak sampled process-tree RSS was 1,350,762,496 bytes. The
write-once receipt and artifact audit preserve the failure. This makes
generic quadratic F4 a poor next N131 scaling bet under the current cap;
the [next gate](NEXT_TARGET_COUPLED_BLOCK_GOAL.md) requires structural
pair-block elimination or target-conditioned generation, with a public-only
small control and source-bound N131 work/memory estimate before an ordinary
N131 attempt. The timed interval is a feasibility diagnostic and lacks host
isolation; the runner's preliminary public-point subgroup check was outside
its timer. No N131 relation, factor logs, recovered scalar, or controlled
one-target IC/rho speedup follows from this result.

**Degree-five single-leaf rank gate (2026-10-04):** the independently rebuilt
[N41 rank result](N41_DEGREE5_SINGLE_LEAF_RESULT.md) lifts the frozen 498
quadratic equations by all 42 square-free degree-at-most-three monomials in
one later six-bit leaf. Its 20,916-row, 433,293-column invariant matrix has
rank **17,346**, exactly the ceiling from the 85 audited source syzygies
repeated in 42 disjoint row blocks. Both Sage sparse elimination and an
independent integer-bitset audit agree, so this relaxation remains consistent
for all 4,096 first-pair assignments. This rejects another single-leaf
invariant projection as a useful early-pruning mechanism; the next experiment
must couple pair outputs or symbolically eliminate across multiple pair
domains. The rank and replay each completed below 40 seconds and about 1.01 GB
under a one-worker 4-GiB guard; these are exploratory diagnostics, not
controlled IC timings. No N131 ordinary relation or one-target speedup
exists.

**N131 R3 setup progress (2026-10-04 21:25 UTC):** the frozen one-target
known-scalar setup query is still active. CryptoMiniSat has accumulated about
4,646 CPU seconds, with 371,113,984 bytes solver RSS and 37,535,744 bytes
parent RSS at the sample; the precomputation rank remains 0/14 and no
relation has been returned. See the
[21:25 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T212543Z_continuation.json).
This remains target-independent setup; the official public target's online
clock has not started.

**Exact public-Q affine-XOR gate (2026-10-04):** the [frozen result](n131_official_m15_affine_xor_20261004/RESULT.md)
compares the R3 original and affine emitters on the **same published
ECC2K-130 Q** and exact W2 base. Affine emission reduces variables from
844,189 to 468,294 (44.5%) and XOR rows from 523,122 to 147,227 (71.9%),
with unchanged 1,054,158 CNF clauses. A planted 15-leaf control passed full
CNF/XOR model replay, but the unpinned public query hit its 600-second cap
with zero models. A same-formula trial that admitted the large XOR matrices
also hit 600 seconds with zero models and a 2.38-GiB sampled peak. These are
exploratory encoding and relation-stage results, not ordinary yield, factor
logs, recovered scalar, or a verified one-target IC/rho speedup. The next
constructive gate must couple target and pair/leaf domains more effectively
on an ordinary small-field control before another N131 query. A third
same-formula public-Q probe removed Gaussian matrices and enabled CCNR local
search. Its planted control passed full model and independent Sage group
replay, but the unpinned public run also reached 600 seconds without a model
at 597 MB sampled peak RSS. This closes the simple matrix-limit/CCNR setting
line under the frozen local cap; it does not prove zero natural relation yield.

**Exact W2 base-index encoding gate (2026-10-04):** the
[single-target experiment](n131_m15_binary_leaf_pair_encoding_20261004/README.md)
replaced each 131-bit free W2 leaf by two ordered 8-bit coordinate indices.
The pinned one-target planted control passed, and fresh checked Sage replayed
the signed relation and folded row. On the **same official Q and exact W2
base** as the prior direct-bit gate, the ordinary query still reached its
600-second cap with zero models. The indexed formula was larger (847,684
variables, 1,069,068 clauses, 525,327 XOR rows) than the direct-bit formula
(844,189, 1,054,158, 523,122). The stage result is censored, so this encoding
does not establish a speedup. Its first control run is retained as a producer
failure: it incorrectly applied ordinary-query leaf ordering to the already
pinned planted tuple. The final frozen candidate skips that redundant ordering
only for the fully pinned control. The next ordinary N131 attempt remains
gated on an independently checked target-coupled N41 row and credible N131
work/memory projection as specified in
[`NEXT_TARGET_COUPLED_BLOCK_GOAL.md`](NEXT_TARGET_COUPLED_BLOCK_GOAL.md).

**N131 R3 remains active (2026-10-04 22:54 UTC):** the exact PID check
confirmed that the single known-scalar setup query is still running after
9,766 CryptoMiniSat CPU seconds. Its rank remains 0/14, no relation has been
returned, and combined parent/solver RSS was 557,105,152 bytes. The ordinary
Q interval has not started. See the
[22:54 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T225351Z_continuation.json).


**N131 R3 setup progress (2026-10-04 23:22 UTC):** the same two PIDs still
match the frozen one-target run. CryptoMiniSat has accumulated 11,498.55 CPU
seconds; combined parent/solver RSS is 563,675,136 bytes, below the 4-GiB
limit. Setup rank remains 0/14 with no relation. The official Q online clock
has not started. See the
[23:22 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T232212Z_continuation.json).


**Pair-interleaved W6/S8 control gate (2026-10-04):** the
[new one-target experiment](n41_w6_s8_pair_interleave_20261004/RESULT.md)
changes only the mask-variable allocation order in the existing exact
seven-link S3 formula. Its complete planted assignment preflight passes, but
the one-worker pinned SAT control again reaches its 30-second cap without a
model (80,150,528-byte sampled RSS). The reference-order pinned control also
reached the cap at 30.034652 seconds, so interleaving provides no demonstrated
feasibility gain. The ordinary public target was not launched because the
pinned solver control failed. This closes the bit-interleaving-only branch;
the next experiment should change the algebraic/XOR preprocessing, not try
another variable-order permutation. Candidate/run IDs remain null, and no
N131 ordinary relation or speedup is established.

**N131 XOR private-pivot screen (2026-10-04):** the [incidence profile](n131_official_m15_affine_xor_20261004/XOR_COMPONENT_PROFILE.md)
checks both the live R3 known-scalar setup formula and the frozen affine public-
Q formula. All 26 XOR components in each formula peel completely by exact
degree-one-column pivots, including the 13 repeated large blocks; the residual
linear row-space core is zero. This rules out reducing the XOR row count by
rank-only preprocessing, while CNF coupling remains intact. A different sparse
basis could still improve propagation, but it needs its own paired solver
test; given the earlier widened Gaussian run's poor performance, the next
useful method gate remains target-coupled pair-domain pruning. No solver was
launched by this diagnostic, and it establishes no relation, yield, recovered
scalar, or IC/rho speedup. The live R3 setup query was preserved unchanged.

**N131 R3 setup progress (2026-10-04 23:49 UTC):** an identity-checked
sample still finds the same one-worker known-scalar setup query active at
restart 8,496 with 13,145.34 solver CPU seconds and 607,797,248 bytes combined
RSS. Its relation rank remains 0/14; the official Q online clock has not
started. See the
[23:49 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261004T234959Z_continuation.json).

**N131 R3 setup progress (2026-10-05 00:10 UTC):** the identity-checked
single known-scalar setup query remains active. CryptoMiniSat has accumulated
14,230.57 CPU seconds, up 1,154.74 seconds from the 23:49 UTC sample; combined
parent/solver RSS is 422,248,448 bytes. Precomputation rank remains 0/14 with
no completed attempts. This is target-independent reusable setup, and the
official public-target online clock has not started. See the
[00:10 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T001014Z_continuation.json).

**Fresh N131 W2/m20 affine-XOR gate (2026-10-05 00:33 UTC):** a frozen,
one-worker exact-base query on a fresh ordinary subgroup target returned zero
SAT models and zero relations at 597.659 s under the 600-s parent cap. Its
formula has 642,292 variables, 1,446,928 CNF clauses, and 200,350 native
XOR rows; sampled combined peak RSS was 1.129 GB. The planted 20-leaf
control's complete model and independent checked-Sage row replay passed,
but the original producer's RSS-monitor race remains recorded. A scope audit
corrected the protocol's distinct-x wording: the public formula permits
proper signed repeated-x multisets. A prospective exact meet-in-the-middle
sign-lift checker passed the N131 planted and repeated-x controls but was not
part of the public query; zero-model SAT search remains the bottleneck. See
the [terminal result](n131_w2_m20_affine_density_20261004/README.md). This
does not establish ordinary-query yield, factor logs, a DLP, complete IC
online time, or a rho speedup. The immediate gate remains the
[target-coupled pair-block goal](NEXT_TARGET_COUPLED_BLOCK_GOAL.md): an
unpinned independently replayed N41 W6 ordinary row within 120 s/4 GiB,
with early pair-domain pruning, followed by a source-bound N131 W18
600-s/4-GiB preflight before one frozen fresh N131 query. This is a distinct
factor-base policy from the W2/m20 stage.


**N131 R3 setup progress (2026-10-05 00:40 UTC):** identity-checked PIDs 99052 and 99169 remain active. CryptoMiniSat has accumulated 15669.79 CPU seconds (1359.23 more than the 00:10 UTC sample); combined RSS is 485,769,216 bytes. Precomputation rank remains 0/14 with 0 completed attempts. This is target-independent reusable setup; the official Q online interval has not started. See the [00:40 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T004011Z_continuation.json).

**N41 W6/S8 mask-only propagation control (2026-10-05):** the first monitor attempt hit a macOS `psutil` global-process-enumeration permission error after starting CryptoMiniSat, so it has no valid solver receipt and is excluded. A fresh frozen one-target retry used the same public Q and pinned only the eight masks of a known row, leaving every leaf, pair, middle, and gate variable free. CryptoMiniSat emitted `s INDETERMINATE` after 28.673 s at its 28-s cap (raw return code 15); peak sampled parent-plus-solver RSS was 112,001,024 bytes. The receipt's wrapper status `SOLVER_ERROR` is corrected in the [result interpretation](n41_w6_s8_quadratic_maskcube_20261004_r2/RESULT.md): this is a censored control, not UNSAT or a recovered row. It does not justify another mask-only SAT run or a public ordinary query.

**N131 R3 setup progress (2026-10-05 01:09 UTC):** identity-checked PIDs 99052 and 99169 remain active. Since 00:40, the one-worker solver accumulated 1,677.85 CPU seconds; combined RSS is 533,479,424 bytes. The target-independent setup-query rank is still 0/14 with no completed attempts. The official fresh-Q online interval has not started. See the [01:09 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T010935Z_continuation.json).

**N131 R3 setup progress (2026-10-05 01:32 UTC):** the same identity-checked one-worker query remains active 5 h 27 min after launch. Solver CPU reached 18,627.65 seconds, up 1,280.01 seconds since 01:09; combined RSS is 542,998,528 bytes. Reusable-log rank remains 0/14 with no completed attempts. The official public-Q online clock has not started. See the [01:32 process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T013223Z_continuation.json).


**N73 compact-orbit transfer gate (2026-10-05):** the existing frozen
one-target N73 run verified both IC and rho answers and measured 249.023875 ms
IC online versus 46,034.26425 ms rho online (184.858838334x); its 18,425,728 ms
reusable IC setup is excluded. The result remains exploratory because the host
was not isolated and the arms had no common finite memory cap. A uniform
four-summand support screen for the official N131 subgroup requires at least
5,107,605,668 base points and 19,494,679 signed-Frobenius columns for one
expected representation. The direct compact index would contain 49,785,568,720,008,371
pair states (at least 398 PB even at eight bytes per state), so do not port this
exact PDP4root layout to ECC2K-130. This is a model-based rejection of the
direct four-summand transfer, not of higher-summand or structured-base IC.
N131 `candidate_id` and `run_id` remain null. See the
[N73 transfer gate](N73_COMPACT_ORBIT_TRANSFER_GATE_20261005.md) and its
[reproducible audit](audit_n73_compact_orbit_transfer.py).


**N131 R3 setup progress (2026-10-05 02:02 UTC):** the exact runner and
CryptoMiniSat child still match their recorded PIDs, command lines, parent link,
and creation times. The solver has accumulated 20,197.96 CPU seconds and the
parent-plus-solver RSS sample is 1,010,745,344 bytes. Reusable-log rank remains
0/14 with no completed relation attempts; the official public-Q online clock
has not started. The job was left running. See the
[02:02 identity-checked observation](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T020213Z_continuation.json).

**Same-Q N131 W2/m16 four-anchor gate (2026-10-05 00:58 UTC):** four
target-independent signed base points from distinct folded columns were
fixed, leaving a 16-leaf exact-base equation on the same fresh public Q as
the m20 gate. The planted full-model control and independent checked-Sage
group replay passed. The public formula shrank to 503,280 variables,
1,132,712 CNF clauses, and 158,038 native XOR rows, but produced zero models
and zero relations in a 596.510-s charged target-dependent interval;
sampled combined peak RSS was 1,022,853,120 bytes. The
[terminal result](n131_w2_m16_anchor4_20261004/README.md) preserves the
censored row, exclusive phase accounting, exact multiset scope, and original
m20 same-Q comparison. This closes one anchor/arity tradeoff under the cap,
not the target-coupled search problem. No N131 factor logs or DLP follow.

**Matched N41 balanced-S3 topology gate (2026-10-05 02:06 UTC):** the
balanced tree and a newly frozen affine-IR left chain each passed a fully
pinned model/group control on the existing independently replayed N41 W2/m8
ordinary row. Their leaf-only formulas have identical 37,306 variables,
84,246 clauses, and 10,819 XOR rows. Both returned no model before the
27-second internal solver cap (26.109 s and 26.097 s charged respectively),
so the unpinned ordinary promotion query was not launched. The
[matched audit](n41_w2_balanced_s3_gate_20261004/README.md) records the
historical emitter difference and the corrected same-emitter control.
Balanced topology alone has not cleared intermediate search; no N131
relation, verified target scalar, or IC/rho speedup is established.

**N41 exact-base projective group-law gate (2026-10-05):** an inversion-free
López–Dahab SAT encoding over the frozen N41 W2/m8 public target passed its
fully pinned ordinary-row control and an independent checked-Sage replay of
all seven projective links. The exact signed-base formula has 81,442
variables and 24,889 XOR rows. With all eight leaves free, the 120-second
one-worker run returned zero models and relations at 119.243 s charged wall;
sampled combined peak RSS was 278,364,160 bytes. The
[terminal result](n41_w2_projective_group_gate_20261004/README.md) preserves
the 4-GiB limit, protocol and source hashes, formula counts, timeout, and
exclusive phases. The smaller circuit and leaf-pinned propagation do not
solve the unpinned search. This is an N41 method diagnostic only, not an N131
relation or speedup; the target-coupled pair-block gate remains open.

**N131 native W18 pair-oracle exactness correction (2026-10-05):** the prior
native inversion stage accepted two algebraic S3 mask pairs for a frozen
full-width coordinate even though their raw source x coordinates had no
rational curve lifts. The new source checks rationality and all four signed
group sums before emitting a pair. On source-locked negative and positive
controls, it rejected both false pairs and retained the existing planted
pair; an independent checked-Sage replay agreed for every emitted algebraic
candidate. The [audited correction](n131_w18_native_pair_oracle_exact_20261004/README.md)
also records an explicit high-nullity limit and an inconclusive optional
sanitizer attempt. This fixes a local oracle false positive, but neither
generates pair outputs jointly nor provides an N131 ordinary relation or
single-target DLP result.

**N41 W2/m8 sparse-orbit transfer gate (2026-10-05):** the new N131 W2/m15
sparse-orbit multiplier idea was tested on the frozen N41 public target with
exact B=164/K=2 base membership. All 82 orbit selectors and 3,362
selector-by-basis products passed the arithmetic preflight. The full-pinned
SAT model and group replay passed at 31,433 variables, 63,101 clauses, and
14,517 XOR rows. The same formula with only its eight known leaves fixed
returned CryptoMiniSat `INDETERMINATE` after 28.390 s charged, with no model
and 123,682,816 bytes sampled combined peak RSS. The
[audited result](n41_w2_sparse_orbit_gate_20261005/README.md) preserves the
frozen source snapshot, timing phases, and failure. The public-only query was
not launched under the promotion gate. This tests method transfer only: no
N131 ordinary relation, scalar, or IC/rho speedup follows. Sparse orbit
arithmetic alone has not cleared the known-leaf intermediate search barrier.

**N131 W2/m15 sparse-orbit multiplier gate (2026-10-05):** the exact frozen
base has 3,668 signed points, 1,834 x-coordinates, and 14 complete
Frobenius orbits. A leaf is encoded by an orbit and an eight-bit rotation;
the gate checks every valid rotation 0..130 and rejects 131..255. Rewriting
`uvw` as `v*(u*w)` gives 43 exact sparse-orbit multiplications plus 13 generic
multiplications across the 14-link chain. Exhaustive selector and basis-vector
checks passed, along with eight planted 15-point chains (112 S3 equations,
344 sparse-product positions) and an independent checked-Sage replay of all
120 subgroup points and eight group sums. A deterministic evaluation of the
complete encoded planted formula also passed every one of 569,044 Tseitin
gates, all clauses, and all native XOR rows. Its planted target differs from
official Q, so its target-specific formula count (570,928 variables) is
separate from the official-Q count below. On the same official single target,
the in-memory formula has 570,213 variables, 891,240 clauses, and 329,740
native XOR rows, versus 844,189 variables, 953,928 clauses, and 523,107 XOR
rows for the generic formulation. The specialized leaf selector also enforces
exact enumerated base membership, while the generic weight-at-most-two
formula has a broader raw leaf domain, so the size delta is not solely a
multiplication-kernel comparison. The specialized XCNF round-tripped through
the writer/parser at 25,983,798 bytes with matching counts, but no solver was
run; no ordinary relation, factor logs, DLP, or wall-time speedup exists.
The previous R3 setup query was left untouched; its latest saved process
identity receipt is at 02:02 UTC and records rank 0/14. See the
[sparse-orbit gate report](n131_w2_m15_sparse_orbit_20261005/SPARSE_ORBIT_GATE.md)
and machine-readable arithmetic, complete-formula, and Sage receipts in that
directory.

**R3 live-search log check (2026-10-05 03:03 UTC):** the known-scalar
CryptoMiniSat stdout log was appended at 20:03:41 PDT and its last records are
still search/distillation statistics, with no terminal status. Direct PID
inspection remains unavailable in this sandbox (`ps`/`kill` return permission
errors and `launchctl procinfo` requires root), so this records recent solver
output rather than a fresh identity-checked process sample. No second SAT job
was launched while this search continues to write.

**N131 offset-one W18 native exact pair inversion (2026-10-05):** the
[source-locked panel](n131_w18_offset_one_native_exact_20261005/README.md)
matches 32/32 planted pair outputs and rejects 64/64 uniform first-gate
controls. Checked Sage independently replays all 34 native pair masks as 68
signed group sums. Eight additional consistent-but-nonrational outputs are
correctly rejected; independent Sage confirms their gate ranks and ten
nonrational algebraic masks. The median internal target-dependent times are
0.708 ms for planted outputs and 0.0195 ms for uniform first-gate rejections
on an unisolated Mac. These timings are exploratory local-stage diagnostics;
the panel has no enforced memory cap after a retained macOS launch failure.
The inverter tests a proposed pair output and does not select four outputs
jointly from a public target. The [next goal](NEXT_TARGET_COUPLED_BLOCK_GOAL.md)
remains an unpinned N41 public-target row with early cross-pair propagation,
then a source-bound N131 transfer. No ordinary N131 relation, factor logs,
verified DLP, or IC/rho speedup follows from this local result.

**Offset-one W18 exceptional-case improvement (2026-10-05):** the
[fixed-left linear-right fallback](n131_w18_offset_one_native_exact_20261005/FIXED_LEFT_FALLBACK.md)
uses the cleared pair equation as an 18-bit linear system after choosing a
left leaf, instead of enumerating a large 79-column kernel and a 512-mask
fiber. A source-locked 104-case panel exactly matches the prior planted,
uniform, and nonrational outputs; the previous independent checked-Sage
replays cover the matched mask sets. Three large-kernel nonrational controls
fell from 2.106–16.834 seconds to 0.089–0.107 seconds of internal query time
on this unisolated Mac. These are exploratory local-stage diagnostics, not
an isolated CPU speedup claim. The improvement applies only after a pair
output is proposed; the public-target joint-output search and natural N131
relation gate remain open.

**On-demand last-pair frontier (2026-10-05):** the
[source-bound integer audit](n131_w18_offset_one_native_exact_20261005/LAST_PAIR_FRONTIER.md)
uses the exact W18 window size and subgroup order to show that a six-leaf
prefix chosen independently of a uniform nonidentity target has at most
`34,482,925,191/(r−1) ≈ 5.07×10^-29` chance of leaving a residual in the
last W18 pair domain. At least `9.87×10^27` such probes are necessary for
50% success by a union bound; even an illustrative billion probes per
second for 600 seconds gives an upper success probability of
`3.04×10^-17`. This is conditional uniform-target arithmetic, not a
fixed-challenge-point yield observation or a bound on target-adaptive
algebraic search. It closes independent six-leaf sampling as a wrapper
around the improved inverter and keeps the next method focused on early
public-target coupling across multiple pair domains.

**Official W2/m15 R3 live handle (2026-10-05 03:25 UTC):** a direct
PID-specific `psutil` observation now verifies solver PID 99169 and Sage
parent PID 99052 with their original creation times and expected command
lines. The solver's live stdout reached restart 11,190 and had no terminal
SAT status; the progress file still records rank 0/14 on the first
target-independent precomputation query. Combined sampled RSS was
755,204,096 bytes. The [observation receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_observation_20261005T0325Z.json)
updates the earlier 03:03 UTC log-only check without altering the worker.
No ordinary relation or online target query has been completed.

**N131 W18 offset-one folded-column correction (2026-10-05):** a new
[same-column control](n131_w18_offset_one_native_exact_20261005/COLUMN_FILTER_RESULT.md)
found two valid rational group-sum mask pairs that v2 reported as
`WITNESS_FOUND` even though each pair's projected leaves occupy the same
signed-Frobenius factor-base column. The v3 native inverter now records
those under `group_w_masks` and returns only distinct-column `w_masks` as
IC-usable. A source-locked 105-case panel retains all 34 planted usable
pairs and rejects both same-column witnesses. Checked Sage verifies the
planted and negative columns; a separate 192-pair native/Sage panel and an
order-four reciprocal control pass. The [audit](n131_w18_offset_one_native_exact_20261005/v3_audit.json)
binds the artifacts. This repairs local relation validity, while the
target-coupled output generator, ordinary N131 relation, logs, DLP, and
paired rho measurement remain open.

**N131 sparse m15 model-to-relation gate (2026-10-05):** the new decoder
recovered all 15 exact W2 factor-base x-masks from each of eight planted SAT
selector models. It then used the thirteen modeled partial-sum x-coordinates
to lift point signs and replayed all eight 14-column relation rows against the
frozen official base. This bypasses the production path's exhaustive
`2^15` sign-mask scan when sparse models are decoded. The checker ran through
the repository's checked `./sage` launcher and preserves source and input
hashes in
[`sparse_model_decode_check.json`](n131_w2_m15_sparse_orbit_20261005/sparse_model_decode_check.json).
The controls are planted correctness cases; no SAT query, natural relation,
factor logs, scalar, or candidate/run ID resulted. The R3 known-scalar
CryptoMiniSat log was still appending search statistics at 20:16 PDT with
rank 0/14, so no competing solve was started. The next useful step is to
run the prepared separate sparse method-gate runner's single unpinned public-Q
query only after R3 reaches a terminal state. That runner has source and
single-target input checks, a shared 600-second budget, one solver worker,
and a 4-GiB envelope. Its terminal-result guard was exercised and refused to
launch because R3 is still active and has no terminal result receipt. It
also requires a current Sage runtime receipt. It reports an ordinary relation
gate only; it does not claim reusable logs, DLP recovery, or a speedup.

**N131 shared-endpoint W2 multiplier refinement (2026-10-05):** factored each
of the fourteen exact weight-two base multipliers into two ONB basis maps and
paired columns sharing a basis endpoint. For the same official single target,
the formula has 489,577 variables, 891,196 clauses, and 249,115 XOR rows. That
is 42.0% fewer variables, 6.6% fewer clauses, and 52.4% fewer XOR rows than
the same-target generic formula; compared with the earlier sparse-orbit
formula, it removes 14.1% of variables and 24.5% of XOR rows with 44 fewer
clauses. The kernel passed 240,254 basis-vector arithmetic cases, a complete
planted formula check (488,408 gate operations; zero failed clauses or XORs),
and remapped selector-to-row replay on all eight planted controls. The
[formula screen](n131_w2_m15_sparse_orbit_20261005/sparse_shared_endpoint_screen.json),
[planted formula receipt](n131_w2_m15_sparse_orbit_20261005/shared_endpoint_formula_witness_check.json),
and [remapped relation receipt](n131_w2_m15_sparse_orbit_20261005/shared_endpoint_model_decode_check.json)
bind this refinement. These are correctness and formula-size results, not
solver or DLP timings. The public-Q gate runner now uses this kernel and its
selector-code map.

**R3 live-process verification (2026-10-05 03:57 UTC):** direct
`proc_pidinfo` identity checks confirm the recorded Python/Sage runner PID
99052 and its CryptoMiniSat child PID 99169 still have the same executable
paths, start times, parent-child link, and attempt PID file. A second sample
913 seconds after the prior one observed increased solver task counters and a
newer log hash/mtime. Precomputation remains rank 0/14 with no completed
attempts, and there is no terminal result receipt, so the shared-endpoint
public-Q gate remains safely guarded. See the
[03:57 live observation](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T035701Z_continuation.json).

**N131 W2/m15 linearized S3 gate (2026-10-05):** combining the two
leaf-multiplication terms into `v(u+w)` removes one sparse product from every
S3 link of the exact sparse-orbit formula. The [source-bound result](n131_w2_m15_linearized_20261005/RESULT.md)
reduces the frozen public-Q formula from 570,213 to 453,691 variables,
1,220,980 to 939,665 clause/XOR records, and 25,983,798 to 19,881,996
XCNF bytes. Eight planted chains pass the exact algebra check, one planted
complete formula passes every clause and XOR row, and the public-Q XCNF
round-trips with matching counts. A separate 600-second/4-GiB one-worker
method-gate runner passes source/runtime/input preflight but refuses to start
before R3 is terminal; no SAT solve on the new variant, natural N131 relation,
factor logs, scalar, candidate/run ID, or speedup is claimed. Once R3 has a
terminal receipt, the next algorithm measurement is one unpinned public-Q
query using this smaller formula under the frozen resource envelope.

**N131 W2/m15 two-position normal-basis gate (2026-10-05):** the
[next exact variant](n131_w2_m15_two_position_20261005/RESULT.md) uses each
W2 leaf's two normal-basis positions and one fixed basis-element
multiplication matrix. All 1,834 valid selector/rotation position circuits
and 1,834 independent field products pass; a planted full formula passes
every clause/XOR, another 84 varied multiplier CNF controls pass, and the
public-Q XCNF round-trips. Relative to the first
sparse formula, variables fall from 570,213 to 345,104 and total records from
1,220,980 to 861,612. Clauses are higher than in the immediately preceding
linearized variant, so SAT performance is unknown. A separate guarded
one-target 600-second/4-GiB runner passes source and runtime preflight but
refuses to overlap the still-active R3 process. No ordinary N131 relation,
logs, scalar, candidate/run ID, or IC speedup is claimed. Once R3 is terminal,
run this two-position public-Q gate first, then compare the other frozen
formula variants if the result warrants another bounded query.

The [two-position formula resource preflight](n131_w2_m15_two_position_20261005/formula_resource_preflight.json)
then regenerated the exact public-Q XCNF while R3 remained active. Its
parent-process peak RSS after serialization was 172,392,448 bytes, leaving a
conservative 4,122,574,848-byte solver RSS allowance under the 4-GiB
parent-plus-solver envelope at that point. This rules out formula construction
as the immediate 4-GiB blocker but gives no evidence of SAT yield or runtime.
The host reported a load average near 102 on 14 logical CPUs, so a concurrent
solver wall-time comparison would be exploratory and would interfere with R3.

**N131 W2/m15 two-position public-Q probe (2026-10-05):** a separate
[contended correctness-only method gate](n131_w2_m15_two_position_20261005/CONTENDED_PUBLIC_Q_PROBE_RESULT.md)
ran one unpinned official-Q query while preserving the frozen R3 process. It
used one CryptoMiniSat worker, a shared 600-second target-query wall budget,
and a 4-GiB parent-plus-solver RSS cap. The source- and formula-hash-bound
attempt timed out after 599.332290 seconds with no SAT model or verified
relation. All exclusive phases sum, peak combined RSS was 545,308,672 bytes,
the probe solver was reaped, and R3 continued at rank 0/14. The host was
heavily contended, so this is a preserved zero-yield failure and exploratory
timing only. It does not show that the exact target lacks a decomposition or
establish an IC speedup. The first gate remains an unpinned N131 relation
from a target-conditioned or structurally different search method.

**R3 continuation and two-position gate recheck (2026-10-05 04:06 UTC):**
PID-specific inspection confirmed the same Sage runner (PID 99052) and its
CryptoMiniSat child (PID 99169), with matching start times and executable
paths to the prior observation. The solver log advanced to 2,313,452 bytes
through 04:06 UTC; precomputation remains `RUNNING`, rank 0/14, with no
terminal result, so no competing SAT query was launched. The [continuation
receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T040618Z_continuation.json)
records this state. The [two-position runner preflight](n131_w2_m15_two_position_20261005/preflight_current.json)
passes the frozen single-target inputs, source hashes, checked Sage runtime,
solver binary, and formula controls; it explicitly launched no solver.

**Q1356 N41 three-pair fingerprint gate (2026-10-05):** The
[exact classifier and bounded public query](N41_THREE_PAIR_FINGERPRINT_GATE_RESULT.md)
added eight quadratic and ten cubic cyclic x-coordinate correlations to
the Q1342 orbit selector. The 18 selected features distinguish all 2,424
exact N41 pair-output orbit classes; quadratic features alone distinguish
2,422. A pinned known public row passes SAT and checked-Sage group replay,
but the unpinned public query timed out after 119.147 seconds with no model
or ordinary relation. The frozen audit passes and combined peak RSS was
471,826,432 bytes under the 4-GiB cap. This is a contended-host negative
method gate, not an IC/rho speedup. The next goal is an exact public-target
constraint that rejects partial states while at least two pair domains are
still free, first on the frozen N41 W6 eight-leaf workload, followed by a
source-bound N131 W18 transfer projection before any degree-131 query.

**N131 weight-four projected factor-base screen (2026-10-05):** an exact
checked-Sage census enumerated all 11,716,640 degree-131 normal-basis
weight-four masks and 89,440 Frobenius support orbits. It found 44,719
rational raw x-orbits; cofactor-four projection produced 44,719 distinct
signed-Frobenius log columns with no projection collisions, hence exact
`B=11,716,378` and `K=44,719`. The [result](n131_w4_projected_base_screen_20261005/RESULT.md)
explains the raw-point relation and the `4·log(Q)` correction; the
[machine receipt](n131_w4_projected_base_screen_20261005/projected_base_screen.json)
and [raw-to-column map](n131_w4_projected_base_screen_20261005/raw_to_projected_columns.jsonl)
bind the frozen one-target workload and checked runtime. A uniform full-group
count predicts 2.64 sign witnesses at arity six and about 4.42 million at
arity seven. Those are heuristics only. This is a promising arity/base trade,
not a measured relation yield or complete candidate; the seven-leaf circuit,
ordinary relation, full-rank logs, DLP, and paired rho measurement remain.

**R3 process continuation (2026-10-05 18:00 UTC):** direct PID-specific
inspection again confirms the same Sage runner PID 99052 and CryptoMiniSat
child PID 99169. The solver log grew to 3,945,918 bytes through 17:58 UTC;
precomputation is still `RUNNING` at rank 0/14 with no terminal result. See
the [continuation receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T180031Z_continuation.json).
The two-position W2 public-Q method gate has since recorded a 599-second
no-model timeout on a heavily contended host; it remains a preserved
zero-yield diagnostic, not a speedup result. No new SAT solver was launched
for the W4 proposal.

**Q1357 N41 mixed-cubic target-filter rank (2026-10-05):** The
[frozen algebraic screen](N41_TARGET_PAIR_MIXED_CUBIC_RANK_RESULT.md)
reached full rank 16,046 in the space of all degree-at-most-two Boolean
features of the first-pair mask/sign and target-x bits plus all mixed cubic
features of types one-pair/two-target and two-pair/one-target. An independent
low-pivot audit replayed all 16,046 exact eight-column witness rows and the
full rank; checked Sage verified all 512 source points and 256 selected group
sums. This rules out a universal necessary first-pair/target-x equation in
that feature family on the frozen N41 geometry. It is a structural diagnostic
over generated targets, not an ordinary-query yield measurement or an N131
impossibility result. The next method for this geometry must couple at least
two still-free pair domains to the public target or change representation
or degree before a new 120-second N41 gate and any N131 transfer projection.

**N131 W4/m7 one-target formula and decoder gates (2026-10-05):** the exact
projected W4 base now has a seven-leaf S3 circuit with 224,719 variables,
651,973 clause/XOR records, and a 13,077,425-byte XCNF. Checked-Sage
arithmetic passed 33,929 constant-multiplier controls. A complete planted
formula passed all 224,151 recorded gates, every clause, and every XOR row;
the planted decoder also replayed the exact raw-point sum and verified the
cofactor-projected planted-row equation `A·logs = 4·log(Q_planted)`. See the
[formula-size receipt](n131_w4_projected_base_screen_20261005/m7_formula_screen.json)
and [planted circuit/decoder receipt](n131_w4_projected_base_screen_20261005/planted_m7_formula_witness_check_v3.json).
The prepared [single-public-Q runner](n131_w4_projected_base_screen_20261005/run_w4_public_q_gate.py)
rebuilds the target formula inside the query timer and enforces one solver
worker plus a 4-GiB envelope. Its current preflight is
`WAIT_FOR_R3_TERMINAL`: the frozen W2 R3 solver remains live at rank 0/14, so
no W4 SAT query was launched (see its [receipt](n131_w4_projected_base_screen_20261005/preflight_current.json)). Candidate/run IDs remain null; there is still no
ordinary official-Q relation, full log table, DLP, or paired single-target
rho speedup.

**R3 continuation (2026-10-05 18:28 UTC):** PID-specific recheck confirms
the same Sage runner PID 99052 and CryptoMiniSat child PID 99169 are still
alive. The solver log advanced to 3,947,466 bytes; R3 remains `RUNNING` at
rank 0/14 with no result receipt. See the [latest process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261005T182828Z_continuation.json).

**N131 W4/m7 official-Q contended overlap probe (2026-10-05):** a
separate [bounded correctness-only trial](n131_w4_projected_base_screen_20261005/CONTENDED_PUBLIC_Q_M7_PROBE_RESULT.md)
preserved the original live R3 worker and ran one unpinned public-Q query
with one CryptoMiniSat worker under 600 seconds and 4 GiB. The frozen
seven-leaf formula used 224,719 variables and 13,077,425 XCNF bytes. The
query timed out after 599.496 seconds with no model or verified relation;
598.967 seconds were charged to the failed solver attempt. The source,
formula, phase, process, and memory audit passes; observed combined peak
RSS was 325,976,064 bytes and the probe worker was reaped. This ran on a
contended host and supplies only a zero-yield method diagnostic. The
overlap runner predates the later v3 decoder control, but no decoder path
ran because the solver returned no model; future SAT-result trials must use
the v3 decoder-controlled source. R3 remains live at rank 0/14. No
ordinary N131 relation, factor logs, scalar, candidate/run ID, or IC/rho
speedup follows.

**Exact-rationality W4/m7 gate (2026-10-05):** the
[rationality result](n131_w4_projected_base_screen_20261005/EXACT_RATIONALITY_M7_PUBLIC_Q_RESULT.md)
establishes an exact, independently audited 42,997-node SAT predicate for
rational weight-four support. Local positive/negative SAT controls and a
complete planted seven-point circuit and projected-row replay pass. The
official one-target formula has 526,426 variables, 1,850,065 clause/XOR
records, and a 42,281,628-byte XCNF. One unpinned one-worker public-Q query
within a 4-GiB envelope timed out after a 602.387-second interval that
includes formula construction and shutdown; it produced no model or verified
relation. The [terminal audit](n131_w4_projected_base_screen_20261005/diagnostic_runs/public_q_w4_m7_rational_overlap_20261005T191038Z/audit.json)
passed and the pre-existing R3 processes remained live. The host was
contended, so this is a zero-yield method diagnostic, not a controlled
wall-time comparison. The immediate goal remains an independently replayed
ordinary N131 relation within the frozen 600-second, 4-GiB one-worker gate;
the next search should couple the public target to at least two still-free
leaf or pair domains before full assignment. Candidate/run IDs and the
complete DLP/rho speedup remain unknown.

**N131 W4/m7 target-first circuit and decoder gate (2026-10-05):** a
target-first layout places the frozen public `Q` at the first S3 link and
accumulates `-Q + P0 + ... + P5`, with `P6` cancelling the final point by
x-coordinate. Its exact one-target formula has 234,286 variables, 648,150
records, and 12,999,259 bytes, with one fixed-target multiplication verified
on all 131 basis inputs. Relative to the earlier seven-leaf layout it reduces
the formula by 3,823 records and 78,166 bytes, but this predicts no solver
speedup. The planted formula check evaluates every gate, clause, and XOR with
zero failures, then exercises the guarded runner's own sign decoder and
verifies the folded seven-column row against `[4]Q_planted` (see the
[formula receipt](n131_w4_projected_base_screen_20261005/m7_target_first_formula_screen_v2.json)
and [planted decoder receipt](n131_w4_projected_base_screen_20261005/planted_m7_target_first_formula_check_v4.json)).
The [one-target guarded runner](n131_w4_projected_base_screen_20261005/run_w4_public_q_target_first_gate.py)
is prepared, but its
[preflight](n131_w4_projected_base_screen_20261005/preflight_target_first_current_v2.json)
still reports `WAIT_FOR_R3_TERMINAL`; no SAT query was launched. Natural
official-target yield remains unknown, candidate/run IDs remain null, and no
full logs, DLP, or paired single-target rho speedup is claimed.

**N131 W4/m6 target-first screen (2026-10-05):** the same frozen one-target
base also has a six-leaf target-first circuit: `-Q + P0 + ... + P4` is
constrained so `P5` cancels the final partial point. The official-Q formula
has 194,538 variables, 538,737 records, and 10,682,704 bytes, roughly 17%
smaller than m7 in variables and records. Its planted six-point formula
passes every gate, clause, and XOR, and the guarded runner's decoder verifies
the six-column projected row against `[4]Q_planted` (see the
[formula receipt](n131_w4_projected_base_screen_20261005/m6_target_first_formula_screen.json)
and [planted receipt](n131_w4_projected_base_screen_20261005/planted_m6_target_first_formula_check.json)).
The uniform-sum heuristic predicts 2.64 sign-witnesses at arity six, but this
does not establish coverage for the frozen Q. The
[one-target m6 runner](n131_w4_projected_base_screen_20261005/run_w4_public_q_m6_target_first_gate.py)
also returns `WAIT_FOR_R3_TERMINAL` in its
[preflight](n131_w4_projected_base_screen_20261005/preflight_m6_target_first_current.json);
no solver was launched. This is a smaller candidate query to try first after
R3 exits, not a yield or speedup result.

**N131 W4/m6 exact curve-membership alternative (2026-10-05):** a second
single-target m6 formula adds one fresh y-coordinate and the exact curve
equation for every selected raw W4 point. Its formula has 306,888 variables,
952,911 records, and 19,527,148 bytes, versus 194,538 variables, 538,737
records, and 10,682,704 bytes for relaxed-rationality m6. It excludes
irrational supports inside SAT but increases formula size; the solver tradeoff
is unmeasured. A planted six-point check passes every curve-membership and S3
gate, clause, and XOR, and the exact decoder replays the projected row to
`[4]Q_planted` (see the
[formula receipt](n131_w4_projected_base_screen_20261005/m6_curve_member_formula_screen.json)
and [planted receipt](n131_w4_projected_base_screen_20261005/planted_m6_curve_member_formula_check_v3.json)).
The [single-target runner](n131_w4_projected_base_screen_20261005/run_w4_public_q_m6_curve_member_gate.py)
passes source-bound preflight checks but still waits on live R3 (see its
[preflight](n131_w4_projected_base_screen_20261005/preflight_m6_curve_member_current.json));
no query or speedup claim follows.

**N131 W2/m15 linearized S3 formula (2026-10-05):** rewriting
`S3(u,v,w)=0` in characteristic two as
`(v(u+w)+uw)^2 + v(uw) + 1 = 0` preserves the frozen selector domain and
decoder while reducing the same official one-target formula by 23.04% in
clause/XOR records and 23.48% in XCNF bytes (to 939,665 records and
19,881,996 bytes). The eight-planted-sum identity screen, full planted
formula/decoder replay, and XCNF round-trip all pass. The
[linearized runner](n131_w2_m15_linearized_20261005/run_linearized_public_q_gate.py)
now requires matching terminal R3 receipts and confirms recorded process
identities are gone before any query launch. Its checked-launcher
[process-gated preflight](n131_w2_m15_linearized_20261005/preflight_r3_guard_current.json)
still says `WAIT_FOR_R3_TERMINAL`: R3 is `RUNNING` at rank 0/14 and PIDs
99052/99169 match and remain alive. No SAT was launched for the linearized
variant; its natural yield is unknown, IDs remain null, and there is no
verified scalar or paired single-target rho speedup.

**N131 W2/m16 online-query candidate (2026-10-05):** the exact linearized
single-target formula for the same frozen public Q is 21,401,050 XCNF bytes,
7.64% larger than m15. Its full planted 16-point formula check evaluates
485,766 gates and passes every clause and native XOR. A uniform-sum heuristic
predicts about 70,613 decompositions versus about 311 for m15, but this is not
observed coverage. Its canonical candidate ID is
`IC1N131Ckb1fb3668PDP16satRCdirectLAgaussTDdirectISO0hab4081e2ef50`; see the
[candidate manifest](n131_w2_m16_linearized_20261005/candidate_manifest.json),
[m16 screen](n131_w2_m16_linearized_20261005/RESULT.md),
[formula receipt](n131_w2_m16_linearized_20261005/formula_screen.json), and
[planted check](n131_w2_m16_linearized_20261005/planted_formula_witness_check.json).
The exact one-target runner waits for terminal m15 logs and independently
replays them before online timing. No m16 SAT query has launched; the planned
R1 is not a measured run. Current preflight still sees the R3 runner/solver
alive at rank 0/14 (see the
[process-gated receipt](n131_w2_m16_linearized_20261005/preflight_r3_guard_current.json)).
There is no target DLP or paired rho speedup yet.

**R3 continuation and m16 gate refresh (2026-10-05 20:45 UTC):** the checked
Sage m16 preflight again reports `WAIT_FOR_R3_TERMINAL`, rank 0/14, with the
recorded runner PID 99052 and CryptoMiniSat PID 99169 still alive by matching
process identity. The latest solver stdout is 3,990,227 bytes (SHA-256
`f1822018f2b22bc60d2203c382aacc3c694857810343cf4cb00bb3ff0b0c4ea6`),
modified at 20:45:37 UTC; the log reached restart 24,713, while rank remains
0/14. No terminal result or reusable-log artifact exists.
The refreshed receipt is
[`preflight_r3_guard_current.json`](n131_w2_m16_linearized_20261005/preflight_r3_guard_current.json).
No SAT query was launched. Keep the live R3 process intact; the m16 R1 remains
planned, not measured, until R3 has terminal receipts, has exited, and its
rank-14 logs pass independent replay.

The m16 runner now also accounts for an unexpected exception during the
online interval by charging elapsed active SAT/relation/recovery work into
exclusive phases and preserving its active attempt metadata. Four focused
accounting controls pass under the checked Sage launcher. The implementation
snapshot changed, so the current candidate ID is
`IC1N131Ckb1fb3668PDP16satRCdirectLAgaussTDdirectISO0hab4081e2ef50`; its
previous unmeasured manifest is preserved beside the current manifest.

**N131 W4 raw-subgroup and W3 projected-base method gates (2026-10-05):**
The exact raw W4 subgroup census gives `B=5,834,478` and `K=22,269`;
its m7 and m8 formulas pass planted and decoder controls, but their frozen
single-public-Q, one-worker 600-second/4-GiB contended correctness probes
both timed out without models or relations. Their [m7 result](n131_w4_projected_base_screen_20261005/diagnostic_runs/public_q_w4_m7_subgroup_overlap_20261005T194632Z/result.json)
and [m8 result](n131_w4_projected_base_screen_20261005/diagnostic_runs/public_q_w4_m8_subgroup_overlap_20261005T200231Z/result.json)
remain zero-yield diagnostics, not speedup rows.

An alternative exact weight-three projected base has `B=356,320` and
`K=1,360`, independently reconstructed with installed Sage. Raw W3 points
have odd order-four torsion class, so only even summand counts can hit the
order-`r` public target. Its exact rationality predicate is a 1,339-node BDD
audited over every valid gap code, with rational SAT and irrational UNSAT
controls. The W3/m10 public-Q formula has 302,176 variables and 17,810,719
XCNF bytes, and complete planted gate and projected-row decoder controls
pass. The [ordinary public-Q probe](n131_w3_projected_base_screen_20261005/diagnostic_runs/public_q_w3_m10_20261005T203605Z/result.json)
nevertheless timed out at 599.339 seconds without a model; its
[phase/custody audit](n131_w3_projected_base_screen_20261005/diagnostic_runs/public_q_w3_m10_20261005T203605Z/audit.json)
passes and independent replay records `NO_RELATION_RECORDED`. The
[method report](n131_w3_projected_base_screen_20261005/RESULT.md) records the
exact geometry, formula, evidence, and next comparison. Candidate/run IDs
remain null. The first required N131 milestone is still one unpinned,
independently verified ordinary relation within a frozen budget; no factor
logs, recovered scalar, complete IC online time, or paired rho speedup is
established by these formula-size improvements.

**Q1358 N131 2-torsion phi-coordinate Frobenius subspaces (2026-10-05):** a
new one-target proposal uses the characteristic-two 2-torsion map
`phi(P)=1/(x(P)+1)` and the sparse symmetrized `P_phi,3` equation. Checked
Sage verified the map and 96 generated relation controls on the exact
official ECC2K-130 curve. A seeded 9-dimensional phi subspace has 131
Frobenius conjugates with pairwise intersection `{0}`; 15 conjugates supply
the 15 ordered summand domains, while the complete orbit closure gives an
exact signed factor base of `B=69,692`, `K=266`. The planted 15-leaf chain
passes all 14 P_phi,3 links and independent `[4]`-projected row replay. One
official Q has four order-four cofactor lifts; a four-way endpoint selector
keeps the workload at one target and predicts 113.71 decompositions under an
unverified uniform-sum model (28.43 for one exact full-curve endpoint). See
the [Q1358 result](n131_phi_torsion_frobenius_domains_20261005/RESULT.md),
[map screen](n131_phi_torsion_frobenius_domains_20261005/map_p3_screen_v2.json),
and [subspace/row screen](n131_phi_torsion_frobenius_domains_20261005/subspace_row_screen_v3.json).
Its v3 single-target XCNF has 280,734 variables, 216,236 clauses, 208,656
native XORs, 424,892 records, and 15,036,037 bytes. Against the same-workload
W2/m15 linearized S3 formula this is 38.1% fewer variables, 67.8% fewer
clauses, 22.2% fewer XORs, 54.8% fewer records, and 24.4% fewer bytes; the
factor base and decomposition changed together, so these are formula-size
diagnostics, not a solver or IC speedup. The v3 planted formula gate and exact
decoder control pass, including a source-bound [v4 decoder receipt](n131_phi_torsion_frobenius_domains_20261005/q1358_exact_decoder_check_v4.json)
and [independent Sage replay](n131_phi_torsion_frobenius_domains_20261005/q1358_exact_decoder_sage_replay_v4.json).
Candidate/run IDs, measured costs, natural target yield, factor logs, target
DLP, and online speedup remain unknown. The frozen W2 R3 process is still live
at rank 0/14, so no Q1358 SAT query has launched.

The checked [m16 follow-up](n131_phi_torsion_frobenius_domains_20261005/m16_static/RESULT.md)
adds one Frobenius-domain leaf and remains a single-target formula. It has
301,948 variables and 16,196,509 XCNF bytes, 7.72% larger than m15; the
unverified uniform-sum extrapolation is about 60,494 decompositions across the
four cofactor-equivalent endpoints. Its planted formula, exact decoder, and
independent Sage replay pass. This raises estimated coverage only; it says
nothing yet about the ordinary-Q solve or online wall time. The process-gated
[preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/q1358_preflight_r3_guard_m16_v1.json)
still finds R3 active, so no SAT query was launched.

**N131 projected-W3 follow-up (2026-10-05 21:28 UTC):** the exact W3 base
`B=356,320`, `K=1,360` now has four source-checked, one-target public-Q
diagnostic variants under the same nominal one-worker 600-second/4-GiB cap:
serial m8, serial m10, target-first m10, and canonical-pivot m10. All four
passed exact planted formula/decoder controls. Each public-Q solver attempt
timed out without a model or verified relation; every terminal custody audit
passes and independent installed-Sage status is `NO_RELATION_RECORDED`.
The [comparison ledger](n131_w3_projected_base_screen_20261005/w3_proposal_stage_diagnostics.json)
retains failure status, attempts, exclusive target-query phases, memory, and
explicit nulls for useful rank, logs, recovery, rho, and speedup. The
[updated method report](n131_w3_projected_base_screen_20261005/RESULT.md)
links all formula and run receipts. The pivot `[0,1,3]` is chosen before the
target from the rational base, but fixes one SAT leaf and does not clear the
strict fully unpinned milestone. Further small SAT encoding changes should
first be selected with smaller-field complete one-target evidence or a
materially different N131 decomposition kernel. The active N131 relation,
factor-log, scalar, and controlled single-target speedup goals remain open.

**Q1358 exact-model gate (2026-10-05):** the frozen 15-leaf phi-coordinate
one-target v3 formula has a planted circuit receipt and an independent
SAT-primary decoder. The decoder reconstructs exact curve points, resolves
the 13 intermediate phi values by group arithmetic, checks the selected
cofactor endpoint including its possible sign, folds all projected leaves
under the verified Frobenius eigenvalue, and replays the full relation in the
prime-order subgroup. Its v4 planted control is bound to the v3 formula and
passes both right-hand-side signs; a deliberately repeated folded column
combines to a 14-column row. Corrupt chain, invalid leaf code, and wrong
endpoint controls all reject. See the
[Q1358 report](n131_phi_torsion_frobenius_domains_20261005/RESULT.md) and
[v4 decoder receipt](n131_phi_torsion_frobenius_domains_20261005/q1358_exact_decoder_check_v4.json).
The same planted repeated-column witness passed a separate
[installed-Sage replay](n131_phi_torsion_frobenius_domains_20261005/q1358_exact_decoder_sage_replay_v4.json)
of both signed 15-leaf sums and folded rows.
This is a correctness gate, not an ordinary-Q relation or DLP result. Q1358
SAT remains held behind the live W2 R3 process; candidate and run IDs stay
null, and the first unpinned ordinary-relation milestone remains open. The
fresh [checked-Sage preflight](n131_phi_torsion_frobenius_domains_20261005/q1358_preflight_r3_guard_v4.json)
confirms R3 remains `RUNNING` at rank 0/14, its recorded PIDs still match and
are alive, and reusable logs are absent; it launched no SAT solver.

**Q1358 guarded ordinary-query probe (2026-10-05):** the v3 280,734-variable
phi-coordinate formula now has a source-bound one-target SAT probe with a
frozen 600-second, one-worker, 4-GiB envelope and a separate installed-Sage
auditor for any decoded public-Q row. Its latest checked-Sage
[preflight](n131_phi_torsion_frobenius_domains_20261005/preflights/q1358_20261005T215450Z.json)
returns `WAIT_FOR_R3_DRAIN` and confirms no new solver launched because the
recorded W2 R3 runner and CryptoMiniSat processes are still live. The Sage
auditor passes a planted two-sign, repeated-column control, while the
ordinary public-Q relation remains unmeasured and unverified. See the
[Q1358 report](n131_phi_torsion_frobenius_domains_20261005/RESULT.md).

**N23 phi-coordinate full-pipeline control (2026-10-05):** an exact
eight-leaf four-pair MITM control now spans the complete small-field IC path
under the canonical candidate
`IC1N23Ckb1fb506PDP8mitmRCdirectLAgaussTDdirectISO0ha5f1b7682d90`.
Its seeded base has `B=506` actual subgroup points and `K=11` folded columns.
Ten independently replayed zero relations gave rank 10/10 and all factor
logs; one unseen target scalar was recovered and independently replayed.
The one-target IC online interval was 7.330375 ms. A corrected, independently
replayed one-target rho interval on the same point was 166.254667 ms; the
observed ratio 22.68 is exploratory on this contended host, with controlled
speedup unknown and one-pair uncertainty unestimated. The
[measurement row](n23_phi_m8_mitm_pilot_20261005/measurement_R1.json) and
[report](n23_phi_m8_mitm_pilot_20261005/RESULT.md) preserve exact stage
evidence and limitations. Its generator is the first base column, which
simplifies factor-log anchoring; an independent-generator control remains
necessary before using it to select an N131 method. It does not clear the
N131 unpinned ordinary-relation milestone or imply N131 SAT success.

**N23 independent-generator control (2026-10-05):** a second complete
eight-leaf phi/MITM pipeline uses a subgroup generator outside the entire
signed Frobenius base. It required ten verified zero relations for rank
10/11 plus one separately verified `[4]G` relation to reach full rank 11;
all eleven factor logs and one unseen target scalar passed independent Sage
replay. The candidate is
`IC1N23Ckb1fb506PDP8mitmRCdirectLAgaussTDdirectISO0he178cb0382ae`.
One-target IC online time was 3.517917 ms and paired corrected-clock rho time
was 17.437416 ms on the same point. The observed ratio 4.96 is exploratory;
controlled speedup remains unknown on this contended host. The
[measurement row](n23_phi_m8_mitm_independent_g_20261005/measurement_R1.json)
and [report](n23_phi_m8_mitm_independent_g_20261005/RESULT.md) preserve
identity, stage, and audit evidence. Its geometry transfers as a method
control, but direct four-pair MITM at N131 would require over 80 billion
four-sums per side for the Q1358 signed domain; this is an extrapolation,
not a measured N131 cost. The N131 SAT ordinary-relation gate remains open.

**Q1358 complete-base independent audit (2026-10-05):** installed Sage
independently reconstructed the exact degree-131 phi-coordinate field,
all 131 conjugate subspaces, the 266 folded columns, and all `B=69,692`
usable subgroup points before sign/Frobenius folding. Its enumerated point
set SHA-256 exactly matches the codegen geometry receipt. The
[Sage audit](n131_phi_torsion_frobenius_domains_20261005/sage_full_phi_base_audit.json)
is now a required input to the source-bound Q1358 ordinary-query preflight;
the independent [official-Q fiber audit](n131_phi_torsion_frobenius_domains_20261005/sage_official_q_fiber_audit.json)
also checks subgroup membership, all four cofactor-equivalent endpoints, and
the formula's selector order. Both audits are bound into the
[latest guarded receipt](n131_phi_torsion_frobenius_domains_20261005/preflights/q1358_20261005T230427Z.json), which
still returns `WAIT_FOR_R3_DRAIN` with no SAT solver launched. This closes
base and endpoint-identity uncertainty but does not establish an ordinary relation,
factor logs, a scalar, or N131 online speed.

**N131 phi-subspace search (2026-10-05):** a frozen 128-seed search for the
same 9-dimensional, 15-position phi/Frobenius method first selected seed
`2026100502068` with `K=282`; a deterministic 864-trial local replacement
search then reached `K=318` and `B=83,316` actual subgroup points, versus
Q1358's 266 and 69,692. Independent Sage reconstructed the full point set
and matched its hash. The official one-target Q formula and complete planted
control pass at 15,001,388 XCNF bytes, 34,649 bytes below the frozen Q1358
formula. The 14.56x uniform-sum relation-count multiplier is a heuristic,
not a measured ordinary-Q yield or speed. The [search and audit report](n131_phi_torsion_frobenius_domains_20261005/subspace_seed_screen/RESULT.md)
retains all trials, exact point-set hashes, and formula receipts. This
follow-up is unpromoted with `candidate_id: null`; it must still pass an
ordinary-Q relation probe after the live R3 process drains, then full
factor-log, scalar, and paired-rho gates.

**N131 318-column ordinary-Q readiness (2026-10-05):** the selected-base
exact decoder now passes planted two-sign, repeated-column, corrupt-chain,
invalid-selector, and wrong-endpoint controls; independent installed Sage
replays both signed folded rows. A separate ordinary-row auditor passes its
planted self-test. The [source-bound one-target preflight](n131_phi_torsion_frobenius_domains_20261005/subspace_seed_screen/preflights/local318_20261005T232401Z.json)
freezes one worker, 600 seconds, 4 GiB combined RSS, and at most four SAT
models, but returns `WAIT_FOR_R3_DRAIN` while the recorded W2 R3 runner and
solver remain alive. It launched no SAT solver. The
[proposal report](n131_phi_torsion_frobenius_domains_20261005/subspace_seed_screen/RESULT.md)
links all controls and the guarded runner; no ordinary relation, useful rank,
factor logs, scalar, or N131 online speed is yet measured.
The [nonlaunching runner build control](n131_phi_torsion_frobenius_domains_20261005/guarded_probe_build_control_v1.json)
found and fixed a six-value formula-builder unpacking mismatch in both
guarded probes, then reconstructed their frozen official-Q XCNFs byte-for-byte.

**N131 318-column same-base circuit variant (2026-10-05):** a greedy basis
change keeps the exact same 512 phi elements, 318 folded columns, and
`B=83,316` points; an independent Sage audit confirms the same subspace and
usable lift count. The official-Q XCNF shrinks from 15,001,388 to 14,814,227
bytes (1.25%) with 116 fewer variables and native XORs, and its planted row
control passes. The [basis and formula report](n131_phi_torsion_frobenius_domains_20261005/subspace_seed_screen/RESULT.md)
labels this a static circuit variant, not a measured ordinary-query or speed
result. The frozen 318-column ordinary-Q probe still uses the original basis.

**N131 318-column 16-leaf follow-up (2026-10-05):** the same independently
audited `B=83,316` base and official target now have a source-bound m16 XCNF
and guarded one-target probe. The 15,957,562-byte formula is 7.72% larger
than the optimized-basis m15 formula; the uniform-sum model count rises by
636 to about 1.05 million possible decompositions across the four
cofactor-equivalent endpoints. The [m16 controls and comparison](n131_phi_torsion_frobenius_domains_20261005/subspace_seed_screen/RESULT.md)
include a complete planted circuit check, exact decoder negatives,
independent checked-Sage group replay, independent auditor self-test, and
byte-identical runner rebuild. The [guarded preflight](n131_phi_torsion_frobenius_domains_20261005/subspace_seed_screen/preflights/local318_m16_20261005T234516Z.json)
still reports `WAIT_FOR_R3_DRAIN` with no solver launched. The large model
count is a heuristic, not measured ordinary-Q yield or solver time; the m16
variant remains a proposal with null candidate/run IDs and no scalar or
speedup claim.

**N23 ordinary-target SAT method-selection result and N131 seed repair
(2026-10-06):** on one frozen N23 public point and exact `B=506`, `K=11`
factor base, m6 and m7 chained-phi SAT formulas both parsed but reached their
60-second/1-GiB solver cap without a model. Exact group meet in the middle
found decompositions for both on that same point, and installed Sage
independently verified each signed folded row. The [N23 result](n23_phi_sat_summand_gate_20261005/RESULT.md)
preserves the first invalid-seed CLI failures, raw R2 timeouts, and their
corrected status audit. This is smaller-field evidence of a solver bottleneck,
not an N131 yield or speed claim. The failure exposed oversized
CryptoMiniSat seeds in all three prepared N131 phi probes. Their old sources
are preserved, the corrected runners use bounded seeds and distinguish CLI
errors from watchdog timeouts, and the [two m15 build controls](n131_phi_torsion_frobenius_domains_20261005/guarded_probe_build_control_v2.json)
plus [m16 build control](n131_phi_torsion_frobenius_domains_20261005/subspace_seed_screen/local_m16_guarded_probe_build_control_v2.json)
rebuilt their respective official-Q formulas byte-for-byte. Fresh no-launch
preflights still find the W2 R3 runner and solver live; no new ordinary N131
relation, factor logs, scalar, or speedup is claimed.
The same N23 ordinary witnesses also satisfy the exact SAT XCNFs. A blind
first-pair-guided m6 run tried 12 signatures and timed out; its known valid
pair was at untried index 41. Even when that valid pair was supplied in a
separate planted conditional run, SAT again reached 60 seconds without a
model. Fully pinning the 118 primary bits made CryptoMiniSat return SAT and
replay both signed rows. These controls narrow the immediate algorithmic
need to stronger search structure than one indexed pair; they do not measure
N131 behavior.
The source-bound N23 m6/m7 XCNFs were also translated to plain CNF with an
exhaustively checked XOR gadget. CaDiCaL and Kissat each solved the fully
pinned witnesses, but all four unpinned ordinary-target searches reached
their 60-second limits without a model. The [independent panel readback](n23_phi_sat_summand_gate_20261005/plain_cnf_backend_panel_audit_v1.json)
therefore keeps the next method target on stronger decomposition structure,
not a simple SAT backend substitution. These are smaller-field diagnostics,
not N131 yield or CPU speed claims.

**Exact pair-join method-selection control (2026-10-06):** on the same frozen
N23 public target and B=506/K=11 base, supplying the first three or four
leaves of an independently verified m6 witness still left CryptoMiniSat
without a model at each 60-second cap. A blind, target-independent exact
2+2+2 pair index then found a valid six-leaf relation after 384 joined
first/second-pair combinations; [independent installed Sage](n23_phi_sat_summand_gate_20261005/runs/pair_join_R1/sage_audit.json)
verified both signed folded rows. The [method report](n23_phi_sat_summand_gate_20261005/RESULT.md)
and [proposal-label correction](n23_phi_sat_summand_gate_20261005/proposal_identity_correction_v1.json)
preserve all raw timeout and relation artifacts. The new comparison labels
are `Q1435` for planted-prefix SAT and `Q1436` for blind pair joining. This
supports direct pair-state joining as a method change on N23, but extending
three pairs to N131 m16's eight pairs still requires a bounded higher-arity
join or algebraic propagation. It supplies no N131 relation or speed claim.

**Q1358 sparse-seed m16 follow-up (2026-10-05):** a deterministic static
screen tested 120 sparse ONB generator subspaces; all passed the rank-18
Frobenius-disjointness check. The selected basis lowers the circuit proxy
from 1,337,968 to 389,744, then passes exact geometry and independent Sage
audits on the official one-target workload. It has 71,788 actual
nonidentity subgroup points before sign/Frobenius folding and 274 folded
columns. Its 16-leaf official-Q formula has 297,827 variables, 232,553
clauses, 220,253 native XOR rows, and 11,274,405 bytes: 25.0% smaller than
the m15 v3 formula by serialized bytes. The
[formula receipt](n131_phi_torsion_frobenius_domains_20261005/m16_static/phi_formula_screen_m16_sparse_seed_v1.json),
[base audit](n131_phi_torsion_frobenius_domains_20261005/m16_static/sage_sparse_seed_full_base_audit_v1.json),
[Q-fiber audit](n131_phi_torsion_frobenius_domains_20261005/m16_static/sage_sparse_seed_official_q_fiber_audit_v1.json),
and planted exact-decoder controls pass. The 97,197 four-endpoint decomposition
count is only an unverified uniform-sum model-count heuristic; it is not fixed-Q
coverage, relation yield, solver time, or a speedup.

The source-bound [m16 single-target probe](n131_phi_torsion_frobenius_domains_20261005/m16_static/run_q1358_public_q_m16_sparse_probe.py)
is held behind the active W2 R3 drain and then a terminal, independently
audited m15 public-Q result. Its latest checked-Sage
[preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/preflights/q1358_20261006T000845Z.json)
returns `WAIT_FOR_R3_DRAIN`, matching live process identities 99052 and 99169;
no SAT query was launched. The preceding m15 probe's latest preflight is
also `WAIT_FOR_R3_DRAIN` at
[its receipt](n131_phi_torsion_frobenius_domains_20261005/preflights/q1358_20261006T005907Z.json).
Thus this is the strongest static single-target IC lead so far, but no ordinary
relation, factor logs, recovered scalar, online time, or ECC2K-130 speedup has
been measured.

**Frozen sparse-seed m16 full pipeline (2026-10-06):** the exact B=71,788,
K=274 sparse-seed base and 16-leaf solver wiring now have a complete,
source-bound one-target candidate manifest:
`IC1N131Ckb1fb71788PDP16satRCdirectLAgaussTDdirectISO0h758917c155b2`.
Its precomputation requests one generated relation target at a time until all
274 factor-base logs are verified, then its online workload is exactly the
single supplied public Q. It records solver launch and formula-input parsing
outside the target-dependent compute interval. The exact geometry, independent
Sage base and Q-fiber audits, formula/decoder controls, and planted
base-to-row integration pass. The checked-Sage
[full-pipeline preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/single_target_preflights/sparse_m16_20261006T021249Z.json)
returns `WAIT_FOR_R3_DRAIN` and confirms that the existing m15 R3 processes
are still alive; no new solver was launched. Its fresh process receipt records
about 89,878 seconds of solver CPU time, rank 0/14, and no terminal result.
The stricter preflight also checks the encoded candidate ID, exact field/curve
equality, and that implementation and input digests in the manifest match the
current sources and controls. The
[candidate manifest](n131_phi_torsion_frobenius_domains_20261005/m16_static/sparse_seed_candidate_manifest_v1.json),
[protocol](n131_phi_torsion_frobenius_domains_20261005/m16_static/sparse_seed_protocol_v1.json),
and [independent run auditor](n131_phi_torsion_frobenius_domains_20261005/m16_static/audit_sparse_seed_single_target_result.py)
are ready. Candidate identity is frozen, but no measured run ID, natural
relation, full-rank logs, recovered scalar, online time, paired rho result, or
speedup exists yet.

**N83 packed wide-root-index scale model (2026-10-05):** the additive
[packed-index design](../koblitz-n83-index-design-20260929/N83_PACKED_WIDE_ROOT_INDEX_MODEL_20261005.md)
extends Q1106's d10/d11 layout estimates to larger bases with an 11-byte
canonical 83-bit root key and a packed state/root/shift
descriptor. With two root records per pair state, the exact Q1104 d10/d11
geometries give raw table payloads of 0.556/2.553 GiB; the Q1102 B8M/B32M
and Q1325 geometries give 6.55/111.04/104.05 TB. The d11 two-copy sort
scratch model is 5.107 GiB before other working memory. These are storage
models, not built indexes or measured RSS. Gross `B^4/r` and `B^5/r` tuple
scales are preserved separately from observed relation yield. Its fixed-width
record codec passes four serialization boundary checks, recorded in the
[control receipt](../koblitz-n83-index-design-20260929/packed_wide_codec_control_20261006.json).
This does not test N83 field arithmetic or index construction. The design
identifies 82-bit subgroup scalars, up to 164-bit modular products, and
42-bit B32M state IDs; packing leaves the `K^2*83` enumeration and does not
establish a faster-than-rho algorithm. At this audit, frozen R3 process IDs
99052 and 99169 were still live and the precomputation receipt remained
`RUNNING`, rank 0/14. No new N83 arithmetic or solver job was launched; after
R3 is terminal, the next gate is a field-width-safe planted-complete PDP5
solver before ordinary-query measurement.

**Sparse-seed m16 runner setup audit (2026-10-06):** the checked-Sage audit
[receipt](n131_phi_torsion_frobenius_domains_20261005/m16_static/sparse_seed_runner_setup_audit_v1.json)
called the frozen candidate runner's actual setup function and reproduced its
`B=71,788` point set, `K=274` folded columns, and exact set digest. The
target-independent setup diagnostic took 8.328455875 seconds; it is separate
from the one-target online metric and launched no solver. The latest full
candidate [preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/single_target_preflights/sparse_m16_20261006T021249Z.json)
still found the existing m15 R3 solver live at rank 0/14, so the N131 relation
and DLP gates remain open.

**N83 unordered-support count correction (2026-10-06):** the exact Q1104
five-summand `B^5/r` model counts ordered tuples, so its 1.247/56.439 d10/d11
values overcount each distinct five-point relation support by up to 120
permutations. The additive [first-moment audit](../koblitz-n83-index-design-20260929/N83_UNORDERED_RELATION_YIELD_AUDIT_20261006.md)
uses `binom(B,5)/r` for the exact mean number of distinct supports under a
uniform target: 0.0103936 for d10 and 0.470297 for d11. The corresponding hit
probabilities are bounded above by 1.04% and 47.03%; the earlier Poisson
predictions are not valid coverage estimates. Q1105's planted cofactor-lift
controls are unaffected, but do not estimate ordinary yield. The calculation
reproduces Q1325's independently recorded `binom(B,4)/r = 15,869.003` mean.
This changes the next useful N83 base-size check: after R3 is terminal and
audited, materialize/replay Q1104 d12 and recalculate its unordered support
count before freezing another PDP5 control. No N83 query has been launched.

**Q1104 d12 pre-materialization screen (2026-10-06):** the additive
[prediction-only screen](../koblitz-n83-index-design-20260929/N83_D12_PREMATERIALIZATION_SCREEN_20261006.md)
uses exact d10/d11 base receipts to set a sensitivity threshold, not a d12
count prediction. Under the explicit `B=166K` assumption, `K=1,182` is the
first folded-column count whose unordered five-point first moment reaches one.
Scenarios `K=2,000` and `K=2,178` model 9.89 and 11.73 GiB raw root tables,
with 19.79 and 23.47 GiB two-copy sort scratch; these sizes inherit the
two-roots-per-state model and are not measured memory. The exact d12 base must
be materialized and independently replayed before any PDP5 control. The
[calculator](../koblitz-n83-index-design-20260929/screen_n83_d12_threshold.py)
and [JSON receipt](../koblitz-n83-index-design-20260929/N83_D12_PREMATERIALIZATION_SCREEN_20261006.json)
contain the scenarios and their assumptions. R3 processes 99052/99169 were
still live at this screen; no N83 Sage or query run was started. A d12-only
[protocol](../koblitz-n83-index-design-20260929/runs/q1104_seed_subspace_d12_20261006/protocol.json),
[producer](../koblitz-n83-index-design-20260929/q1104_seed_subspace_d12.py),
and [independent Sage verifier](../koblitz-n83-index-design-20260929/verify_q1104_seed_subspace_d12_sage.py)
are now prepared and syntax-checked. Both check the exact R3 process marker and
refuse to run while it is live. The post-run
[receipt/count auditor](../koblitz-n83-index-design-20260929/audit_q1104_d12_result.py)
will validate both runtime records and calculate exact support/storage counts
from independently replayed `B` and `K`. No Sage run receipt or d12 base exists
yet.

**Sparse m16 exact pair-index transfer gate (2026-10-06):** a checked-Sage
target-independent `Q1437` build materialized one exact adjacent-pair table
for the official N131 sparse phi base: 548 signed choices per position,
300,304 raw states and distinct pair sums, and a 12,012,160-byte sorted
binary artifact. The [independent Sage audit](n131_phi_torsion_frobenius_domains_20261005/m16_static/pair_index_R1/sage_audit.json)
read back all signed selector pairs and independently checked sampled sums
and all seven Frobenius-rotated pair positions. The
[exact membership-oracle control](n131_phi_torsion_frobenius_domains_20261005/m16_static/pair_index_R1/oracle_check_v1.json)
passed all 300,304 stored-sum lookups and 2,072 rotated samples. The
[scaling receipt](n131_phi_torsion_frobenius_domains_20261005/m16_static/pair_index_R1/pair_join_scaling_v1.json)
shows that a literal Cartesian join of only two such pair lists has
90,182,492,416 raw combinations and needs at least 3.15 TB even for bare
35-byte point keys. That rules out this literal table construction under
4 GiB; it does not rule out a compressed, streaming, or algebraic joint
solver. The [m16 report](n131_phi_torsion_frobenius_domains_20261005/m16_static/RESULT.md)
keeps `Q1437` as a proposal with null candidate/run IDs. No ordinary N131
relation, factor logs, target scalar, or online speedup follows from this
target-independent index.

**Sparse m16 independent base-auditor control (2026-10-06):** the checked-Sage
[control receipt](n131_phi_torsion_frobenius_domains_20261005/m16_static/sparse_seed_independent_base_auditor_control_v1.json)
builds the candidate's actual runtime base, then independently reconstructs
all signed 131-step Frobenius entries and coefficients in Sage. It matches all
71,788 points, 274 representatives, and the frozen point-set digest. This
validates the future run auditor's base-table checks; it does not produce an
ordinary relation, factor logs, or a DLP.

**Windowed-phi method gate (2026-10-06):** `Q1438` used four disjoint
Frobenius-rotation windows on the exact N23 phi base and found a blind
ordinary-target relation after 46 right-pair states. Its independent
installed-Sage [audit](n23_phi_sat_summand_gate_20261005/runs/windowed_m4_join_R1/sage_audit.json)
passed. The same target's exact windowed four-leaf `P_phi,3` SAT circuit
passed a complete known-witness clause/XOR check, but its unpinned
[solver run](n23_phi_sat_summand_gate_20261005/runs/windowed_m4_sat_R2/result.json)
timed out without a model at the 60-second/1-GiB one-worker gate. The
source-bound N131 [Q1440 capacity receipt](n131_phi_torsion_frobenius_domains_20261005/m16_static/m11_windowed_static/support_model_v3.json)
counts ten 12-position and one 11-position windows over the audited
71,788-point sparse phi base. It has 11 leaves and nine chain partials;
the uniform-sum heuristic suggests about 1,339 representations over four
cofactor endpoints, but fixed-Q coverage and solver cost are unmeasured.
Its conditional random-prefix gate bounds a 600-second final-pair lookup
strategy below `3.50×10⁻²⁰` even at one nanosecond per probe, assuming
uniform prefix residuals. That bound does not apply to adaptive
target-coupled search.
Keep Q1440 a proposal with null candidate/run IDs. The next method gate is
an unpinned, independently verified small-field target relation from a
target-coupled solver with a credible N131 600-second/4-GiB capacity
preflight; generic windowed phi SAT has not cleared that gate. The primary
goal remains one ordinary N131 relation, then verified factor logs and a
fresh target DLP with paired one-target rho online timing. No N131 relation
or speedup has been obtained.

**Q1440 literal window-join capacity gate (2026-10-06):** the exact
[capacity receipt](n131_phi_torsion_frobenius_domains_20261005/m16_static/m11_windowed_static/literal_join_capacity_v1.json)
counts the best raw 5/6 split of the eleven disjoint rotation windows. The
side lists contain 12,297,278,894,166,245,376 and
74,127,997,174,034,127,126,528 group sums, so 35-byte point keys alone would
need about `4.30×10^20` and `2.59×10^24` bytes. The largest two-window pair
index is 43,243,776 states and would need 1.57 GiB for bare keys plus
descriptors; this fits as a primitive but leaves nine windows unresolved.
This rules out literal complete-side materialization under 4 GiB, not an
algebraic or compressed solver. No N131 formula or solver was built.

**N131 W2/m15 R3 verified live sample (2026-10-06 02:27 UTC):** the
[10-second process receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261006T022731Z_continuation.json)
rechecked runner and CryptoMiniSat process identities and observed both alive.
The solver added 3.20 CPU seconds in the sample while stdout stayed unchanged;
the saved relation progress remains rank 0/14 and no terminal result exists.
The checked-Sage [m16 preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/single_target_preflights/sparse_m16_20261006T022243Z.json)
still returns `WAIT_FOR_R3_DRAIN`; no competing SAT solver was launched.

**R3 process-gate readback (2026-10-06):** the newest R3 interval
observation nested process entries under `end`, while the frozen sparse-m16
preflight reads top-level `processes`. Its first fresh preflight therefore
returned `WAIT_FOR_R3_PROCESS_OBSERVATION`, a safe uncertainty rather than a
terminal result. The [flat identity observer](n131_phi_torsion_frobenius_domains_20261005/m16_static/observe_r3_flat_for_preflight.py)
rechecked both original PID creation times and confirmed the runner and
CryptoMiniSat were still live. A [second preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/single_target_preflights/sparse_m16_20261006T024025Z.json)
returned `WAIT_FOR_R3_DRAIN`; neither preflight launched a solver. The
existing R3 job remains the authoritative N131 process to observe.

**Latest sparse-m16 gate refresh (2026-10-06 02:50 UTC):** the checked-Sage
[preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/single_target_preflights/sparse_m16_20261006T025006Z.json)
again verified the original R3 process identities as live and returned
`WAIT_FOR_R3_DRAIN`; `solver_launched` is false. No N131 relation, factor-log
rank, DLP, or paired online speedup has been established.

**Q1441 N23 three-leaf audit (2026-10-06):** a blind three-window join on
exactly one supplied N23 target produced 17 oriented relations across 14 of
23 Frobenius orientations, or four unique rows after inverse-Frobenius
folding. The independent installed-Sage census
([audit receipt](n23_phi_sat_summand_gate_20261005/runs/windowed_m3_orbit_join_R1/sage_audit.json))
passed: 30,976 left-pair states, 30,872 distinct sums, and exact per-orientation
counts match. The raw producer remains marked pending because the audit is a
separate artifact. This is a small-field correctness result with null
candidate/run IDs, no solver, and no complete online time; it gives no N131
yield or speedup. The N131 R3 SAT solver remains the only live SAT job, and
the N83 d12 base enumeration gate is still closed until its terminal record
is independently audited.

**N23 three-leaf solver gate and N131 orbit correction (2026-10-06):** the
verified `Q1441` census includes an orientation-zero relation for the same
supplied public point. Its [Q1442 phi circuit](n23_phi_sat_summand_gate_20261005/runs/windowed_m3_sat_R1/formula_receipt.json)
passed a complete known-witness clause/XOR check, but the unpinned
[CryptoMiniSat run](n23_phi_sat_summand_gate_20261005/runs/windowed_m3_sat_R2/result.json)
timed out without a model at 60 seconds/1 GiB. The equivalent
[Q1443 plain-CNF panel](n23_phi_sat_summand_gate_20261005/runs/windowed_m3_plain_cnf_R1/result.json)
had planted SAT models from both CaDiCaL and Kissat; each ordinary public-Q
run reached the solver self-limit inside its 60-second parent envelope
without a model. The exact
[Q1444 N131 m10 overlap model](n131_phi_torsion_frobenius_domains_20261005/m16_static/m10_orbit_static/overlap_model_v1.json)
counts ten disjoint rotation windows and all 131 overlaps. Its uniform-sum
heuristic totals about 69.8 oriented representations over the one public
target's Frobenius orbit, but exact rotation geometry gives an average of
23.76 valid shifts per valid window pattern; orientation trials are not
independent. Fixed-Q coverage, SAT cost, and N131 yield remain unknown.
The N23 solver failures do not justify an N131 generic SAT launch. Continue
to seek a target-coupled multi-pair solver under the 600-second/4-GiB gate.

**Q1446 specialist SAT check (2026-10-06):** the exact N23 three-window
public-Q circuit was also run through WDSat with XOR-Gaussian propagation
and endpoint/leaf/rotation branch priority. The [corrected R2 receipt](n23_phi_sat_summand_gate_20261005/runs/windowed_m3_wdsat_R2/result.json)
shows a pinned audited model satisfying all XCNF clauses and XOR rows,
followed by an unpinned 60-second/1-GiB timeout without a model. The
[R1 verifier-wrapper failure](n23_phi_sat_summand_gate_20261005/runs/windowed_m3_wdsat_R1/result.json)
is preserved. The raw rows used `Q1445` before a concurrent
[identity correction](n23_phi_sat_summand_gate_20261005/windowed_m3_wdsat_proposal_identity_correction_v1.json)
assigned this comparison `Q1446`; `Q1445` remains the N131 three-leaf
transfer screen below. The host is unisolated, and neither row is a complete IC
online-time result. Together with the CryptoMiniSat, CaDiCaL, and Kissat
controls, this closes backend-only promotion of the m10 orbit proposal to
an N131 query; early target-coupled multi-pair propagation remains required.

**Q1445 direct three-leaf N131 transfer screen (2026-10-06):** the
[source-bound receipt](n131_phi_torsion_frobenius_domains_20261005/m16_static/q1445_m3_transfer_gate.json)
uses the independently audited sparse base (`B=71,788`, subgroup order
`680564733841876926932320129493409985129`) and the one-target Q1440
windowing contract. Even the generous ordered `B^3` count gives only
`7.13×10⁻²³` expected hits over the four cofactor endpoints and 131
Frobenius orientations under the uniform-sum model. A balanced 44/44/43
window join has `13,699,839,650,816` ordered tuples and `2.64×10⁻²⁴`
expected hits; its 581,388,544-state pair index has at least 11.37 GiB of
raw x-key-plus-descriptor payload. This rejects the literal Q1441-style
three-leaf transfer as an N131 candidate, while leaving compressed or
algebraic target-coupled solvers open. The gate is heuristic/capacity-only:
there is no fixed-Q yield, solver, online time, or speedup.

**R3 process refresh (2026-10-06 03:26 UTC):** the latest
[flat observer receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261006T032630384986Z_flat_guard.json)
matched both recorded PIDs as active and found no terminal result. The
existing SAT process remains the sole live SAT job; no batch workload or
competing solver was launched.

**R3 follow-up (2026-10-06 03:39 UTC):** a second fresh
[flat observer receipt](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_observation_20261006T033926435711Z_flat_guard.json)
again matched both processes as active and reported no `result.json`. The
single R3 solver remains in flight; the existing one-target workload is
unchanged.

The associated progress file still reads `rank=0/14`, `status=RUNNING`; the
solver stdout last changed at 03:18 UTC (restart counter 28,634). A direct
03:39 UTC process sample measured about 93,707 solver CPU seconds and
252,755,968 bytes RSS. No factor-log row or terminal result has been
recorded.

**Q1447 static W2/m15 multiplier-cutoff screen (2026-10-06):** the source-bound
[screen](n131_w2_m15_leafcutoff_gate_20261006/RESULT.md) compares exact XCNF
counts for one generic degree-131 S3 link, varying only the Karatsuba leaf
cutoff and using both the original and the already-tested affine-XOR emitter.
The affine emitter at cutoff 1 reduces per-link clauses from 70,704 to 33,732
and total constraints (clauses plus XOR rows) from 81,991 to 58,887 relative
to cutoff 12; it also raises native-XOR rows from 11,287 to 25,155 and
variables from 35,205 to 36,749. Cutoff 3 reduces total constraints by 17.0%
with a smaller XOR-row increase. Independent field-arithmetic replay passed
nine seeded triples across cutoffs 1, 5, and 12. This is a static circuit
screen, not a full 15-summand formula, a solver result, an ordinary relation,
or a speedup claim; Q1447 candidate and run IDs remain null. The proposed
next gate is a planted control plus ordinary small-field check for affine-XOR
cutoffs 1 and 3 before any N131 solver run.

**R3 process refresh (2026-10-06 04:32 UTC):** direct `psutil` inspection
matched the original runner and CryptoMiniSat PIDs and creation times. Both
remain alive on the frozen precomputation `query.xcnf`; progress is still
`RUNNING`, rank `0/14`, and no terminal `result.json` exists. The solver had
93,827.9 CPU seconds and 263,979,008 bytes RSS at the sample. No competing SAT
job was launched.

**Target-coupled pair-domain control (2026-10-06):** the frozen
[Q20261006043102 Bloom-filter join](q1448_pair_bloom/RESULT.md) found an
unpinned eight-point relation on the ordinary N41 W6 public target in
6.293 seconds of target-dependent stage time; an independent checked-Sage
audit verified subgroup membership, eight distinct folded columns, and the
exact sum. A compact target-independent bitmap rejected 505,678 of 513,088
examined first-two-pair residuals while the last two pair domains remained
free. The literal N131 transfer fails its source-bound 600-second work gate:
at least 1,186,709,766,821,143,716,096 group sums would be needed just to
build that bitmap. The complementary
[Q20261006043101 residual-oracle goal](Q1447_RESIDUAL_ORACLE_GATE.md)
therefore still requires symbolic two-pair compression or target-adaptive
generation. Raw Q1448 receipts and the earlier Q1447 draft retain their
original labels, with hash-bound identity corrections beside them. Neither
control supplies an ordinary N131 relation, logs, a recovered DLP, or an
IC/rho speedup. The existing R3 solver remains separate.

**Q1449 full public-Q affine cutoff gate (2026-10-06):** the
[source-bound receipt](n131_w2_m15_leafcutoff_gate_20261006/full_public_formula_gate.json)
emits the exact one-target ECC2K-130 public-Q W2/m15 formula at affine-XOR
Karatsuba leaf cutoffs 12, 1, and 3. The cutoff-12 rebuild matches its pinned
affine reference SHA-256; all three retained XCNFs pass independent streamed
checks of their digest, header, clauses, and native-XOR row count. At cutoff 1,
the complete formula has 874,791 constraints versus 1,201,385 at cutoff 12
(27.19% fewer), with 110.91% more native XOR rows. Cutoff 3 has 1,010,707
constraints (15.87% fewer) and 54.51% more XOR rows. This is a static
formula-size result only: no solver was launched, `candidate_id` and `run_id`
remain null, and ordinary relation yield, reusable logs, the fresh target DLP,
paired one-target rho time, and speedup are unknown. The R3 one-target solve
remained live during these emissions. Next are planted formula/group controls
and an ordinary small-field single-target comparison before any new N131 SAT
solve.

**Q1450 planted full-chain IR control (2026-10-06):** the
[source-bound control](n131_w2_m15_leafcutoff_gate_20261006/planted_chain_control.json)
formed one synthetic target as a sum of 15 distinct usable W2 base points
under its own canonical workload `Wd43ea35f8a62`, then replayed the ordered
14-link S3 chain directly through the IR at cutoffs
12, 1, and 3. All 1,834 root equations were zero for each cutoff, and the
leaves obey exact weight-two membership and ordering. This validates one
planted arithmetic chain, not the XCNF gate encoding, ordinary relation yield,
or the published ECC2K-130 target. No solver was launched. After R3 drains, the
remaining gates are a planted XCNF constraint check and an ordinary small-field
single-target comparison before considering a new N131 solve.

**R3 process refresh (2026-10-06 05:05 UTC):** direct `psutil` inspection
again matched runner PID 99052 and CryptoMiniSat PID 99169 to their frozen
command lines and creation times. The solver remains on the existing one-target
precomputation query; no terminal result or recovered relation is present.
Its CPU use was 96,304.4 seconds and RSS was 493,846,528 bytes. The solver log
continued updating at 05:06 UTC (restart counter 28,683), while the run record
still reports `RUNNING`, rank 0/14. No second solver was launched during the
formula gate.

**R3 live process snapshot (2026-10-06 05:15 UTC):** the new
[run-bound snapshot](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_snapshot_20261006T051542Z.json)
again confirms the original runner and solver identities on the same one-target
precomputation query. The process sample shows 96,759.7 solver CPU seconds and
528,564,224 bytes RSS; the solver log advanced at 05:14:59 UTC. The run record
still has rank 0/14 and no terminal result. No other SAT solver was started.

**Q1449 planted complete-XCNF model follow-up (2026-10-06):** the
[frozen direct evaluator](n131_w2_m15_leafcutoff_gate_20261006/planted_model_evaluator_result_v2.json)
used a previously independent-Sage-replayed 15-leaf W2 fixture and assigned
every auxiliary variable in the full affine-XOR formulas at cutoffs 1 and 3.
All 1,834 functional roots and all 564,279/783,222 CNF clauses and
310,947/227,917 native-XOR rows passed, respectively. A separate
[streaming audit](n131_w2_m15_leafcutoff_gate_20261006/planted_model_independent_audit.json)
read the saved XCNFs and packed models and found zero failures for both.
This fixture has only ten distinct folded columns and is a correctness
control, not an ordinary relation or useful matrix row. No SAT solver was
launched. The remaining method gate is an unpinned ordinary small-field
solver comparison before any cutoff variant is promoted to an N131 query;
the live R3 job remains authoritative for the current N131 attempt.

**Q20261006052200 paired N41 cutoff preflight (2026-10-06):** the
[frozen W2/m8 control](n41_w2_m8_leafcutoff_gate_20261006/RESULT.md) holds one
previously independently replayed N41 public target and its exact `B=164`,
`K=2` factor base fixed while changing only the affine-XOR Karatsuba leaf
cutoff. All three planted S3 chains passed 287/287 root checks, and independent
XCNF readback passed. A later complete-model audit checked every clause and
XOR row under the same independently replayed known row, with zero failures
for all three cutoffs. Cutoffs 12, 1, and 3 produce 94,443, 62,669, and
72,534 total constraints, respectively. This is a static method-selection
preflight, not a solver result or ordinary relation. The bounded next decision
is a same-target, one-worker, 120-second/4-GiB unpinned SAT comparison after
R3 drains, with independent Sage replay
of any found row. If no cutoff clears that N41 gate, stop treating circuit-size
tuning as a route to the N131 relation and prioritize target-coupled pair-domain
elimination. Candidate and run IDs stay null for this proposal.

**Q20261006052200 executable gate follow-up (2026-10-06):** the
[ordinary-query runner and solver protocol](n41_w2_m8_leafcutoff_gate_20261006/RESULT.md)
are frozen. Its saved offline preflight rebuilt all three exact public XCNFs,
checked the planted complete models, and replayed signed points and folded rows
to the public target. The solver entry point rejected a deliberate launch while
the original R3 runner/worker identities remained live, before creating a run
directory; no competing SAT worker ran. The next executable action remains the
120-second/4-GiB unpinned N41 comparison after R3 drains, followed by
independent replay of any ordinary row. No N131 decomposition, factor logs,
target DLP, or IC/rho speedup is established by this gate.

**Q1451 second one-target planted-XCNF control (2026-10-06):** the
[source-bound control](n131_w2_m15_leafcutoff_gate_20261006/planted_xcnf_control.json)
uses its own canonical synthetic workload `Wd43ea35f8a62`; it is a single
target made from 15 distinct usable W2 base points. Cutoffs 12, 1, and 3 each
produce a complete XCNF and packed witness. The separate
[independent readback audit](n131_w2_m15_leafcutoff_gate_20261006/planted_xcnf_independent_audit.json)
recomputes hashes and streams every clause and XOR row from those artifacts;
all three pass with zero unsatisfied constraints. This independently
corroborates the earlier checked-Sage cutoff-1/3 planted model and adds a
cutoff-12 control. It is still only planted correctness evidence. Candidate
and run IDs remain null; no ordinary N131 relation, logs, public-target DLP,
paired rho result, or speedup exists. The next actual solver gate remains the
one-target, one-worker, 120-second/4-GiB N41 cutoff comparison after R3 drains.

**R3 live process snapshot (2026-10-06 05:32 UTC):** the
[fresh run-bound snapshot](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_snapshot_20261006T053252Z.json)
confirms the original runner and CryptoMiniSat processes are still alive on
the same single-target precomputation query. The current record remains at
rank 0/14, with no `result.json`; solver CPU is 97,584.3 seconds and RSS is
302,186,496 bytes. The log was still advancing at 05:31:37 UTC. No new solver
was launched, so the bounded N41 comparison remains deferred until R3 drains.

**N41 checked-Sage fixture preflight (2026-10-06 05:34 UTC):** the previously
empty ordinary-runner runtime file is now populated by
`./sage --runtime-info` and reports a verified accepted build. The frozen
`run_ordinary.py verify-fixture` check passed at cutoffs 12, 1, and 3 through
`./sage -python`, including formula identity and signed-point/folded-row
replay. The per-cutoff [12](n41_w2_m8_leafcutoff_gate_20261006/fixture_check_cutoff12.json),
[1](n41_w2_m8_leafcutoff_gate_20261006/fixture_check_cutoff1.json), and
[3](n41_w2_m8_leafcutoff_gate_20261006/fixture_check_cutoff3.json) receipts
are saved beside the protocol. No SAT solver ran. A plain Python 3.9 preflight had failed before
solver launch on the runtime's `int.bit_count()` requirement; the saved
checked-Sage receipt and launcher resolve that execution mismatch. The actual
one-worker N41 comparison remains guarded until the original R3 process drains.

**R3 live process snapshot (2026-10-06 05:39 UTC):** the
[latest run-bound snapshot](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_snapshot_20261006T053924Z.json)
again matched both original PIDs and the same one-target query. Rank remains
0/14, `result.json` is absent, and the CryptoMiniSat log last advanced at
05:37:30 UTC. It has used 97,945.1 CPU seconds and 606,289,920 bytes RSS. The
N41 SAT comparison remains deferred; no new solver was started.

**Q20261006052200 independent row-verifier gate (2026-10-06):** the
[frozen v2 installed-Sage verifier](n41_w2_m8_leafcutoff_gate_20261006/RESULT.md)
now rebuilds the exact N41 field, curve, and subgroup base independently of
the SAT producer; it checks full XCNF/model assignments, signed leaf membership,
the public-point group sum, and an independently folded relation. The known
historical row passed at cutoffs 12, 1, and 3, totaling 179,358 CNF clauses
and 50,288 XOR rows checked. Its first frozen fixture control failed only
because the older row lists the same eight leaves in a different slot order;
the v2 verifier normalizes that fixture, while future unpinned rows must match
their SAT model slot by slot. This completes the verifier prerequisite for the
later N41 comparison, not the comparison or any N131 relation.

**R3 live process snapshot (2026-10-06 05:48 UTC):** the
[fresh run-bound snapshot](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_snapshot_20261006T054852Z.json)
confirms the original runner (PID 99052) and CryptoMiniSat worker (PID 99169)
remain alive on the same frozen one-target query (SHA-256
`cbfba6cb37225e327c76dca02280dd7f48ed7fe363d581c96fcd4d0673cecd66`). The
solver log advanced at 05:45:30 UTC; rank is still 0/14 and `result.json` is
absent. Solver CPU is 98,473.9 seconds and RSS is 643,203,072 bytes. No second
solver was launched. This is a long-running target-dependent decomposition
attempt, not a recovered relation, complete IC candidate, or speedup result.

**Q20261006052200 public-formula propagation diagnostic (2026-10-06):** the
[source-bound profile and independent readback](n41_w2_m8_leafcutoff_gate_20261006/RESULT.md)
examined cutoffs 12, 1, and 3 on the same N41 public W2/m8 formula and the
exact N131 public-Q W2/m15 formulas without launching SAT. Positive implication
and contradiction controls passed. On N41, the 296 initial unit assignments
were the entire level-zero CNF/native-XOR closure; none of 328 leaf bits was
forced. On N131, the same was true of 1,850 initial assignments and 1,965
leaf bits. This does not include Gaussian elimination or branch search and is
not a solver-time comparison. It supplies exact evidence that smaller affine
Karatsuba cutoffs do not by themselves create initial target-to-leaf unit
propagation. Keep the unpinned N41 solver gate, but do not promote cutoff
tuning to an N131 relation method on static counts alone; structural
target-coupled pruning remains the main algorithmic need.

**Guarded N41 continuation (2026-10-06 05:54 UTC):** the
[continuation scheduler](n41_w2_m8_leafcutoff_gate_20261006/continue_after_r3.py)
is waiting on the exact R3 PID/create-time identities. After both original
processes exit, it will run cutoffs 12, 1, and 3 in the frozen order, all on
the same single public N41 target, one solver worker, 120 seconds and 4 GiB
per cutoff. Any found ordinary row is independently replayed immediately.
The scheduler invokes the solver in the same checked-Sage process so there is
no uncounted parent process during the RSS-capped run. Its log is
[continuation_scheduler.jsonl](n41_w2_m8_leafcutoff_gate_20261006/continuation_scheduler.jsonl).
No SAT process has been launched by the scheduler while R3 is live. A fresh
[prelaunch Sage runtime receipt](n41_w2_m8_leafcutoff_gate_20261006/sage_runtime_info_ordinary_prelaunch.json)
matches the frozen receipt byte-for-byte.

**Q20261006052200 exact N41 XOR-rank projection (2026-10-06):** the
[source-bound GF(2) analysis and independent low-pivot audit](n41_w2_m8_leafcutoff_gate_20261006/RESULT.md)
eliminated every native XOR row and unit clause in the three same-target N41
W2/m8 formulas. For cutoffs 12, 1, and 3, full coefficient ranks were
10,828, 23,004, and 17,344; removing all 328 leaf-bit columns lowered each
rank by exactly eight. Those eight leaf-only equations are precisely the
independent local even-parity constraints of the eight weight-two leaves.
No leaf bit is fixed, and no additional target-dependent linear leaf
equation exists in this declared XOR-only relaxation. The result leaves
nonunit CNF, nonlinear inference, and SAT branching open, and is not an N131
rank result or speed claim. It reinforces the requirement for a search method
that couples the public target to pair domains beyond circuit-size tuning.

**Continuation preflight and R3 status (2026-10-06 05:58 UTC):** checked-Sage
imports for the deferred runner and independent verifier pass. Both original
R3 PID/create-time identities are still alive, and the N41 `runs/` directory
remains absent, so the scheduler has not started a solver. The [newest
snapshot](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/live_process_snapshot_20261006T055810Z.json)
shows the same query hash, rank 0/14, no result, 98,995.9 solver CPU seconds,
and 553,680,896 bytes RSS; the stdout log advanced at 05:55:37 UTC.

**Exact N131 XOR-rank result (2026-10-06):** the
[source-bound full-formula analysis](n41_w2_m8_leafcutoff_gate_20261006/N131_XOR_RANK_RESULT.md)
computed the GF(2) rank of every native XOR row and unit clause on the
three frozen, ordinary public-Q W2/m15 formulas. For Karatsuba cutoffs 12,
1, and 3, the coefficient ranks are 149,077, 312,362, and 229,335;
removing all 1,965 leaf columns lowers each by exactly 15. These are the
15 existing local W2 parity equations, so this linear relaxation yields no
additional target-dependent leaf-only equation or fixed leaf bit. The native
implementation reproduced the independent N41 control, and a separate
readback passed source, binary, formula, and rank invariants. There is no
second independent N131 elimination. Nonunit CNF and nonlinear search are
outside this diagnostic; it is not a relation or speedup. The queued
same-target N41 SAT comparison remains the next bounded solver gate after
the authoritative R3 run drains.

**First-two-leaf order and strictness gate (2026-10-06):** a
[source-frozen 17-prefix panel](n41_w2_m8_leafcutoff_gate_20261006/PAIR_PIN_PROPAGATION_RESULT.md)
on each exact N41 W2/m8 public formula found zero CNF/native-XOR unit
contradictions after two legal leaves were pinned. Two prefixes forced later
bits because their second x was among the last two values in the encoder's
bit-index lexicographic order; this was local ordering, not evidence of
target-conditioned pruning. The first two raw panels used integer order
and are preserved as invalid diagnostics. The frozen formula's comparator
is non-strict, while the N41 ordinary replay requires eight distinct x
values. A separate [strict-order cutoff-1 preflight](n41_w2_strict_lex_gate_20261006/RESULT.md)
reproduced the original XCNF and added exactly seven equality-exclusion
unit clauses with no new variables or XOR rows. The known full model still
passes; duplicate and terminal-prefix controls are rejected by unit
propagation, and an independent streamed XCNF readback passes. This is a
proposal with null candidate/run IDs and no SAT timing, N131 ordinary
relation, or speedup. Repeated x can carry a useful coefficient in the
official N131 pipeline, so this N41 policy restriction needs its own
coverage and solver comparison before any transfer. The original R3 and
queued N41 cutoff runs remain separate.

**Strict-order transfer boundary (2026-10-06):** the
[integer-only source-bound count](n41_w2_strict_lex_gate_20261006/combinatorial_transfer.json)
shows why seven N41 inequality units are a limited challenge-width lead.
They remove duplicate x assignments under the N41 acceptance policy and
prune 471/3,321 distinct first-two prefixes by suffix capacity, but the
analogous W2/m15 N131 count is only 23,751/1,680,861 (1.413%). Across
all ordered x multisets, strictness retains 50.47% at N41 and 89.18% at
N131. This does not measure SAT work or coverage, and the official N131
solver permits some useful repeated-x rows. Keep the N41 strict variant as
a separate proposal and continue to prioritize target-coupled nonlinear
pair-domain search for the actual challenge relation.

**Continuation advanced to the complete sparse-seed m16 candidate (2026-10-06):**
the previous N41 cutoff scheduler was stopped while still waiting, before it
launched any solver. The replacement
[continue_after_r3_phi_q.py](n131_phi_torsion_frobenius_domains_20261005/continue_after_r3_phi_q.py)
waits for the exact R3 process identities to exit and its terminal result,
then launches the frozen
[sparse-seed m16 full pipeline](n131_phi_torsion_frobenius_domains_20261005/m16_static/run_sparse_seed_single_target.py).
That candidate collects factor logs in sequential target-independent setup,
then measures exactly one previously unseen official public Q after logs are
ready; no multi-target or batch workload is used. It stops precomputation at
full rank or after 256 relation queries, with a seven-day cap per query,
one solver worker, and a 4-GiB combined RSS limit. The fresh checked-Sage
[preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/single_target_preflights/sparse_m16_20261006T064353Z.json)
confirms `target_count=1`, `batch=false`, and `solver_launched=false` while the
original R3 runner and worker identities remain alive. A separate installed-Sage
auditor will replay the rows, full-rank logs, online relation, scalar, and
phase accounting if the run produces complete logs. If R3 itself terminates
with a recovered scalar, the continuation instead performs an independent
Sage scalar replay before choosing the next action. The durable state and
event log are in
[continuation_20261006](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/).
Until a DLP and same-target rho run are independently verified, this is a
candidate execution, not a speedup claim.

**Exact N131 phi pair-output affine-rank gate (2026-10-06):** the
[source-frozen subset screen and independent low-pivot readback](n131_phi_torsion_frobenius_domains_20261005/m16_static/pair_output_affine_rank_20261006/RESULT.md)
used 1,024 evenly spaced records from Q1437's exact 300,304-state adjacent
pair-sum index. The augmented `[1,x]` and `[1,phi]` GF(2) ranks both reached
132/132, at sample 514 and 134 respectively; all sampled phi inverse
identities passed. Thus no nonzero affine equation in either output
coordinate alone can reject a member of the complete pair domain, and
Frobenius rotations preserve this rank for the other seven adjacent pairs.
This closes only output-only linear filtering. Nonlinear and target-coupled
multi-pair constraints remain open. No SAT solve, ordinary N131 relation,
factor logs, DLP, or speedup follows; this proposal is separate from the
full sparse-seed m16 candidate. The drain-gated m16 one-target pipeline
remains the next live challenge-width test after W2 R3 ends.

**Exact N131 phi pair-output quadratic-rank gate (2026-10-06):** the
[source-frozen degree-two screen and independent reversed-variable audit](n131_phi_torsion_frobenius_domains_20261005/m16_static/pair_output_affine_rank_20261006/QUADRATIC_RESULT.md)
evaluated all `1 + 131 + C(131,2) = 8,647` squarefree Boolean features on
16,000 deterministic exact pair outputs. Their GF(2) rank reached the full
8,647 by sample 8,651; both elimination orders and all sampled phi inverse
identities agree. No universal output-only polynomial of degree at most
two vanishes on that complete pair domain or its seven Frobenius rotations.
This closes that declared low-degree membership-filter route, but it does
not rule out target-conditioned pruning of completable pair subsets,
higher-degree equations, or multi-pair algebraic elimination. It is neither
an ordinary N131 relation nor a speedup. The complete sparse-seed m16
single-target candidate remains queued behind the live R3 terminal gate.

**Static N131 pair-join coverage frontier (2026-10-06):** the
[Q20261006065000 source-frozen and independently audited calculation](n131_phi_torsion_frobenius_domains_20261005/m16_static/static_join_frontier_20261006/RESULT.md)
uses Q1437's exact 300,304-state pair domain and the challenge subgroup
order. Under the specific design of a target-independent explicit 35-byte
affine-point-key table, a 4-GiB cap stores at most 122,713,351 sums. Even
granting 600 billion complete target-independent online probes in 600
seconds, the largest uniform-target coverage fraction over every split of
the eight pair domains is at most `1.08187e-19` for one orientation, or
`5.66898e-17` after an intentionally generous factor of 4 endpoints and
131 Frobenius orientations. This exact counting bound is specific to that
static table-and-probe architecture and says nothing decisive about the
fixed public target, compressed or symbolic tables, or target-adaptive
algebraic generation. It does rule out promoting the direct explicit
N23-style pair-list join as a viable N131 method under the declared
600-second/4-GiB method-selection gate. The separate frozen m16 SAT
candidate has a seven-day per-query cap, so this static-join bound does
not apply to that different solver. No N131 solver, relation, DLP, or speedup
was produced; the live R3 and drain-gated full m16 candidate remain the
execution path.

**Continuation poll (2026-10-06 06:52 UTC):** the checked-Sage watcher
refreshed its state while both original R3 runner/solver process identities
remained alive. The R3 precomputation remains `RUNNING`, rank `0/14`, with no
terminal result; the full m16 runner is still gated and has not launched. The
one-target target policy and frozen workload remain unchanged.

**R3 compute-progress sample (2026-10-06 06:58 UTC):** after saving the
checked-launcher runtime receipt, an installed-Sage/psutil sample matched
both process creation identities. CryptoMiniSat had accumulated 102,212.3 CPU
seconds and 534,462,464 bytes RSS; the runner had 207.3 CPU seconds and
16,973,824 bytes RSS. Relative to the 05:58:10 snapshot, solver CPU increased
by 3,216.4 seconds over 3,604.4 wall seconds and stdout grew from 4,558,127
to 4,570,093 bytes (last write 06:51:16 UTC). Despite active solver work, the
precomputation record remains rank `0/14`, with no terminal result. The sample
and Sage runtime receipt are
[r3_live_resource_sample_20261006T065600Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T065600Z.json)
and
[sage_runtime_info_process_monitor_20261006T065600Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/sage_runtime_info_process_monitor_20261006T065600Z.json).
The drain gate remains closed; no competing solver was started.

**N41 global trace-character method gate and exact N131 support transfer
(2026-10-06):** the [Q20261006070300 source-frozen result](n41_pair_trace_xor_20261006/RESULT.md)
added one mathematically necessary target-coupled native-XOR row to the
established exact four-pair N41 public-point SAT formula. The known row,
byte-level formula diff, and independent checked-Sage trace/group audit all
pass; the unpinned one-worker run reached its 120-second cap without a
model. This N41 diagnostic overlapped the continuing R3 solver, so its CPU
timing is exploratory. The challenge-width exact pair index has 150,184
trace-zero and 150,120 trace-one outputs per Frobenius-rotated domain. As a
result, a completely free pair can always satisfy either residual global
trace parity; this cut cannot deliver the required early two-free-pair
pruning. It is not an N131 relation, factor-log result, DLP, or speedup.
Keep the unpinned N131 decomposition milestone and require stronger
target-coupled nonlinear elimination before promoting another method.

**Sparse-m16 first-row audit gate (2026-10-06):** the separate
[incremental independent Sage auditor](n131_phi_torsion_frobenius_domains_20261005/m16_prefix_audit_20261006/README.md)
can replay a completed precomputation row before all 274 factor-base logs
exist. It checks frozen candidate/run/source identity, all 71,788 base points
and 274 folded columns, the saved SAT assignment against every CNF/XOR record
of its hash-matched query, the row against `[4]` times its generated target,
and the prefix rank. Planted and corrupt-row controls pass, including a real
saved CryptoMiniSat N131 model parser check. This is an audit capability,
not an ordinary relation or an algorithmic speed result. The live R3 run
remains rank `0/14`; sparse m16 remains drain-gated. The next algorithmic
decision is still an unpinned target-coupled row, not a formula diagnostic.

**Known-scalar target-shift method gate (2026-10-06):** the frozen
[Q20261006074000 screen](n131_target_shift_constant_screen_20261006/RESULT.md)
examined the official Q and 255 deterministic known-scalar shifts, charging
the entire policy to the one supplied target if ever promoted. The best
shift reduced the four final-link constant multiplication row supports by
only 228/33,460 (0.6814%); it saved 1,596 bytes of an 11.27-MB formula,
with no change to variables, clauses, or XOR-row count. The unshifted
formula's hash exactly matches the frozen sparse-m16 Q formula. No solver
was launched and no relation or timing speedup was measured. Do not divert
the live R3 or queued m16 solver for this weak formula-footprint lead;
continue the target-coupled joint-search gate.

**High-density N131 d13/m12 formula probe (2026-10-06):** the
[source-bound result](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/RESULT.md)
built an exact 12-summand formula for the same official Q using the audited
13-dimensional phi subspace. It has 232,244 variables, 171,278 native XOR
rows, and 11,202,092 bytes, with 4,134 folded base columns. A planted
synthetic-target model passes the exact decoder, and independent checked
Sage replays all 12 leaves, ten partials, four endpoint lifts, and two signed
group rows. The uniform-sum model predicts more decompositions than sparse
d9/m16, but this is not measured fixed-Q yield. The separate complete-base
Sage digest audit was interrupted for runtime and remains open; no unpinned
Q solver was launched while R3 is live. Consider a resource-frozen
public-only d13/m12 probe after the active R3 and queued d10/m15 searches
drain, with any
model checked against the saved XCNF and independently replayed in Sage.
No ordinary N131 relation, factor logs, DLP, or speedup follows yet.

**Single-target d10/m15 candidate freeze (2026-10-06 08:03 UTC):** after the
user restated that the objective is one target, the d10/m15 variant was frozen
against the same official public Q and workload `3c1992b7c92f` as
`IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0h35d801e69db9`.
Its exact basis has ten dimensions, 532 valid selectors per position, 139,384
usable signed subgroup points before folding, and 532 relation columns. The
15-summand official-Q formula has 282,598 variables, 225,092 clauses, and
208,783 native XORs. The uniform-full-curve estimate of 931,526 decompositions
per exact cofactor endpoint is only a heuristic; no natural official-Q
relation has been observed. The corrected independent Sage planted control
passes all 15 leaves, 13 partials, four fiber lifts, and both signed relation
replays. The previous replay failure was its incorrect `lambda^2=-2` check;
the curve's Frobenius polynomial is `lambda^2+lambda+2`.

The full runner and result auditor are source-bound, explicitly single-target,
and keep setup/log preparation outside the target-online interval. Its
preflight at 08:02 UTC passed all frozen checks and returned
`WAIT_FOR_R3_DRAIN` without launching a solver. The old m16 continuation was
stopped before it could launch its queued candidate. New checked-Sage watcher
session 78771 waits on the exact R3 process identities, independently audits
an R3 scalar if present, and then queues only d10/m15. At the last live check
both R3 processes were still active; the latest recorded relation-matrix rank
remains `0/14` at 06:58 UTC. There is still no natural relation, verified DLP,
online-time measurement, paired rho run, or speedup claim. The host is macOS,
so CPU timing remains exploratory without an isolated-host receipt.

**R3 single-target continuation compute sample (2026-10-06 08:11 UTC):** a
fresh checked-Sage/psutil sample matched both original process creation
identities. The runner remains alive and CryptoMiniSat has accumulated
105,874.1 CPU seconds and 521,535,488 bytes RSS. Since the 06:56 UTC resource
baseline, the solver used another 3,661.8 CPU seconds over 4,393.9 wall
seconds; its log is 9,948 bytes larger, but the last log write remains
08:06:57 UTC. The precomputation is still `RUNNING`, rank `0/14`, with no
attempts or terminal result. This demonstrates continued solver activity,
not a relation or DLP. The d10/m15 watcher remains gated on this exact run;
no competing SAT job was launched. Receipt:
[r3_live_resource_sample_20261006T081128Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T081128Z.json).

**R3 live solver and queued-candidate recheck (2026-10-06 08:19 UTC):** the
checked-Sage/psutil sample at 08:17 matched both original R3 process identities.
CryptoMiniSat had accumulated 106,192.6 CPU seconds and 576,520,192 bytes RSS;
it added 3,980.3 CPU seconds over 4,750.1 wall seconds from the 06:56 baseline.
Its log grew by 10,725 bytes and was written at 08:15:21 UTC, while the
precomputation remains `RUNNING`, rank `0/14`, and has no terminal result. The
watcher refreshed at 08:19 and still reports `WAIT_FOR_R3_DRAIN`. The d10/m15
manifest comparison confirms the intended structural trade: 139,384 base
points and 532 folded columns, with a frozen official-Q formula of 282,598
variables, 225,092 clauses, and 208,783 native XORs, versus the active R3
candidate's 3,668 points and 14 folded columns. These configurations are not
a controlled runtime comparison; d10/m15 remains queued, not measured. The
fresh sample is
[r3_live_resource_sample_20261006T081724Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T081724Z.json).

**Independent d13/m12 full-base Sage audit (2026-10-06):** the previously
unfinished audit now passes through the checked repository Sage launcher.
It independently verified the 13-dimensional ONB and all 131 conjugate
subspaces, a 1,073,022-coordinate nonzero union, 4,134 valid signed subgroup
selectors, full signed-Frobenius orbit length 131, the 1,083,108-point set
digest, the official-Q embedding, and all four cofactor-fiber lifts. Receipt:
[sage_d13_full_base_audit_v1.json](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/sage_d13_full_base_audit_v1.json);
the result note was corrected at
[RESULT.md](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/RESULT.md).
This closes the mathematical base-audit gap for proposal `Q20261006081500`,
but it still has no candidate/run ID or complete log/DLP pipeline. Its
149,946,445 expected signed tuples across four endpoints are a uniform-sum
heuristic, not fixed-Q relation yield. It has 4,134 folded columns versus
532 for frozen d10/m15, so promoting it for single-target online speed still
requires an ordinary-Q solve and eventually a complete verified DLP.

**R3 compute refresh (2026-10-06 08:35 UTC):** a fresh checked-Sage sample
again matched both original process identities. The solver had accumulated
107,177.6 CPU seconds and 575,094,784 bytes RSS, with 4,965.3 additional CPU
seconds over 5,804.5 wall seconds since the 06:56 baseline. Its log grew by
75,239 bytes and was written at 08:34:57 UTC; precomputation remains
`RUNNING`, rank `0/14`, and no terminal result exists. The d10 watcher also
refreshed at 08:34 UTC and remains at `WAIT_FOR_R3_DRAIN`. Receipt:
[r3_live_resource_sample_20261006T083459Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T083459Z.json).

**Q20261006081500 d13/m12 first-relation gate (2026-10-06 08:26 UTC):** the
[frozen proposal protocol and method-selection result](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/RESULT.md)
now have a source-bound public-only Q probe with a 600-second/4-GiB envelope,
four-model cap, preserved failure statuses, and exclusive partial-query
phases. It refuses to run while R3 is live or d10/m15 has not reached a
terminal unsolved result, and stops if either predecessor has an independently
verified DLP. A checked-Sage preflight returned `WAIT_FOR_R3_DRAIN` with no
solver launch. An independent Sage row auditor replays any eventual saved
XCNF model and folded group row; planted both-sign and two tamper controls
pass. The separate full-base Sage digest remains unverified, and no ordinary
Q model or relation has been produced by this proposal. The v2 frozen
protocol moved target-fiber selection and checking inside the charged
partial-query interval; its preflight and gate controls pass with the R3
wait intact. Its `candidate_id`
and `run_id` remain null; the prediction of higher relation density is not
a measured speedup or reason to interrupt the live R3/d10 queue.

**D13/m12 saved-formula and live-gate recheck (2026-10-06 08:30 UTC):** the
[saved-XCNF planted control](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/saved_xcnf_planted_control_v1.json)
independently checked all 401,375 CNF/XOR records and rejected one changed
pinned leaf bit. The source hashes in the proposal protocol still match, and
no d13 public-Q run directory exists. A new checked-Sage process sample
matched the live R3 identities at 08:30 UTC: rank remains `0/14`, no terminal
result exists, and CryptoMiniSat has added 4,686.9 CPU seconds since the
06:56 UTC baseline. The d13 gate therefore remains closed. Receipt:
[r3_live_resource_sample_20261006T083004Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T083004Z.json).

**D13/m12 drain-gated continuation (2026-10-06 08:35 UTC):** a checked-Sage
[watcher](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/continue_after_d10.py)
is live, with identity recorded in its
[state](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/continuation/state.json).
Its one-shot and live checks returned `WAIT_FOR_R3_DRAIN`; it created no
public-Q run. After R3 and d10/m15 terminally fail to recover an independently
verified DLP, it will run the frozen 600-second/4-GiB d13 first-relation
probe once and automatically audit a decoded row in installed Sage. A
verified predecessor DLP stops this probe. This is a queued diagnostic,
not a relation, complete IC result, or speedup.

**Post-audit state reconciliation (2026-10-06 08:40 UTC):** the preceding
08:26 and 08:30 notes saying the d13 complete-base digest was unverified are
superseded by the 08:34 installed-Sage `PASS` receipt above. The d13 watcher
PID 25398 was checked directly through the repository launcher; its process
creation time matches `1791275723.789869`, it is alive, and it remains at
`WAIT_FOR_R3_DRAIN`. The d10 continuation session 78771 is also still live.
R3's latest identity-matched sample is 08:34:59 UTC, rank `0/14`, with recent
solver-log writes. Neither queued d13 nor d10 has launched its solver yet.

**Single-target execution poll (2026-10-06 08:42 UTC):** the R3 sample at
08:42:01 again matched both process identities. CryptoMiniSat is alive at
107,575.2 CPU seconds and 550,092,800 bytes RSS; its log grew 171,893 bytes
from the 06:56 baseline and was written at 08:41:57 UTC. The tail has advanced
to restart 30,055, but precomputation remains `RUNNING`, rank `0/14`, with no
terminal result. Thus the solver remains active; the gate has not drained. The
d10 continuation session remains live, and a direct checked-Sage/psutil check
matched d13 watcher PID 25398 to its recorded creation time. Both watchers
remain gated and neither new solver has launched. Receipt:
[r3_live_resource_sample_20261006T084201Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T084201Z.json).

**D13 runtime-formula integration and R3 poll (2026-10-06 08:56 UTC):** the
d13/m12 adapter emitted the frozen public-Q XCNF byte-for-byte through the
reusable runtime relation-formula path: SHA-256
`91ed7b49e8a8e8637f79c94cdb568ece415f32359d82425d4369fd829481622e`,
11,202,092 bytes, 232,244 variables, 228,629 clauses, and 171,278 native
XORs. It remains a formula-wiring correctness result only; no SAT solver was
launched, no natural relation or logarithm exists, and candidate/run IDs stay
null. Receipt:
[adapter_formula_equivalence_v1.json](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/adapter_formula_equivalence_v1.json).
The checked-Sage process sample at 08:56:17 matched both R3 process identities;
CryptoMiniSat had accumulated 108,329.2 CPU seconds and 612,794,368 bytes RSS,
with 6,116.9 additional CPU seconds and 194,073 log bytes since the 06:56
baseline. The log was written at 08:55:44 UTC. Precomputation remains
`RUNNING`, rank `0/14`, without a terminal result. Both d10 and d13 watchers
refreshed at 08:54 UTC and remain `WAIT_FOR_R3_DRAIN`; neither launched a
solver. Receipt:
[r3_live_resource_sample_20261006T085617Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T085617Z.json).

The d13 full-runner review also found a capacity mismatch before any
candidate was frozen: its 4,134 folded columns require at least 4,134
independent log equations, while the existing d10 runner's 256-target,
four-model cap can yield at most 1,024 rows. Added a separate sparse
forward-elimination and back-substitution implementation for d13 and passed
known-log recovery, dependent-row, inconsistency, and randomized small-system
controls at the ECC2K-130 subgroup modulus. Large-matrix performance has not
been measured; d13 remains a proposal with null candidate/run IDs.

The sparse elimination controls also recover a known vector through a
4,134-column banded system inserted in reverse pivot order, matching d13's
actual folded matrix width. This is a dimension/correctness control, not a
large random-matrix performance estimate. The next checked-Sage sample at
09:03:41 UTC again matched both R3 process identities: CryptoMiniSat had
108,730.9 CPU seconds and 585,826,304 bytes RSS; its runner used 557,367,296
bytes RSS. The solver log was written at 09:01:21 UTC and had grown by
197,815 bytes from the 06:56 baseline. The precompute is still `RUNNING`,
rank `0/14`, with no terminal result. Both watchers refreshed at 09:04 UTC and
remain `WAIT_FOR_R3_DRAIN`. Receipt:
[r3_live_resource_sample_20261006T090341Z.json](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T090341Z.json).

**D13 full-width exact matrix control (2026-10-06 09:38 UTC):** the FLINT
relation-rank worker passed an exact synthetic 4,134-column control at the
d13/m12 folded matrix width. It recovered the planted log vector from 4,167
12-sparse rows over the ECC2K-130 subgroup modulus, replayed all equations,
and assigned zero rank gain to a consistent duplicate. Elimination took
918.19 seconds with 356,286,464 bytes reported process peak RSS; final replay
took 8.47 ms. The [test receipt](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/flint_relation_rank_fullwidth_v1.json)
and [compiler/library provenance](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/flint_relation_rank_fullwidth_provenance_v1.json)
are saved. Host-wide CPU isolation was not established and R3 was live, so the
wall time is exploratory. This verifies the exact matrix stage on synthetic
rows only; natural relation yield, factor logs, the single-target DLP, paired
rho timing, and speedup remain unknown. At 09:51 UTC both downstream watchers
still reported `WAIT_FOR_R3_DRAIN`; no competing solver was launched.

**Frozen d13/m12 candidate and one-target preflight (2026-10-06 10:11 UTC):**
the complete pipeline is now source- and evidence-bound as
`IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0h44e0b7f66da0` on
workload `3c1992b7c92f`. Its actual base has 1,083,108 usable points before
folding and 4,134 final columns. The candidate uses twelve-summand SAT
decomposition, direct collection and target handling, and exact FLINT modular
Gaussian elimination for final relation logs. The [candidate manifest](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json)
and [single-target run protocol](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/d13_m12_single_target_protocol_v1.json)
bind all algorithm and workload inputs. The protocol permits up to 8,192
singleton target-independent preparation queries, caps each at 600 seconds and
four models, and starts the primary online clock only for the one supplied Q
after verified factor logs are ready. It excludes launch/input load and
target-independent setup/precomputation and keeps the 4-GiB resource envelope
and per-query failure records explicit. Setup RSS and parent-plus-FLINT worker
RSS are checked against the same conservative cap. A bounded compressed-artifact budget
prevents the long setup from consuming the remaining disk while retaining
artifact hashes and query outcomes.

The checked-Sage [preflight](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/single_target_preflights/d13_m12_20261006T101125Z.json)
validated the candidate's frozen source/evidence/curve/workload digests and
returned `WAIT_FOR_R3_DRAIN`; `target_count=1`, `batch=false`, and no solver was
launched. R3 is still active and the d10 and d13 gates remain closed. No natural
relation, completed factor logs, ECC2K-130 DLP, same-point rho result, or
speedup exists yet; the candidate run ID remains null.

**R3 live sample (2026-10-06 10:14 UTC):** the checked-Sage process sampler
again matched both recorded R3 PIDs and creation times. Since the 06:56 UTC
baseline, CryptoMiniSat accumulated another 10,583.1 CPU seconds and its log
grew by 215,341 bytes; the log was written at 10:14:30 UTC. Precomputation
remains `RUNNING`, rank `0/14`, with no terminal result. The [sample receipt](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T101430Z.json)
and its [checked-Sage runtime info](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/sage_runtime_info_process_monitor_20261006T101312Z.json)
are saved. D10, the d13 one-relation probe, and the frozen 4,134-column
candidate remain gated; no additional solver was launched.

**Isolation-host capability check (2026-10-06):** the repository's read-only
`scripts/isolated_bench.py probe-host` reports this current host as Darwin,
arm64, `virtualization=not_linux`, with no cgroup isolation, NUMA node, or
`numactl` state. The [receipt](isolated_host_probe_20261006T102148Z.json)
therefore cannot qualify a CPU speedup run. Local correctness and matrix-stage
diagnostics remain exploratory until an equivalent isolated Linux host is
available.

**Refrozen d13/m12 protocol and current gate (2026-10-06 10:45 UTC):** after
adding full-width timing provenance and the independent run auditor, the final
candidate identity is
`IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0h963f931502c1`.
The [manifest](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json)
and [protocol](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/d13_m12_single_target_protocol_v1.json)
bind workload `3c1992b7c92f`, one supplied Q, 1,083,108 usable base points,
4,134 folded columns, and explicit `target_count=1`, `batch=false` fields. The
updated checked-Sage [preflight](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/single_target_preflights/d13_m12_20261006T104458Z.json)
passed source, evidence, curve, workload, and runtime checks, then correctly
returned `WAIT_FOR_R3_DRAIN` without launching a solver. The persistent
[continuation state](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/candidate_continuation/state.json)
is `WAIT_FOR_D10_AND_D13_TERMINAL`; its identity-matched watcher is alive and
will perform a final checked-Sage preflight before launching this candidate
once both upstream gates are terminal.

The instrumented [synthetic full-width matrix control](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/flint_relation_rank_fullwidth_v2.json)
reached rank 4,134/4,134 on 4,167 planted 12-sparse equations and independently
replayed the known log vector. It reports 21.1 ms parsing, 63.6 ms matrix
construction, 925.05 s elimination, 8.71 ms equation replay, and 357,335,040
bytes peak RSS. Its [provenance](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/flint_relation_rank_fullwidth_provenance_v2.json)
marks timing exploratory: the host is not isolated and R3 was active. It is
not natural relation yield or an end-to-end candidate measurement.

The latest checked-Sage [R3 sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T104216Z.json)
matched both process identities. Since the 06:56 UTC baseline the solver added
12,188 CPU-seconds and its log grew 220,100 bytes, with the latest log write
at 10:38:08 UTC; relation rank remains 0/14 and no terminal result exists. The
same-target rho run, a completed IC DLP, and any speedup remain unknown.

**R3 and continuation poll (2026-10-06 10:49 UTC):** the confirmed live R3
solver accumulated another 393 CPU-seconds since the 10:42
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T104903Z.json),
while its log size and 10:38:08 UTC write time remained unchanged. This is
active CPU work with no new rank evidence: precomputation remains `RUNNING`,
rank `0/14`, and no terminal result exists. The full-candidate watcher process
72738 is identity-matched and refreshed its state at 10:49:06 UTC; it remains
`WAIT_FOR_D10_AND_D13_TERMINAL` and has not launched a solver.

**Remote isolation-host access check (2026-10-06 10:53 UTC):** a read-only SSH
probe through the configured `runpod` alias returned `Connection refused`, so
the remote `probe-host` did not execute and no host isolation was established.
No remote computation or host change was made.

**Rho reference re-bound to the current candidate (2026-10-06 10:57 UTC):**
the corrected one-target rho identity audit now reads the d13/m12 manifest and
protocol. Its [v5 receipt](n131_rho_reference_identity_audit_v5.json) passes
the official curve, field map, generator, supplied Q, subgroup order, target
count, workload digest, Frobenius eigenvalue, and production walk-identity
checks for candidate `...ISO0h963f931502c1`. This prepares an exact same-Q
reference; it is not a rho walk, target solution, timing, or speedup. The
[reference design](N131_RHO_REFERENCE_DESIGN_20261005.md) now names the current
d13/m12 candidate instead of the superseded m15 candidate.

**Online timing boundary correction and refreeze (2026-10-06 11:05 UTC):**
source review found online SAT artifact compression was occurring before scalar
recovery. The runner now stops the single-target clock after the recovered
scalar is replayed against Q, then records SAT artifact archival duration and
status separately. The independent auditor requires archival to be marked as
excluded; an archival error no longer converts an already verified DLP into a
failed computation. The updated manifest and protocol freeze candidate
`IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0ha088b3d8e4a0`.
Its checked-Sage [preflight](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/single_target_preflights/d13_m12_20261006T110556Z.json)
returns `WAIT_FOR_R3_DRAIN` with no solver launched, and the [v5 rho identity
audit](n131_rho_reference_identity_audit_v5.json) passes all 18 checks for
this candidate and the same supplied Q. The restarted [watcher
state](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/candidate_continuation/state.json)
is live under the updated candidate identity.

The latest checked-Sage [R3 sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T110634Z.json)
at 11:06 UTC matched both process identities; rank remains `0/14`. No
candidate SAT run has started, and no natural relation, factor logs, or DLP
exists yet.

**R3 follow-up sample (2026-10-06 10:54 UTC):** the checked-Sage sample
[matched both live process identities](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T105426Z.json).
The solver added about 321 CPU-seconds and 1,411 log bytes since the 10:49
sample; the log was written at 10:51:02 UTC and advanced through restart
30,163. Precomputation rank is still `0/14`, so this confirms solver activity
but yields no usable relation yet. At 10:58 UTC the candidate watcher was still
alive and the d10 and d13 states remained `WAIT_FOR_R3_DRAIN`.

**R3 progress sample (2026-10-06 11:01 UTC):** the next checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T110100Z.json)
matched both process identities. Since 10:54 UTC the solver added about 393
CPU-seconds and 882 log bytes; the log's latest write is 10:59:01 UTC. The
recorded stdout tail advanced through its distillation phases, but relation
rank remains `0/14`. The candidate continuation session also remains live and
gated.

**R3 and candidate poll (2026-10-06 11:08 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T110847Z.json)
matched both processes, adding about 132 CPU-seconds and 775 log bytes since
11:06. The last solver-log write is 11:07:34 UTC and relation rank remains
`0/14`. Candidate `...ISO0ha088b3d8e4a0` is integrity-frozen with the artifact
archive excluded from its online timer; its identity-matched watcher remains
`WAIT_FOR_D10_AND_D13_TERMINAL` and no candidate run has started.

**R3 and candidate poll (2026-10-06 11:15 UTC):** the next checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T111451Z.json)
matched both process identities, adding about 67 solver CPU-seconds and 1,031
log bytes since 11:13. The latest log write is 11:14:51 UTC, but relation
rank is still `0/14` and there is no terminal result. The candidate watcher
continues to wait for d10 and d13; no candidate run has started.

**R3 and host-gate check (2026-10-06 11:20 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T111723Z.json)
matched both process identities; the solver added about 152 CPU-seconds and
523 log bytes since 11:14, but rank remains `0/14`. The candidate watcher
still waits for d10 and d13. A read-only [local host probe](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/local_cpu_isolation_probe_20261006T111942Z.json)
records Darwin arm64, which cannot satisfy the repository's isolated Linux
CPU timing gate. No IC or rho timing was run.

**R3 and remote-host check (2026-10-06 11:21 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T112111Z.json)
matched both R3 processes, adding about 226 solver CPU-seconds and 775 log
bytes since 11:17. Rank remains `0/14`; d10 and d13 still wait for R3 to
drain. The configured RunPod SSH endpoint refused a read-only check, and no
`runpodctl` executable or RunPod API key is available, so no remote benchmark
job was started.

**R3 sample (2026-10-06 11:23 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T112341Z.json)
matched both process identities, adding about 149 solver CPU-seconds and
1,659 log bytes since 11:21. The solver log advanced through 11:23:24 UTC;
precomputation rank remains `0/14`. No terminal result exists, and the
single-target m12 candidate remains gated.

**R3 no-output interval (2026-10-06 11:25 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T112556Z.json)
matched both process identities and measured about 135 more solver
CPU-seconds since 11:23. Log size did not change, its latest write is still
11:23:24 UTC, and rank remains `0/14`. No terminal result exists; the
candidate and prerequisite watchers remain live and gated.

**R3 live poll (2026-10-06 11:27 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T112713Z.json)
again matched both processes. Solver CPU advanced about 77 seconds since
11:25, with no new log bytes, no rank gain from `0/14`, and no terminal
result. The same single-target gates remain active.

**R3 live poll (2026-10-06 11:28 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T112832Z.json)
matched both process identities. Solver CPU advanced about 79 seconds since
11:27, but the log size is unchanged, its latest write remains 11:23:24 UTC,
and rank remains `0/14`. Both the R3 job and one-target candidate watcher are
still live; no terminal result exists.

**R3 output resumed (2026-10-06 11:29 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T112941Z.json)
matched both process identities and measured about 69 more solver CPU-seconds
and 777 log bytes since 11:28. The output advanced through restart 30,172
with the latest write at 11:28:44 UTC. Rank remains `0/14`; there is still no
usable relation or terminal result.

**R3 live poll (2026-10-06 11:31 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T113114Z.json)
matched both process identities, with about 93 more solver CPU-seconds since
11:29. No log bytes were added since 11:29; the last log write remains
11:28:44 UTC, rank is still `0/14`, and there is no terminal result.

**R3 live poll (2026-10-06 11:32 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T113245Z.json)
matched both processes. Solver CPU advanced about 90 seconds during roughly
91 seconds of wall time, at about 542 MiB RSS. The log remains unchanged,
rank remains `0/14`, and no terminal result exists.

**R3 and pipeline review (2026-10-06 11:34 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T113418Z.json)
matched both processes and recorded about 93 more solver CPU-seconds since
11:32. The log remains unchanged since 11:29 and rank is still `0/14`. The
frozen m12 runner performs factor-base setup and relation-log precomputation
before its target-online interval; the candidate controller waits on R3/d10/
d13 terminal states, so no independent precompute mode is registered.

**R3 progress and d13 watcher recovery (2026-10-06 11:43 UTC):** the checked-
Sage [sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T114312Z.json)
matched both R3 process identities, adding about 238 solver CPU-seconds and
775 log bytes since 11:39; the latest log write is 11:42:17 UTC. Rank remains
`0/14`. The d13 watcher PID recorded in state was missing, while its event
log showed no run and its state remained `WAIT_FOR_R3_DRAIN`. I restarted it
through `./sage -python`; new PID 26810 is identity-matched and has not
launched SAT. The d10 and m12 watchers are also confirmed live; all gates
remain single-target.

**Post-recovery poll (2026-10-06 11:44 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T114447Z.json)
matched both R3 processes. Solver CPU advanced about 94 seconds since 11:43,
but log size and rank did not change; rank remains `0/14`, with no terminal
result. The restored d13 watcher remains alive at `WAIT_FOR_R3_DRAIN`,
`run_id=null`, and has launched no SAT query.

**R3 restart progress (2026-10-06 11:48 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T114802Z.json)
matched both process identities and recorded about 195 solver CPU-seconds and
775 log bytes since 11:44. Solver output advanced to restart 30,175. Rank is
still `0/14`, and no terminal result exists; the restored d13 watcher remains
live with no probe run active.

**R3 progress and rho source fingerprint (2026-10-06 11:53 UTC):** the latest
checked-Sage [R3 sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T115323Z.json)
again matched runner/solver PIDs 99052/99169. Solver CPU has advanced by about
16,413 seconds and the SAT log by 232,693 bytes since the fixed 06:56 sample;
the last log write is 11:52:59 UTC. Rank remains `0/14` and there is no
terminal result, so the queued d10, d13, and full m12 gates remain closed. I
also recorded and revalidated the one-target rho source/build-input snapshot
at [n131_rho_reference_source_snapshot_v1.json](n131_rho_reference_source_snapshot_v1.json):
all 53 input paths, sizes, and SHA-256 values match the current tree. Its
status remains source snapshot passed / target binary pending; the local
Darwin/ARM64 binary is stale and ineligible. No rho arithmetic or timing was
run, and the single-target pairing remains unchanged.

**R3 freshness and target-scalar provenance audit (2026-10-06 11:57 UTC):**
the checked-Sage [sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T115749Z.json)
again matched both live processes. Solver CPU advanced about 266 seconds and
the log by 773 bytes since 11:53, with restart 30,179; rank remains `0/14`.
The SAT attempt's `target_scalar_known=true` is for a randomly generated
precomputation relation (`scalar * G`), not the workload Q. Its point hash
differs from Q; the run header says
`primary_target_scalar_available_to_solver=false`, and the runner source
decomposes the official Q only after reusable logs are ready. This resolves
the apparent scalar leak without changing the one-target protocol. The d10,
d13, and m12 continuations are still identity-matched and waiting for R3 to
drain; none has launched a second SAT run.

**R3 live poll and N131 result audit (2026-10-06 12:01 UTC):** the checked-
Sage [sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T120116Z.json)
matched both R3 processes. Solver CPU advanced about 206 seconds and the SAT
log by 779 bytes since 11:57; last write is 11:58:15 UTC. Rank remains
`0/14`, with no terminal result. A candidate-bound audit of the current
N131 result files found 16 one-target `IC1N131` rows, zero recovered primary
targets, zero primary-target online times, and zero rho times. There is no
completed candidate to promote or switch to; R3 and the drain-gated
single-target d10/d13/m12 continuations remain the current route.

**Pinned-control versus natural-query check (2026-10-06):** the one
`VERIFIED_RELATION` in the candidate-bound audit is the h-aa159 binary-leaf
pinned control, which solved and replayed in 1.92 seconds. The same candidate
on official workload `3c1992b7c92f` was parent-censored with no model after
600 seconds. Its control result explicitly sets `result_is_full_dlp: false`;
it is not natural relation-yield evidence and does not qualify as a candidate
win. The active h9bb R3 run is still searching its first random precomputation
relation.

**Queued m12 candidate size and gate audit (2026-10-06 12:11 UTC):** the
frozen `IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0ha088b3d8e4a0`
preflight remains `WAIT_FOR_R3_DRAIN`; its final controller remains
`WAIT_FOR_D10_AND_D13_TERMINAL`, `target_count=1`, `batch=false`, and has
launched no solver. Its static formula receipt has 232,244 variables and
228,629 clauses, compared with about 728,000 variables and 830,130 clauses in
the live m15 query log (about 68% fewer variables and 72% fewer clauses).
This is a formula-size comparison only, not a solve-time result. The m12
method uses 1,083,108 actual factor-base points folded to 4,134 columns; its
protocol allows up to 8,192 sequential singleton precomputation queries
capped at 600 seconds each, and caps the one official-Q online query at 7
days. The smaller query and much larger relation rank make this the strongest
queued candidate to test after the gates, but no natural m12 relation or
official-Q solve has been measured yet.

**m12 positional-domain and count audit (2026-10-06 12:31 UTC):** source
review found that the frozen candidate description incorrectly said
lexicographic leaf sorting quotiented permutations. The formula instead binds
leaf `i` to its own Frobenius-conjugate domain `F_i`; the exact geometry proves
those domains meet only at the excluded zero element. I corrected the
prelaunch manifest, archived the prior identity, and froze the corrected
candidate as
`IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0h36143c49e85d`.
Its refreshed one-target rho identity audit passes the exact curve, generator,
Q, subgroup, and workload checks; no rho walk or timing has run.

The reproducible
[model-count audit](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/d13_m12_model_count_heuristic_audit_v1.json)
computes about 37.49 million ordered signed decompositions per cofactor-fiber
endpoint under the builder's uniform full-curve-sum assumption. This corrects
the earlier back-of-envelope estimate. It is a combinatorial expectation, not
a measured relation yield or SAT success rate. The protocol still runs
sequential one-query preparation attempts for the single public target, with
up to four returned models per query; it is not a multi-target batch. At the
maximum four-model yield, 1,098 queries would reach the first 4,390-row rank
check, while the 8,192-query cap permits at most 32,768 rows. The worst-case
serial query budget is 56.89 days. Solver success, verified natural rows, and
novel rank remain unmeasured.

The refreshed checked-Sage
[R3 sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T123121Z.json)
still matches the active processes, with rank `0/14`, no terminal result, and
no usable relation. The corrected m12 candidate's fresh checked-Sage
[preflight](n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/single_target_preflights/d13_m12_20261006T123423Z.json)
also returns `WAIT_FOR_R3_DRAIN` with no solver launch. Its continuation is
live at `WAIT_FOR_D10_AND_D13_TERMINAL`, with `target_count=1` and
`batch=false`; the active R3 candidate continues independently, while the
corrected m12 full run and rho solve have not started.

**R3 poll (2026-10-06 12:36 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T123608Z.json)
still matches both recorded processes and shows rank `0/14`, no terminal
result, and no natural relation. The d10 and d13 states remain
`WAIT_FOR_R3_DRAIN`; the corrected one-target m12 controller is still gated.

**d10 record correction and candidate comparison (2026-10-06 12:49 UTC):**
the queued d10/m15 manifest had the same inaccurate leaf-permutation claim as
the earlier m12 record. I corrected and re-froze it as
`IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0hcaa3ab9d3890`,
preserving the old h35d manifest and protocol. Its checked-Sage preflight
returns `WAIT_FOR_R3_DRAIN` with no solver launch, and the refreshed one-target
[rho identity audit](n131_rho_reference_identity_audit_v7.json) passes all 18
checks. The d10 monitor was verified live again with the corrected ID; R3 was
not interrupted.

The reproducible
[static comparison](n131_d10_m12_static_candidate_comparison_v1.json) points
to m12 as the stronger online-query candidate to test: it has 17.8% fewer
variables and 18.0% fewer XOR rows than d10, with 1.6% more clauses, and its
uniform-sum model-count heuristic is about 40 times larger. d10 has 532
relation columns compared with m12's 4,134. Both runners ask for one model
for the one supplied public Q; these static counts do not prove SAT speed,
natural relation yield, rank recovery, or a verified DLP. The [d10 result
record](n131_phi_torsion_frobenius_domains_20261005/m15_d10_static/RESULT.md)
preserves its one-target gate and limitations.

The latest checked-Sage
[R3 sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T124911Z.json)
at 12:49 UTC still matches both active processes. Solver CPU is about 19,740
seconds above the fixed baseline, with 272,093 new log bytes; rank is `0/14`
and no terminal result exists. The corrected d10 and m12 candidates remain
queued behind this single active run.

**R3 identity and continuation check (2026-10-06 12:55 UTC):** the fresh
checked-Sage [R3 sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T125345Z.json)
still matches the recorded runner and solver identities. Since the fixed
06:56 UTC baseline, solver CPU advanced about 20,012 seconds and the SAT log
grew by 273,410 bytes. The latest log shows restart 30,276; rank remains
`0/14`, no relation is available, and there is no terminal result. The
checked-Sage runtime receipt is
[saved alongside it](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/sage_runtime_info_process_monitor_202610061253Z.json).

The d10 continuation PID 48071 is alive in `continue_d10_after_r3.py --stage
wait`; the m12 continuation PID 26881 is also alive. Their latest state files
remain `WAIT_FOR_R3_DRAIN` and `WAIT_FOR_D10_AND_D13_TERMINAL`, respectively,
with `target_count=1` and `batch=false`. Neither has launched another solver.
The active R3 manifest's permutation-ordering entry was also checked against
its executed code path: the run calls `decompose(..., "candidate", ...)`,
whose encoder enables `orderPoints`, and the candidate's recorded encoder
and solver source hashes match the checked files. This confirms the R3
manifest's lexicographic point-ordering description; no active run files were
changed.

Checked-Sage validation at 12:55 recompiled the d10/m12 and audit scripts,
reran the static candidate comparison (`PASS_STATIC_COMPARISON`), the d10 rho
identity audit (`PASS`, 18 checks), and the m12 combinatorial count audit
(`PASS_STATIC_IDENTITY_AND_ARITHMETIC`). These checks leave m12 as the stronger
static online-query candidate, but provide no natural relation yield, target
solve, rho timing, or speedup result.

**Sparse m16 identity correction and three-way comparison (2026-10-06 13:12 UTC):**
the frozen sparse-seed m16 record claimed lexicographic point sorting to remove
leaf permutations, while its actual formula builder constrains each leaf to a
distinct Frobenius position domain `F_i` and imposes no sorting constraint. I
preserved the old manifest/protocol and corrected the current identity to
`IC1N131Ckb1fb71788PDP16satRCdirectLAgaussTDdirectISO0h4487b507a43d`.
The formula bytes and algorithm implementation are unchanged. The
[identity-correction receipt](n131_phi_torsion_frobenius_domains_20261005/m16_static/sparse_seed_point_ordering_identity_correction_v1.json)
records the evidence; a fresh checked-Sage
[preflight](n131_phi_torsion_frobenius_domains_20261005/m16_static/single_target_preflights/sparse_m16_20261006T130911Z.json)
accepts the corrected manifest and remains `WAIT_FOR_R3_DRAIN` with no solver
launch.

The reproducible
[three-candidate comparison](n131_d10_m12_sparse_m16_static_candidate_comparison_v1.json)
rechecks d10/m15 and m12, then adds sparse m16. All three bind the same curve,
workload `3c1992b7c92f`, and exactly one supplied public Q. M12 leads the
static online-query signals: 232,244 formula variables and about 37.49 million
uniform-sum models per endpoint, versus 24,297 for sparse m16 and 931,526 for
d10. Sparse m16 has a 274-column matrix, compared with 532 for d10 and 4,134
for m12. These are design heuristics, not measured yields or solve times; m12
is the first online-query candidate to prioritize after the existing single-
solver queue drains, while sparse m16 is a lower-width fallback.

**R3 and queue status (2026-10-06 13:13 UTC):** the checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T131356Z.json)
matched the active solver and runner. Since the fixed 06:56 UTC baseline,
solver CPU increased by about 21,218 seconds and the log by 280,323 bytes;
rank is still `0/14`, no relation is available, and no terminal result exists.
The checked-Sage runtime receipt is
[saved here](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/sage_runtime_info_process_monitor_202610061313Z.json).
The d10 watcher, d13 single-target probe watcher, and m12 full-candidate
watcher were directly verified alive. Their states remain `WAIT_FOR_R3_DRAIN`,
`WAIT_FOR_R3_DRAIN`, and `WAIT_FOR_D10_AND_D13_TERMINAL`; each continues to
use one target, and no queued solver has started.

**R3 poll and identity recheck (2026-10-06 13:17 UTC):** the new checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T131747Z.json)
again matches runner PID 99052 and CryptoMiniSat PID 99169. Since the fixed
06:56 UTC baseline, solver CPU increased by about 21,448 seconds and the log
grew by 280,711 bytes. The SAT log's last recorded modification is 13:13:57
UTC; rank remains `0/14`, no relation is available, and there is no terminal
result. The runtime receipt is
[saved beside the sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/sage_runtime_info_process_monitor_202610061317Z.json).

The d10, d13 probe, and m12 full-candidate controllers remain alive and
gated, with no candidate SAT process launched. Their protocols and the m16
preflight all specify one target and `batch=false`. A fresh read-only
consistency check confirms the corrected sparse-m16 candidate record digest,
candidate-ID suffix, protocol-to-manifest hash, correction receipt, and
unchanged formula hash agree. Its status remains `WAIT_FOR_R3_DRAIN`; the
three-way d10/m12/m16 comparison remains static evidence only.

**R3 poll and explicit probe-state compliance (2026-10-06 13:24–13:27 UTC):**
the next checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T132456Z.json)
still matches the active solver identities. Solver CPU is about 21,876 seconds
above the fixed baseline, with 281,488 additional log bytes; the latest log
modification is 13:18:32 UTC, rank is still `0/14`, and no terminal result or
relation exists. Its checked-Sage runtime receipt is
[saved here](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/sage_runtime_info_process_monitor_202610061324Z.json).

The d13 watcher had omitted a redundant `batch` field in its state file even
though its frozen protocol already required one target and `batch=false`. I
added an explicit protocol assertion and state field in
`d13_m12_probe/continue_after_d10.py`, syntax-checked it with repository Sage,
and restarted only the idle watcher after verifying its PID and wait status.
The new state and preflight both record `target_count=1`, `batch=false`, and
`WAIT_FOR_R3_DRAIN`; no solver launched. The replacement watcher is PID 95499.
Its checked runtime receipt is
[saved here](n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/continuation/runtime_receipts/sage_runtime_info_batch_state_fix_20261006T1326Z.json).
The d10 and m12 controllers remain alive and sequentially gated behind the
same active R3 run.

The active R3 run's immutable `started.json` also omitted `batch` while its
frozen protocol and workload both require one target and `batch=false`. I left
that start record unchanged and added a
[compliance audit](n131_w2_m15_official_single_target_4g_r3_20261004/runs/IC1N131Ckb1fb3668PDP15satRCdirectLAgaussTDdirectISO0h9bb927d6e658W3c1992b7c92fR3/single_target_batch_compliance_audit_v1.json)
that verifies the singleton target list and all counts, records the omitted
field transparently, and confirms the repeated precomputation requests are
sequential one-target queries. This audit makes no relation, DLP, timing, or
speedup claim.

**m15 run-history audit (2026-10-06 13:40 UTC):** I compared all three
single-target preparation attempts for the same frozen candidate and public
workload. Their query XCNF hashes and preparation/solver seeds differ, so R3
is not an exact replay. R1's solver process is documented absent, with no
terminal result or known stop cause. R2's first attempt ended as `budget` after
32,124 seconds, with rank still `0/14` and 2.91 GB peak RSS; it has no
run-level terminal result. R3 remains live on its distinct query under the
seven-day query cap, at rank `0/14` after about 124,663 solver CPU-seconds
(34.6 hours) in total.
The [history audit](n131_phi_torsion_frobenius_domains_20261005/m15_r1_r2_r3_precomputation_history_audit_v1.json)
preserves those attempt states without treating them as measured zero yield.
The queued d10 and m12 candidates have substantially smaller static formulas
and stronger uniform-sum heuristics, but still no measured yield; their
sequential one-target queue remains in force.

**Kissat input-format failure and refreshed one-target queue (2026-10-06 14:00 UTC):**
The bounded Kissat diagnostic used the exact same R3 setup point, with
`target_count=1` and `batch=false`. Its formula is CryptoMiniSat extended
DIMACS, not plain DIMACS CNF: after 1,054,158 CNF clauses it contains 523,995
native XOR records, including 15 width-130 equations. The freeze check looked
only for records starting `x ` and missed the actual `x-...` form. Kissat
parsed the header, rejected the first XOR record with exit code 1, and never
started search. The result file's `NO_VERIFIED_RELATION` label is therefore
not evidence of zero natural yield; the separate
[audit](n131_w2_m15_kissat_same_target_r3_20261006/run_r1/producer_failure_audit_v1.json)
classifies it as a producer/input-format failure. The failed attempt's 1.410 s
and 1.29 GiB combined RSS remain recorded as failed-stage costs. Its
[result note](n131_w2_m15_kissat_same_target_r3_20261006/RESULT.md) keeps the
protocol, source formula, and original result immutable.

The checked-Sage
[sample](n131_phi_torsion_frobenius_domains_20261005/continuation_20261006/r3_live_resource_sample_20261006T140025Z.json)
confirms R3's runner and CryptoMiniSat worker remain alive on the same frozen
one-target query. At the sample, the log was 4,860,446 bytes and last updated
at 13:57:12 UTC; its latest restart line showed restart 30,298 and about
145,314K conflicts. No terminal run result exists. The d10 and d13 probes
remain `WAIT_FOR_R3_DRAIN`; the m12 full-candidate watcher remains
`WAIT_FOR_D10_AND_D13_TERMINAL`. All three still record one target and
`batch=false`; no queued solver has started. Their current states and watcher
processes were checked directly.

The IC-boundary autolab plan, preflight, and status were refreshed read-only
in `/Volumes/SSD990/crypto`. Preflight passes with ledger schema v2 and the
Rust/producers present. Its latest stored n=41 one-target result remains
`INDEPENDENT_VALIDATION_PASS` but `NOT_PROMOTED`; it is separate small-curve
evidence, not an ECC2K-130 speedup. No timing beat was launched while this
long N131 computation occupies the shared host. The N131 objective remains
open: no public-Q IC solution, same-point rho timing, or isolated speedup is
available yet.
