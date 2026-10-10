# Q20261010120000: rational-orbit prefilter for fixed-output S3 scans

For `y²+xy=x³+1`, a nonzero field coordinate `x` has a rational point lift
exactly when `Tr(x+x⁻¹)=0`. Frobenius preserves this trace. The new source
enumerates one normal-basis necklace per sparse-x orbit, classifies that
representative, and expands only rational orbits before evaluating S3 against
one fixed outer output. This is a target-independent admissibility census;
its time, inversion count, and memory stay separate from the target-dependent
scan. An exact assertion matches the rational mask count to half the
established, fully enumerated usable factor-base point count for each curve.

This experiment uses the same N53 `EC1N53Ckb1hf77aab617904` W≤3 base
(`B=24,062`, `K=227`) and N83 `EC1N83Ckb1h876c2921cb64` W≤5 base
(`B=30,977,592`, `K=186,612`) as Q20261010111900. For each degree, the
control and ordinary target/output are byte-identical to that experiment's
input law. The two inversion windows are 4,096 and 16,384. All eight cells
scan their complete rational domains with one worker, a 120-second native
target-scan cap, a 180-second complete-process cap, and 512-MiB peak RSS cap.
The source, release binary, exact inputs, predecessor receipts, and resource
limits are hashed in `freeze.json` before measured runs. The source-bound
`prepare` stage then writes a compact orbit-representative file once per
degree, with its own operation, time, RSS, and content-hash receipt. Every
target scan verifies that hash and expands the same representatives in memory
before starting its target-dependent interval.

The decisive checks are the exact number of rational orbits and masks,
identical pair decisions and pair witnesses versus the matched complete
Q20261010111900 scans, and independent checked-Sage replay of each distinct
control relation. A rationality prefilter must never drop a valid leaf.
Report target-dependent S3 root calls, field multiplications, scan wall,
reusable census time/inversions, per-process expansion time, and RSS for each
cell. Host wall ratios are
exploratory until an isolated CPU receipt is available. The factor-base
configuration and S3 stage remain proposal-stage with `candidate_id: null`.

The N131 screen transfers only the measured N83 field-multiplication rate per
rational root to Q1414's exact W≤6 base and optimistic uniform-subgroup-query
minimum. It charges one full rational scan per query and no other phase to
state a conditional lower affordability figure. A second uniform-field-output
screen counts only rational right-pair inputs; this is a different input law.
Complete cold and one-target online work exponents remain unassigned until
natural relation yield, useful rank, final matrix work, target descent, and
scalar replay are measured in a common unit.
