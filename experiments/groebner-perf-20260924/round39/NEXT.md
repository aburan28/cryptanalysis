# Decisions after the first native screen

Keep the screen's exact-output checks, scalar first-pivot control, source hashes
and failed controls. Inspect selector work separately from row/proof work before
turning any counter difference into an implementation decision. Full forward
proofs are a diagnostic; the accepted producer can stop at its first checked
contradiction and reconstruct one proof later.

An available refinement is bounded: stop the coefficient-combination search as
soon as the all-one function is in the span of the inspected coefficients.
Existing coefficient pivots are never modified by later insertions, so once
the target reduces to zero its chosen original-row combination is unchanged
by subsequent inputs. The complete output rows and proof matrices must still
match the original full-scan policy. Test both absent-unit and rank-changing
blocks; do not assume every block offers a common pivot. However, the completed
v1 screen shows that even eliminating all search work leaves 1.786–1.835 times
the scalar word XOR count in the unchanged row-update schedule, plus partial
coefficient ANDs. This refinement is therefore lower priority than changing
the dominant work. It has not been implemented or measured.

For any next sharing policy, retain separate results for:

- coefficient-search work;
- packed coefficient elimination, including partial-function ANDs;
- proof propagation/reconstruction;
- packing and exceptional-lane handling;
- whole verified-query cost against the accepted implementations.

If function-valued elimination still increases the dominant work, preserve the
negative result and avoid replacing the accepted query path. A different proof
representation, per-lane masked pivots, or cooperative GPU implementation would
be a new hypothesis with new checks, not an implied consequence of shared rank.

The next CPU hypothesis targets the currently repeated row construction
in `round37/producer.cpp:multiplier_identity_width`. Each original equation is
scanned again for every degree-one multiplier. Precompute only invariant
monomial-product layouts and form fresh packed original rows per branch. Test
small-chunk lookup transforms or sparse set-bit remapping against the existing
coefficient scan. Charge lookup construction separately as reusable setup;
charge each branch's coefficient transpose and all row generation to the query.
Measure table traffic and code size as well as latency. Preserve source-row
order, pivot order, budgets and exact certificate bytes in the first candidate.

Neither this screen nor reduced operation counts establish a faster complete
query. Keep the earlier qualified 27-variable implementation in every paired
comparison, retain the fastest earlier GPU, and repeat qualification under the
unchanged resource/load boundary before dispatch changes. All ordinary
failures, budget fallbacks and independent verification remain charged.
