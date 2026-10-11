# Round 60: reusable packed ANF input buffers

The existing input adapter copies a coefficient dictionary and allocates mask
and coefficient arrays for every native solve. This opt-in path allocates arrays
once for a declared support envelope and lends their view to the unchanged
producer and independent checker. Both comparison arms use the same round 58
indexed native engine. The legacy complete-query path remains available.

`PackedDescentPlan` retains the ring-only contraction layout. Each call clears
the contraction buffers, computes fresh target coefficients, and compacts the
nonzero output into existing native arrays. It creates no final ANF dictionary
and does not allocate new mask or coefficient arrays. Compacting is necessary:
the native decoders charge each supplied slot, including zero slots. The packed
descent preserves the old order and zero omission, so partial budget behavior
stays identical. The separate mapping adapter preserves explicit zeros and
dictionary iteration order exactly as the legacy adapter does.

An input lease holds the workspace lock through the native producer, independent
checker, solution extraction and curve/equation replay. Every active slot is
overwritten before the new term count is published; inactive tail storage is
outside the declared view. Exiting or failing a lease invalidates its generation
and resets its visible term count to zero. Stale, nested, wrong-ring, wrong-query
and foreign-thread use is rejected. Other threads may acquire the workspace
after the current lease ends. Raw internal pointers are not a public asynchronous
interface.

The workspace has at most 1,048,576 support slots and 4,194,304 coefficient words
(32 MiB for the coefficient array, separately from masks and Python metadata).
Inputs outside its declared envelope or limits are rejected by this opt-in API;
the legacy adapter remains available. No basis, answer, numerical elimination,
or target-dependent coefficient value is reused for a new query.

The paired benchmark freezes the same 23 inputs and limits as round 59. It
compares legacy input construction with leased buffers, keeping column-indexed
F4 constant. Five primary cases have three trials of seven measured pairs;
18 secondary controls each have one trial of three pairs. Each trial also has
one warmup. A complete panel has 384 query executions. Load admission, failed
attempt retention, independent preflight and paired analysis are unchanged.

All target-dependent preparation and lock acquisition are inside the query
clock. The first phase includes fresh coefficient descent and input preparation;
the final phase includes reference replay and lease teardown. All four exclusive
phases must be present and sum to the total. Offline Python certificate replay
is separate validation. Algebra controls are not complete PDP or IC solves.

Build and run the complete validation with
`python3 run_validation.py --output /absolute/new/evidence/directory`.
Tests exercise exact producer/checker traces, every work budget from 0 through
512, equation bitsets through 4096 equations, zero compaction, fresh target
alternation, invalid fills, stale/nested leases and concurrent workspace use.
The benchmark retains the unchanged exact algebraic checker, original-equation
checks and curve replay. A correctness pass alone does not establish a speedup.
