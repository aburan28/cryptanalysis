# Next performance steps

The next engineering target is target-dependent input preparation. In the
round-three profile, equation construction takes more time than native basis
computation and independent verification combined. The current resident-code
18-variable query is roughly 45–52 ms on six planted controls. These are PDP
phase diagnostics, not unknown-target IC measurements.

| Priority | Change to investigate | Experiment and acceptance gate |
| --- | --- | --- |
| 1 | Pass packed ANF coefficients directly into native code; avoid expanding into Python sets, sorting, and repacking | Freeze the current interface and compare complete single-query time. Independently reconstruct/check equations and retain curve replay. Target another 2x query improvement as an engineering goal, not a prediction. |
| 2 | Reuse target-independent symbolic structure and buffers | Cache only ring/order/support layouts whose invariance is proved. Do fresh target-dependent coefficients, solving, and certification. Record setup separately and prove identical outputs on unseen target inputs. |
| 3 | Select between Boolean F4/M4RI, signature methods, and evaluation/interpolation using measured costs | Include root-cap failures and every fallback attempt in one query's cost. Validate broader sparse/dense, satisfiable/unsatisfiable, and high-regularity inputs before changing defaults. |
| 4 | Improve GPU latency for one query | Profile pivot-panel work, launch/barrier overhead and CPU/GPU crossover for matrices from one solve. GPU wins only if the full single-query boundary improves. Parallelism inside one target is allowed; accumulating unrelated targets is not the primary objective. |
| 5 | Explore structural algorithms beyond the small Boolean enumeration regime | Test decomposition by separators, low-rank/structured matrix updates, and family specialization with explicit applicability conditions. Preserve exact completion/certification. Existing evaluation/interpolation methods are not a novel F6 algorithm. Any asymptotic claim needs a theorem and adversarial controls. |

## Primary IC measurement gate

When these components are connected to a complete IC candidate, assign the
canonical curve/candidate/workload/run IDs required by AGENTS.md. Freeze one
previously unseen public target point and compare verified IC online wall
time with one-target rho on that same point and resource conditions.

Begin timing at the first target-dependent computation after reusable setup
is ready, and stop only after independently verified log recovery. Charge all
target-dependent equation construction, failed attempts, PDP, relation checks,
descent and recovery checks. Keep process startup and reusable factor-base,
index and log preparation outside this interval, with separate receipts.
Generating the public target from a known scalar is fixture construction and
must be outside both solvers' intervals. No precomputed answer for that target
may be reused. Freeze the exact included timing boundary in the run record.

Retain failures/timeouts/OOMs, actual usable base size and orbit columns,
ordinary-query yield, novel rank, final LA/descent and scalar replay. Missing
costs remain unknown. Planted decompositions establish correctness, not natural
relation yield. GPU batches of unrelated targets are secondary experiments,
after a completed single-target measurement and with an explicit separate
question. They do not establish the primary IC speedup.

## How much headroom is plausible?

A faster 0.9 ms basis kernel has limited effect when a query takes about
47 ms. Eliminating Python conversion work is therefore a better immediate
bet than spending the same effort reducing that kernel alone. Reusable
symbolic structure and adaptive backends could provide further gains on
appropriate families. The 20-variable verifier still enumerates exponentially;
large high-regularity systems require another representation or certificate.
No fixed speedup, globally fastest implementation, or new asymptotic algorithm
is assumed by this plan.
