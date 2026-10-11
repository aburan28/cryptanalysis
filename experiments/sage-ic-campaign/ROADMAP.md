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
| 4 | `binary_hardware_metal.mm:bh_metal_apply` | Pack into reusable shared Metal input storage and reduce host copies | Four fresh profiles show GPU commands at only 0.9–4.6% of Metal API time; isolate copies before editing the buffer ownership model. |
| 5 | `binary_hardware_metal.mm:bh_metal_apply` | Reuse command resources or batch consecutive maps | Metal API cost is 10.7–43.2% of the complete call on profiled cases, with command setup/sync mixed with copies; retain exact CPU control. |
| 6 | `binary_hardware.py:kernel_source` | Assign one Metal thread per field element and reuse decoded bytes across output words | Current kernel repeats byte extraction per word; test exact packed outputs and full calls. |
| 7 | `binary_hardware.py:kernel_source` | Reorder table layout for coalesced Metal reads | Current table index is byte/digit/word; profile device memory behavior before editing. |
| 8 | `binary_hardware.py:FrobeniusPlan._make_table` | Compute basis images and lookup table with native NTL code | Setup is charged and can erase warm gains; compare cold calls and break-even target count. |
| 9 | `binary_hardware_cpu.cpp:transform/dispatch` | Specialize common word widths and avoid repeated index arithmetic | Compare complete CPU plan against current CPU and native NTL on degree 19/67/131. |
| 10 | `binary_hardware.py:FrobeniusPlan.apply` | Select native NTL or a reusable CPU/Metal plan from measured size/power/cold-cost boundaries | Large degree-67/131 power-65 batches pass routed cold and warm confirmation, including an alternate modulus. The strict nonrouted wall-time gate failed on a shared host; a direct same-plan branch measurement bounds added work at 0.12 microseconds. Keep the merge decision reviewable. |
| 11 | `binary_batch_ntl.pyx:_add_prepared` | Reduce Python pair validation and coordinate extraction | Prior profile showed native work and output construction share; measure complete `add_pairs`. |
| 12 | `binary_batch_ntl.pyx:_add_prepared` | Separate exceptional sums from active inversion storage | Exact duplicate, inverse, order-two, and infinity behavior must remain; measure exception-heavy and natural inputs. |
| 13 | `binary_batch_ntl.pyx:_add_prepared` | Rework Montgomery prefix storage or inversion scheduling | Preserve one inversion and `3(n-1)` reciprocal products; compare exact full calls. The simple reserve/emplace candidate was held at 1.002x. |
| 14 | `binary_batch.py:add_cartesian` | Stream native blocks without Python pair-list materialization | Charge all points and output list, including edge block sizes and memory peak. |
| 15 | `ell_point.py:EllipticCurvePoint_field._add_` | Specialize ordinary binary scalar addition | Generic formula and factory are still used for `P+Q`; benchmark Sage scalar and a real IC reference call path. |
| 16 | `ell_point.py` scalar multiplication path | Reduce repeated binary-field point allocation in public scalar multiples | Profile before changing generic point semantics; verify subgroup and exception cases. |
| 17 | `hom_frobenius.py:EllipticCurveHom_frobenius._call_` | Reuse the native coordinate path for repeated maps where domain/codomain permit | Existing call raises every coordinate to the Frobenius degree; compare full isogeny application on fixed curves. |
| 18 | `element_ntl_gf2e.pyx` GF(2^m) squaring/Frobenius | Reduce context setup or reuse field temporaries in repeated public operations | Only promote after field-level and containing point-operation gains; cover alternate moduli. |
| 19 | `pbori/gbcore.py` nonlinear pair and reducer selection | Reduce work seen in complete Boolean Gröbner profiling | Existing dispatch and fixed batch-cap trials were held; use larger representative PDP systems and exact bases. |
| 20 | `pbori` native matrix construction/reduction | Reduce Macaulay conversion and interreduction cost before considering Metal | Prior standalone Metal RREF was 9–21x slower than M4RI on tested matrices; profile stage costs and retain CPU control. |

The executable degree-131 IC reference in `ecc2k130/codegen/indexcalc_e2e.py`
currently performs most field and curve work in its own Python ONB classes and
uses a separate SAT/F5 path. Sage's faster arithmetic therefore has **no
automatic end-to-end IC speedup**. A later integration must run a frozen
workload with complete phase accounting and a verified recovered log. The
Metal rebaseline is in `metal-rebaseline-20260924/`.
