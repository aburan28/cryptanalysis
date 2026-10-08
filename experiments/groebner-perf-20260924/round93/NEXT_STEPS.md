# Remaining performance work

1. Complete the existing PR sequence without changing frozen numeric sources.
   Require full CI and audited artifacts before the authorized merges. At the
   latest PR345 snapshot, the 60 remaining queued checks are all macOS jobs;
   runner availability has not been established as their cause.
2. Reduce successful derivation verification cost and memory. A useful next
   experiment is DAG liveness: count future uses, release a polynomial value
   after its last use, and measure peak live terms separately from total terms
   materialized. Define any changed retention-budget semantics explicitly;
   preserve a legacy policy and test shared children, duplicate operands, unused
   nodes, output references, malformed graphs and exhaustion/recovery. Acceptance
   must still include both ideal inclusions and Boolean completion.
3. Reduce normal-form cost for completion. The 16-variable rejected candidate now
   spends its time finding a critical-pair obstruction. Profile leading-monomial
   search, divisor lookup and polynomial XOR separately; retain independent
   arithmetic and test adversarial reducer sets before sharing/indexing metadata.
4. Continue the complete single-query GPU experiment: instrument joined producer
   transform/projection, preserve its one-submission path, and charge conversion,
   transfer, scheduling and independent checks. General sparse F4 GPU matrices
   must retain row-combination proofs. Keep CPU dispatch until matched complete
   measurements justify routing.
5. Test invariant sparse layout closures and structural F6 hypotheses against
   the same difficult nonlinear families, with explicit applicability and proof
   obligations. Neither layout reuse nor reordered checking is a new asymptotic
   algorithm. A proved improvement in hard high-regularity solving remains open.

The full goal remains active. The new schedule improves some unsuccessful
algebraic attempts; it has not established another qualified 2x complete-query
speedup, full independent curve replay, general single-query GPU crossover, or a
new F6 complexity bound. Qualified CPU timing still requires host isolation.
The larger IC gate remains one unseen public target with independently verified
recovery, paired with rho on the same point and resources. No polynomial-stage
control substitutes for that end-to-end measurement.
