# Next ECC2K point-decomposition gates

The exact point solver in [RESULTS.md](RESULTS.md) passed the complete n=13
control, but its quadratic pair table cannot take the n=83 base of 130,604
signed points under 512 MiB. The exploratory S6 size check in
[S6_DIAGNOSTIC.md](S6_DIAGNOSTIC.md) built 190,252 terms at about 448 MiB
RSS and timed out during Boolean descent. Neither measured an ordinary
full-base n=83 relation. Work in this order:

1. **Correct the target fiber.** The n=83 base consists of `[4]P` with
   original `x(P)<2^17`. For subgroup target `R`, set
   `T=[4^{-1} mod r]R`. The complete rational kernel is
   `{O,(0,1),(1,0),(1,1)}` on `y²+xy=x³+1`. An S6 equation on the original
   `x(P_i)` must examine `T+K` for all four kernel points. Verify the kernel
   by doubling, check that all four lift to `R`, then exhaustively compare
   the encoded search and exact signed point addition on a small complete
   base. Reject algebraic roots without `[4]ΣP_i=R`. Record both projected
   and original targets; a planted witness only checks correctness.

2. **Build a bounded compact encoding.** Specialize S6 coefficients to
   each of the four target x-values *before* expanding Boolean monomials.
   Stream or factor the sparse tensor and store a reproducible digest for
   each equation set. Measure peak RSS, terms, degree and wall time for every
   kernel branch, including setup and failed branches. First require
   complete encoding under 512 MiB and 120 seconds at n=31; then repeat
   at n=83, l=17. If it cannot finish at n=83, retain the timeout and try
   an implicit phase-aware chain with explicit intermediate point validity.
   Do not infer solve time from an encoding count.

3. **Get ordinary relations on n=31 before n=83.** Construct and archive an
   exact subgroup-valid x-subspace base for the same Koblitz model, then
   freeze at least five independent streams of uniform subgroup targets.
   Make the three-summand direct control, compact five-summand SAT, F4 and
   F5 candidates consume the *same* base and streams; cap each attempt and
   retain all failures. Extract signs, cofactor projection and exact rows,
   and stop each arm only at independent rank eight or its frozen budget.
   n=31 is an algorithm development gate: its curve order factors as
   `4·373·1,439,393`, so its largest prime subgroup is much smaller than
   n=83 and its yield is not an ECC2K83 rate estimate.

4. **Promote only a solver that actually handles the full n=83 base.** Freeze
   target streams and resource limits before the run. Charge base and
   workload construction, all kernel branches, failed and timed-out
   attempts, witness verification, repeated/dependent rows and rank
   updates. Compare total wall time per new independent verified row with
   the fastest same-base control over at least five streams. A ≥2× claim
   requires both arms to reach rank eight and the paired cost gate to pass;
   zero-yield cells stay in the record. The existing 13.10% five-summand
   *upper bound* is only a feasibility screen, not a yield prediction.

After a full-base relation-collection result, measure the cost of the
65,302-column sign-folded sparse relation matrix, final linear algebra and
single-target descent separately. Those phases are unknown today.
