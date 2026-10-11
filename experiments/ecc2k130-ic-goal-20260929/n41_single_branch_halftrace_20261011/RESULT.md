# Half-trace replaces each Artin--Schreier vector by one branch bit

The odd-degree identity `HT(T)²+HT(T)=T+Tr(T)` gives an exact Boolean
encoding of each four-atom branch witness as `w=HT(S+Z)+epsilon`, with
`epsilon` one bit and `Tr(S+Z)=0` enforced. On the same public N41 target,
the complete formula uses **159,783 variables and 61,549 native-XOR rows**,
versus 159,966 and 61,612 for the affine-shear version with three free
41-bit branch vectors. The known twelve-point public relation satisfies
every constraint. The frozen unpinned search is `BOUNDED_UNKNOWN` at the
same one-worker, 60-second solver cap.

The exact field is `GF(2)[t]/(t^41+t³+1)` on `y²+xy=x³+1`, subgroup order
`549756390943`; the public point is `(1458168294740,1672312028033)`,
the actual base has `B=384` points and 26 folded columns. The
[circuit](circuit.py) computes a 41-bit half-trace by a fixed linear map
from `S+Z`, checks its one-bit absolute trace, and XORs `epsilon` into its
constant coefficient. Thus both Artin--Schreier roots remain available.
The [identity audit](halftrace_audit.json) checks zero, one, every basis
element, and 100 fixed-seed uniform field elements, plus the three branch
choices of the archived public relation (`1,0,0`). The
[arithmetic replay](audit_result.json) checks the emitted sheared quartic
against direct `A,B` evaluation on sixteen field inputs. The
[complete assignment](control_result.json) checks all 300,563 clauses and
61,549 native-XOR rows.

The [frozen protocol](protocol.json) binds the same target, source,
one-worker solver flags, 60-second solver cap, five-second parent margin,
120-second construction cap, and 4-GiB RSS as the
[affine-shear query](../n41_single_branch_shear_20261011/RESULT.md).
The [query receipt](query_result.json) records 65.024 seconds from solver
launch to parent stop, 177 restart rows in [stdout](solver.stdout.gz),
and empty [stderr](solver.stderr.gz); it has no terminal solver line.
The [cross-variant audit](../n41_single_branch_shear_20261011/variant_audit.json)
checks its source binding, logs, phase sum, and exact formula counts.
Wall intervals are exploratory on an unisolated host. The active N131
relation search still requires target-conditioned rejection before
expanding source families; `candidate_id` remains `null`.

Reproduce with `python3.12 -B audit_halftrace.py`,
`python3.12 -B audit_horner.py`, then the frozen `run.py` modes in order.
