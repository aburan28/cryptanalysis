# Q1451: specialize phi5 to one public-target preimage

Q1451 fixes raw target preimage index 0 from each archived ordinary workload
as a field constant before constructing the four-leaf phi5 circuit. This
removes target-selector products while retaining Q1450's CryptoMiniSat 5
binary, native XOR input, bounded Gaussian settings, model blocking, curves,
factor bases, public targets, and workload IDs. The [frozen protocol](protocol.json)
records the exact selected raw x coordinates, hashes, and solver limits.
The stage is `PDP4phi5` with `candidate_id: null` and `isogeny: "none"`.

The [fully pinned controls](controls.json) replay exact four-point group
relations at N53 and N83. The N53 control uses the archived ordinary target's
known witness at preimage index 201; the N83 control uses a planted target.
These controls prove circuit correctness for their pinned leaves. Neither
estimates ordinary relation yield. The ordinary query always uses preimage
index 0, which is not known to contain a relation for either workload.

| Ordinary field | Target preimages screened / total | Q1450 → Q1451 AND gates | Q1450 → Q1451 CNF clauses | Active Gaussian matrices | Solver process | Target-dependent stage | Peak child RSS | Verified relations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | 1 / 428 | 58,936 → 47,700 | 201,649 → 145,227 | 5 | 65.016 s, external timeout | 66.001 s | 108,445,696 bytes | 0 |
| N83 | 1 / 4 | 144,586 → 117,030 | 438,667 → 355,751 | 5 | 65.041 s, external timeout | 68.361 s | 116,441,088 bytes | 0 |

The target-dependent stage interval includes circuit construction,
serialization, the solver process, model checks, and blocking overhead;
compressed archive creation is timed separately. The solver's nominal
60-second limit did not terminate it on this host; the remaining-budget-plus-
five-second external safeguard stopped both processes. The last partial
restart lines round conflict counts to 81K for N53 and 26K for N83. They are
not final operation counts. Wall-time ratios to Q1450 are exploratory because
the host was not isolated and Q1451 searches only one of Q1450's preimages.

The [archive audit](verification.json) rebuilds both XCNFs and checks frozen
source hashes, the selected target preimages, solver settings, raw output
hashes, and all returned models. The protocol recheck covers input hashes.
Both ordinary cells are censored.
There is no successful ordinary decomposition, measured natural relation
yield, novel relation-matrix rank, cost per useful row, successful N53-to-N83
growth rate, or complete N131 `2^x`. The challenge gate remains closed.

The next controlled screen should specialize the known-satisfiable N53
ordinary target to its archived preimage index 201 **without pinning the four
leaves**. That tests whether constant-target algebra helps find a relation
when one is known to exist in the selected slice. If it still caps, the next
solver needs a solution-preserving field-level propagation or elimination
step that couples several sparse leaves before SAT branching; another
preimage choice or clause-order variation does not establish that.
