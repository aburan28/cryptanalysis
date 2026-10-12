# Buffer transfer and accounting contract

The checker operates on a validated forward-reference-free derivation DAG.
Its existing use counters include every operand occurrence and every output
reference. For an XOR of distinct values, a counter of one proves that the
current node is that operand's last use. The left operand is preferred when
both qualify. Same-operand XOR retains the allocating path. Without use counters
(keep policy), reuse is disabled.

Before any ownership change, the candidate reserves exactly the existing
`left.terms + right.terms` charge and three words-per-value charges. Those are
conservative budget charges, including avoided initialization. A budget failure
therefore occurs at the same logical point as the reference when the physical
byte cap is ample. No term work is discounted and no fallback gets a fresh
budget. All successful numerical and semantic checker records must match.

Transferring the vector leaves the donor's word vector empty and its original
term count intact. The result XORs the other operand into those words and counts
its own terms. Ordinary logical reclamation later subtracts the donor's original
term count. It releases zero payload bytes for the moved donor, because that
payload now belongs to the result. The other operand is unchanged until its
normal last-use point. Output references prevent early transfer.

The physical cap covers reserved DenseValue vector metadata, last-use counters
and owned word payloads, as in round102. Allocator bookkeeping, fixed scalar
checker/stat structures, original-input/basis hash sets, transport and process
setup remain outside that explicitly scoped cap and are reflected in process
RSS. A transferred payload is counted once. Reuse may satisfy a physical byte
limit at which the allocating reference is inconclusive; that is tested at the
exact boundary rather than hidden by changing a limit.

`ownership.py` independently simulates buffer ownership and output pins from
the decoded proof. It predicts left/right transfers, fresh payload allocations,
payload releases and maximum simultaneously owned buffers. The native-free
artifact audit combines that prediction with the unchanged word count and
reserved metadata. Successful checks release all payloads. Failure statistics,
as in the reference, describe the point of failure before scope destruction;
RAII destroys any remaining vectors as the checker unwinds. Work/term/byte
boundary tests are followed by successful checks to exercise recovery.

The candidate library is separate from the old dense library. Tests compare
the old library, the candidate library with transfer disabled, and transfer
enabled, including both checker phase orders, all three retention policies,
large-ring sparse fallback, aliasing, unused nodes, cancellation, malformed
proofs, fresh coefficients and concurrent calls. Proof formats and output
ownership are unchanged from round103.

The preset complete-query comparison has four paired arms and 13 frozen cases,
one warmup followed by four rotated observations. Input generation and reusable
layout setup are outside the query; fresh coefficients and independent equation
and curve replay remain inside. All timeouts, failures and inconclusive results
stay in the raw evidence. Local CPU times are diagnostics, with every qualified
speedup null until an auditable host-isolation receipt passes.
