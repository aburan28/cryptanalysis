# Local result: vectorized Frobenius table construction

## Decision and boundary

**PASS_LOCAL for the frozen CPU cold complete-call gate.** This is a Sage
arithmetic result, not a complete index-calculus or discrete-log speedup.
Each cold call charges plan construction, one verified point-map call, and
cleanup. It includes the table and the native CPU execution path. The fixed
parent is PR #75; the only source change is `_make_table`. All measured
outputs match Sage's Frobenius isogeny, and all old/new lookup tables agree
bitwise. The Metal call includes its own shader/plan setup and is reported
separately.

| Run | Degree and workload | Cold complete-call result | Status |
| --- | --- | ---: | --- |
| `run-004` | Nine CPU cells, 12 balanced pairs each | Alternate degree-131 modulus: **0.905x** | Held under frozen >=0.98x per-cell gate |
| `run-005` primary | Six CPU cells, degrees 19/67/131/163 | **1.369x** geometric mean; min 1.167x | Passed |
| `run-005` confirmation | Three CPU cells, degrees 31/131 and alternate degree-131 modulus | **1.339x** geometric mean; min 1.171x | Passed |
| `run-006` Metal | Degree 19, 1,024 points, power 1 | 0.968x | Diagnostic regression; first-call variation dominates this small case |
| `run-006` Metal | Degree 67, 4,096 points, power 65 | 1.033x | Diagnostic |
| `run-006` Metal | Degree 131, 4,096 points, power 1 | 1.299x | Diagnostic |
| `run-006` Metal | Degree 131, 4,096 points, power 65 | 1.225x | Diagnostic |

`run-005` table-stage geometric means are 2.915x primary and 2.343x
confirmation. Warm calls are near parity; the gain comes from cold table
construction. Its 29,417,472 timed point outputs were verified. The held
pilot verified another 4,085,760 outputs, and the Metal diagnostic verified
1,597,440. The runs used fresh plans, balanced arm order, independent
confirmation inputs, exact source hashes, and no cloud spend. The
per-cell JSON files preserve every pair and the full timings.

Fresh-process degree-131/4,096-point/12-call peak RSS was **275,087,360 B**
for PR #75 and **274,808,832 B** for this patch, a reduction of 278,528 B.
The table equality suite covered degrees 1 through 256 at word boundaries,
five powers including negative one, and alternate irreducible moduli at
degrees 19 and 131. The installed hardware suite passed all six CPU/Metal
tests on the exact candidate source.

The degree-19 Metal cold result is a measured limitation, and the held CPU
pilot remains in the archive. No end-to-end IC or recovered-log claim is
made: the repository's degree-131 IC reference currently uses separate ONB
and SAT/F5 paths, and its full cost must be measured under the repository's
candidate/run naming and phase-accounting rules after integration.
