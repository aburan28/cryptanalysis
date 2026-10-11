# Shared sparse-Horner compilation halves the target-coupled N41 circuit

Compiling the two quartic polynomials together by a shared sparse-Horner DAG
reduces the complete unpinned public-target formula from 312 to **165 field
multiplications**, and from 261,004 to **120,929 AND gates**. The exact
positive public relation satisfies every emitted equation. The frozen
one-worker query remains `BOUNDED_UNKNOWN` at its 60-second solver cap, so the
next algorithmic step is to reduce the remaining nonlinear search in the
target-coupled system before transferring it to the N131 challenge.

## Method and exact checks

The [compiler](circuit.py) evaluates the 60-term `A(a,S,Z,P,Q)` and 16-term
`B(a,S,Z,P,Q)` of the [single-branch quartic identity](../n41_quartic_joint_public_20261010/RESULT.md)
with one memoized coefficient DAG. It uses sparse Horner order
`(S,Z,a,Q,P)`; exponent-gap powers are shared across both polynomials, and
Frobenius squaring is emitted as a linear map. The outer circuit still
constrains all twelve source masks, distinct folded columns, three four-atom
blocks, their existential Artin--Schreier branches, and both joins to the
public point. The extra multiplication by each branch variable `w` contributes
one call per block to the complete 165 count.

The [order search](order_search.json) counts the emitted field multiplications
for all 120 five-variable Horner orders under the same coefficient-sharing
rule. This order is the minimum at 54 multiplications and nine linear squares
per `A,B` block. This is an exact search over axis orders for this compiler;
it is not a lower bound over all arithmetic circuits. The [arithmetic audit](audit_result.json)
evaluates the actual emitted wires on the zero and unit vectors and fourteen
seeded uniform five-tuples in `GF(2^41)`, checking both outputs against direct
monomial evaluation. The [complete control](control_result.json) evaluates
every CNF clause and native-XOR row on the independently audited public
relation assignment.

## Frozen public query

The curve is `y²+xy=x³+1` over `GF(2)[t]/(t^41+t³+1)`, with subgroup
order `549756390943` and public point `(1458168294740,1672312028033)`.
The source has actual base size `B=384`, 26 signed-Frobenius columns, W6 masks
at rotations `0,5,10,15,20,25`, and the same two raw target-lift choices as
the [prior complete circuit](../n41_single_branch_joint_sat_20261011/RESULT.md).
The [protocol](protocol.json) froze source and input hashes before control and
search, one CryptoMiniSat worker, a 120-second construction cap, a 60-second
solver flag with five-second parent margin, and 4 GiB combined RSS.

| Complete public formula | Monomial DAG baseline | Shared Horner |
| --- | ---: | ---: |
| Quartic field multiplications, including `wB` | 312 | **165** |
| Quartic linear squares | 138 | **27** |
| Variables | 408,089 | **196,923** |
| AND gates | 261,004 | **120,929** |
| CNF clauses | 789,713 | **369,488** |
| Native-XOR rows | 146,725 | **75,634** |
| XCNF bytes | 20,045,455 | **9,304,582** |
| Public search status | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` |

The [query receipt](query_result.json) records 4.121 seconds of target-dependent
construction, 0.221 seconds to write and hash the formula, and 65.085 seconds
from solver launch to parent stop, totaling 69.426 seconds. The combined
sampled peak RSS was 208,273,408 bytes. Its formula SHA-256 is
`6ecdac5d8f2ce929d031bef00a35ac4aef8629415833393b204ae5441ab45ba8`.
The [compressed stdout](solver.stdout.gz) shows active restarts through row
171 and about 44,000 conflicts at the stop, with no terminal SAT or UNSAT
line; [stderr](solver.stderr.gz) is empty. The
[terminal audit](terminal_audit.json) checks the source binding, log hashes,
exclusive phase sum, matched baseline resources and target, and operation
counts. The host has no CPU-isolation receipt, so construction and solver
wall times are exploratory stage diagnostics; the exact circuit-size counts
and assignment checks do not depend on timing isolation.

The next experiment should compile the exact factored `P,Q` coefficient
polynomials from the [coefficient record](../n41_single_branch_joint_sat_20261011/coefficient_result.json)
into the same complete public-target circuit, then run the unpinned N41
query on this frozen point and resource cap. Promotion to an ordinary N131
query requires a source-bound complete circuit within the declared one-worker,
600-second, 4-GiB gate. The primary ECC2K-130 objective remains a fresh
ordinary N131 factor-base relation followed by measured relation yield,
useful rank, factor logs, a verified fresh target scalar, and paired
same-point one-target rho online accounting. This compiler is a
point-decomposition stage improvement; the full IC configuration still has
`candidate_id: null`.

Reproduce the non-Sage checks with `python3.12 -B search_order.py`,
`python3.12 -B audit_horner.py`, and `python3.12 -B verify_receipts.py` from
this directory. The frozen search was `python3.12 -B run.py freeze`, then
`control`, then `query`; its source hashes and outputs are retained here.
