# Q1450: bounded Gaussian matrices in the compact phi5 solver

Q1450 changes one solver setting package from Q1449 while retaining its
exact ordinary N53/N83 XCNFs, curves, factor bases, public targets,
workload IDs, single-thread CryptoMiniSat 5 binary, model replay, and
invalid-model blocking rule. It admits at most eight Gaussian matrices
with at most 512 rows and 8,192 columns each and disables automatic
Gaussian shutdown. The stage remains `PDP4phi5`; its exact settings are
in the [frozen protocol](protocol.json). It is a Q proposal with
`candidate_id: null`, `isogeny: "none"`, and no complete IC pipeline.

The [partial controls](controls.json) pin two known witness leaves and
the target preimage selector. They report eight N53 and six N83 active
matrices, proving that the new limits admit field-product components.
Both controls ended indeterminate after their five-second internal
limit; they are activation checks, not newly recovered relations.
Q1449's fully pinned N53/N83 controls independently replay verified
relations for the same mathematical circuit and CryptoMiniSat binary.
The first Q1450 control runner failed on an uncaught outer timeout
before saving a receipt; the [failed preflight](failed_control_preflight.json)
is retained. The corrected runner and controls were frozen before any
ordinary Q1450 run.

| Ordinary field | Active Gaussian matrices | Formula build | Solver process | Target-dependent stage | Peak child RSS | Verified relations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | 6 | 1.102 s | 65.020 s, external timeout | 66.272 s | 135,938,048 bytes | 0 |
| N83 | 5 | 1.644 s | 65.012 s, external timeout | 67.278 s | 228,638,720 bytes | 0 |

The target-dependent stage interval includes formula construction,
serialization, the solver process, model checks, and blocking overhead;
compressed archive creation is timed separately. The solver's nominal
60-second setting did not terminate it on this contended host, so the
runner's remaining-budget-plus-five-second external safeguard stopped
both processes. The raw logs show some Gaussian propagation and
conflicts, but no SAT model. Last restart lines report about `248K`
N53 and `134K` N83 conflicts; these are rounded partial progress
values, not exact final operation counts. CPU wall comparisons to Q1449
are exploratory without host-isolation evidence.

The [archive audit](verification.json) regenerates the XCNFs, checks
matrix settings and activation, verifies the compressed inputs and raw
outputs, and replays every returned model. Both ordinary cells are
censored. There is no measured natural relation yield, novel matrix
rank, cost per useful row, successful N53-to-N83 solve growth, or
complete N131 `2^x`. The challenge gate remains closed.

The next solver must use a target-dependent field-level condition that
couples several leaves before generic Boolean branching. A bounded
algebraic elimination or propagation rule should be proved solution
preserving, checked on small fields and the archived witnesses, and
then tested on the known-satisfiable unpinned N53 ordinary target before
any N83 work projection.
