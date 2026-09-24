# Sage arithmetic campaign for local index-calculus work

The table is an experiment queue, not a list of proven speedups. Each item has
a concrete implementation site and a complete-operation boundary. Promote a
change only after exact output checks, paired incumbent/candidate measurements
with independent confirmation inputs, resource accounting, and a source/binary
binding. Keep failed attempts. For an IC claim, use the repository's candidate
IDs and charge every exclusive phase through verified logarithm recovery.
Metal kernel timing is diagnostic; a PR must report complete Sage-point or
solver cost, including packing, transfers, construction and verification.

| # | Candidate site | Mechanism to test | Evidence and next gate |
| ---: | --- | --- | --- |
| 1 | `binary_batch.py:frobenius_points` and `binary_batch_ntl.pyx` | Native NTL coordinate squaring and standard point construction | **PASS_LOCAL**, 2.15x primary and 2.31x confirmation over the prior Python API; PR #72 is open. |
| 2 | `binary_hardware_codec.pyx:unpack_points` | Cache the point homset and initialize verified normalized outputs directly | **PASS_LOCAL** after a noisy held pilot: 1.85x primary and 1.79x independent confirmation geometric means over complete CPU/Metal point calls; package as a stacked PR. |
| 3 | `binary_hardware_codec.pyx:pack_points` | Reduce per-point Python validation/`xy()` work while retaining exact curve and class checks | **PASS_LOCAL** after a held first candidate: 1.337x primary and 1.258x confirmation complete-API geometric means; package as a stacked PR. |
| 4 | `binary_hardware_metal.mm:bh_metal_apply` | Pack into reusable shared Metal input storage and reduce host copies | **HELD as a standalone target.** Instrumented warm host copies totaled only 0.002–0.019 ms across 1,024–16,384 points in two runs; removing them cannot explain the observed complete-call gap. Keep the exact copy and working-set controls while testing a larger mechanism. Receipts: `metal-host-timing-20260924/`. |
| 5 | `binary_hardware.py:FrobeniusPlan.apply_batches` | Batch independent same-plan point maps into one backend dispatch | **PASS_LOCAL for explicit batching, HELD for automatic Metal routing.** Four frozen degree-131 cells with 4 or 16 batches improved full warm Metal point calls 1.98–2.84x; matched batched CPU still won all cells. Separate cold processes also favored CPU. Exact patch and receipts: `metal-batched-point-maps-20260924/`. |
| 6 | `binary_hardware.py:kernel_source` | Assign one Metal thread per field element and reuse decoded bytes across output words | **HELD.** The dynamic-array kernel was 7.6–12.9% slower in two full-call pilots. A static-word variant gained 17.6% in one 4,096-point pilot but was slower in both independent 4,096-point confirmations and the 16,384-point cell; batched CPU remained faster. Exact negative receipts: `metal-element-kernel-20260924/`. |
| 7 | `binary_hardware.py:kernel_source` | Reorder table layout for coalesced Metal reads | Current table index is byte/digit/word; profile device memory behavior before editing. |
| 8 | `binary_hardware.py:FrobeniusPlan._make_table` | Vectorize the lookup-table recurrence over `uint32` rows | **PASS_LOCAL** on the PR #75 source: 1.369x primary and 1.339x confirmation cold CPU means; three of four Metal cold diagnostics improved, degree-19 Metal measured 0.968x. Standalone patch and held pilot archived in `table-build-20260924/`. Native NTL basis-image construction remains a possible next experiment. |
| 9 | `binary_hardware_cpu.cpp:transform/dispatch` | Specialize common word widths and avoid repeated index arithmetic | Compare complete CPU plan against current CPU and native NTL on degree 19/67/131. |
| 10 | `binary_hardware.py:FrobeniusPlan.apply` | Select native NTL or a reusable CPU/Metal plan from measured size/power/cold-cost boundaries | Draft PR #76 routes selected large power-65 lists and gives >5x cold gains there, but its nonrouted empirical gate remains unresolved; remeasure thresholds on the new table source before promotion. |
| 11 | `binary_batch_ntl.pyx:_add_prepared` | Reduce Python pair validation and coordinate extraction | Prior profile showed native work and output construction share; measure complete `add_pairs`. |
| 12 | `binary_batch_ntl.pyx:_add_prepared` | Separate exceptional sums from active inversion storage | Exact duplicate, inverse, order-two, and infinity behavior must remain; measure exception-heavy and natural inputs. |
| 13 | `binary_batch_ntl.pyx:_add_prepared` | Rework Montgomery prefix storage or inversion scheduling | Preserve one inversion and `3(n-1)` reciprocal products; compare exact full calls. The simple reserve/emplace candidate was held at 1.002x. |
| 14 | `binary_batch.py:add_cartesian` | Stream native blocks without Python pair-list materialization | Charge all points and output list, including edge block sizes and memory peak. |
| 15 | `ell_point.py:EllipticCurvePoint_field._add_` | Specialize ordinary binary scalar addition | **PASS_LOCAL** after three held prototypes: 1.177x primary and 1.182x binary confirmation geometric means over public `P+Q`; prime and unsupported-model controls also improved. Standalone patch and receipts in `scalar-add-20260924/`. A real IC reference call path remains to be integrated. |
| 16 | `ell_point.py` scalar multiplication path | Reduce repeated binary-field point allocation in public scalar multiples | Profile before changing generic point semantics; verify subgroup and exception cases. |
| 17 | `hom_frobenius.py:EllipticCurveHom_frobenius._call_` | Reuse native NTL binary squaring for standard Koblitz point evaluations | **PASS_LOCAL** after a held custom-point guard: 11.128x primary and 11.226x confirmation geometric means over public warm `phi(P)` calls; cold constructor plus first batch also improved. Standalone patch and all receipts are in `frobenius-hom-20260924/`. |
| 18 | `element_ntl_gf2e.pyx` GF(2^m) squaring/Frobenius | Reduce context setup or reuse field temporaries in repeated public operations | Only promote after field-level and containing point-operation gains; cover alternate moduli. |
| 19 | `pbori/gbcore.py` nonlinear pair and reducer selection | Reduce work seen in complete Boolean Gröbner profiling | Existing dispatch and fixed batch-cap trials were held; use larger representative PDP systems and exact bases. |
| 20 | `pbori` native matrix construction/reduction | Reduce Macaulay conversion and interreduction cost before considering Metal | Prior standalone Metal RREF was 9–21x slower than M4RI on tested matrices; profile stage costs and retain CPU control. |
| 21 | `binary_batch_ntl.pyx:_frobenius_one` | Restore NTL context before coordinate extraction and use one-point native squaring from `hom_frobenius.py` | **PASS_LOCAL** over PR #78 after a held context bug: 1.251x primary and 1.154x confirmation warm public-call means, exact field-switch suite and 116 hom doctests. Standalone patch and receipts in `frobenius-singleton-20260924/`. |
| 22 | `binary_batch_ntl.pyx:_construct_standard_point` | Initialize the C-level parent and affine coordinates for verified standard finite-field outputs | **PASS_LOCAL** within the public-addition patch: GF(101) and unsupported binary controls improved 2.045x and 1.482x; the Python-only prototype failed parent identity. Keep the constructor coupled to `ell_point.py`'s guarded call site. |
| 23 | `ecc2k130/{codegen,runner/codegen}/curves.py:Curve.mul` | Use a width-4 signed window for ONB scalar multiplication of 32 bits or more | **PASS_LOCAL**: all 16 frozen primary/confirmation cells were exact; 32–131-bit complete scalar calls improved 1.132–1.367x and 16-bit controls stayed within 1%. Both real copies are changed, with tests and receipts in `onb-scalar-window-20260924/`. A full IC total remains unmeasured. |
| 24 | `ecc2k130/{codegen,runner/codegen}/curves.py:Curve.mul` | Recode large Koblitz scalars in the Frobenius endomorphism ring | **PASS_LOCAL over row 23**: exact tau identity and exhaustive small-field checks; all twelve 32–131-bit primary/confirmation cells improved 1.487–1.848x warm and at least 1.383x first-call. The tracked runner `AuditField` is included. Source and receipts: `onb-tau-adic-20260924/`. Charge complete IC phases before a DLP claim. |
| 25 | `ecc2k130/{codegen,runner/codegen}/curves.py:CurvePb.mul` | Apply exact Koblitz Frobenius recoding to polynomial-basis curves | **PASS_LOCAL**: exhaustive small-field and 20 frozen paired cells. For 8–64-bit scalars, complete calls improved 1.381–2.028x primary and 1.618–1.976x confirmation; first calls improved too. Both real code copies changed. Source and receipts: `pb-tau-adic-20260924/`. |
| 26 | `ecc2k130/{codegen,runner/codegen}/field.py:Pb.inv` | Replace Fermat exponentiation with polynomial extended Euclid | **PASS_LOCAL** over row 25: exact exhaustive small-field and random wide-field checks. Twelve frozen local/runner cells improved inversion 14.5–91.4x, complete point addition 4.86–25.70x, and complete scalar calls 2.63–12.11x. Source and receipts: `pb-euclid-inverse-20260924/`. The IC total remains unmeasured. |
| 27 | `ecc2k130/{codegen,runner/codegen}/field.py:Pb.sqr` | Expand even polynomial coefficients by byte before modular reduction | **PASS_LOCAL** over row 26: exhaustive small-field and 16 frozen paired cells. Complete 256-square batches improved 1.46–2.66x, and three-point 32-bit scalar calls improved 1.20–1.58x across both copies and independent seeds. Source and receipts: `pb-squaring-20260924/`. |
| 28 | `ecc2k130/{codegen,runner/codegen}/curves.py:CurvePb.trace` | Derive a lazy trace mask from Newton sums of the field polynomial | **PASS_LOCAL** over row 27: exhaustive small-field and 16 frozen paired cells. Complete 64-point recovery batches improved 1.72–2.97x primary and 1.73–2.57x confirmation; first calls including mask setup improved at least 1.36x. Source and receipts: `pb-trace-mask-20260924/`. |
| 29 | `ecc2k130/{codegen,runner/codegen}/field.py:Pb.mul` | Use sparse-bit or nibble carryless products | **HELD in exploratory pilot**: sparse-bit iteration regressed field batches at every tested degree; nibble products regressed degrees 11/15 and only helped larger fields. Exact paired samples are in `pb-mul-pilot-20260924/`. A degree-specific path needs independent confirmation and cold accounting. |
| 30 | `ecc2k130/{codegen,runner/codegen}/curves.py:CurvePb.halfTrace` | Cache basis-vector half traces and XOR selected images | **HELD for automatic activation**: degree-131 cold 64-point batches were 0.27–0.28x and cold 256-point batches 0.92–1.03x across frozen primary/confirmation, despite 5.76–6.03x warm 256-point gains. Cold 1024-point batches improved 2.59–2.68x. Exact samples: `pb-halftrace-pilot-20260924/`. Test an explicit bulk policy with full IC charge. |
| 31 | `CurvePb.prepareHalfTrace` and `runner/codegen/indexcalc.py:factorBase` | Explicitly prepare half-trace images for declared polynomial-basis factor-base work | **PASS_LOCAL stage**: exact factor-base points and Frobenius orbits in eight frozen cells. Complete cold `factorBase` calls improved 1.300–4.019x over degrees 11/13/53/131; degree 131 was 4.019x primary and 4.001x fresh-process confirmation, with preparation charged. The CLI opt-in is `--basis pb --bulk-half-trace`. Source and receipts: `pb-bulk-halftrace-20260924/`. No complete IC/DLP total yet. |

The executable degree-131 IC reference in `ecc2k130/codegen/indexcalc_e2e.py`
currently performs most field and curve work in its own Python ONB classes and
uses a separate SAT/F5 path. Sage's faster arithmetic therefore has **no
automatic end-to-end IC speedup**. A later integration must run a frozen
workload with complete phase accounting and a verified recovered log. The
Metal rebaseline is in `metal-rebaseline-20260924/`.
The later installed-codec CPU/Metal comparison and phase receipts are in
`metal-current-profile-20260924/`; they supersede the older timing boundary
for this Apple M4 Pro installation. PRs #81–#89 separately improve local and
tracked-runner Python ONB arithmetic, with cold and warm receipts in their
individual archives. The tracked IC runner already overrides inversion and
trace, so public-API ratios for those operations are not incremental IC
pipeline speedups.
The following `metal-host-timing-20260924/` archive repeats identical-seed
cells and profiles a standalone bridge. It finds host copy removal too small
on its own and shifts the next Metal experiment to command batching. Because
absolute timings varied across independent runs, keep CPU and native Sage as
paired controls in any dispatch threshold experiment.
The next `metal-batched-point-maps-20260924/` archive supplies an explicit
batching API and complete point-call results. It does not change automatic
routing. Row 6 then tested a per-element kernel against the same batched CPU
and native Sage controls.
The subsequent `metal-element-kernel-20260924/` pilots held row 6 after
independent confirmation. Row 7's table access layout is the next measured
Metal hypothesis. Keep the word-kernel and batched CPU as paired controls.
The following `onb-scalar-window-20260924/` archive changes both local ONB
curve copies. Scalar-call measurements are paired and verified, but should
not be substituted for a complete IC run's charged phase total.
`onb-tau-adic-20260924/` replaces its large-scalar path with exact
Frobenius recoding; the signed-window result remains as the paired parent.
`pb-tau-adic-20260924/` applies the same verified curve relation to the
polynomial-basis path used by the runner when a type-II ONB is unavailable.
`pb-euclid-inverse-20260924/` accelerates that path's field inversion and
measures both direct inversions and containing curve calls. It does not infer
an IC speedup from those stage measurements.
`pb-squaring-20260924/` further accelerates the Frobenius-heavy polynomial
basis scalar path. The standalone field gain is supported by the containing
point-scalar gain, while a complete IC total remains a separate measurement.
`pb-trace-mask-20260924/` turns a repeated Frobenius trace loop into a cached
linear form. The first-call result includes the lazy construction, and the
complete point-recovery result bounds its practical effect.
`pb-halftrace-pilot-20260924/` retains the next cold/warm experiment. Its
degree-131 setup threshold keeps the cached half-trace path out of automatic
routing until a caller can declare enough point queries and charge setup.
`pb-bulk-halftrace-20260924/` supplies that explicit caller in the polynomial
basis IC factor-base collector. Its opt-in result charges preparation to the
factor-base stage; relation work through verified log recovery remains the
next complete-workload gate.
