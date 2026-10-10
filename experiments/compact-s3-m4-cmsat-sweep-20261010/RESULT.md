# Bounded parameter sweep on N53 and N83 chained-S3 formulas

A frozen six-setting CryptoMiniSat sweep executed **18 exact N53/N83
balanced-S3 cells**, followed by two separately frozen N83 Gaussian-width
cells. Solver search began in all 20 cells, and the audited stdout/stderr
archive records a 30-second external wall cap for every cell. All 20
statuses are `BOUNDED_UNKNOWN`; each final conflict count is unavailable
because the solver was killed at the wall cap. The N83 25,000-column
follow-up successfully activated **three Gaussian matrices** on both the
ordinary and known-satisfiable formulas. It establishes the setting needed
to exercise that branch of the solver at N83; the present host condition
does not support a performance ranking among settings.

This is the four-summand SAT point-decomposition proposal
`Q20261010125300`, with
`candidate_id: null`, `run_id: null`, and `isogeny: "none"` (`ISO0`). The
[freeze](freeze.json) fixes all three raw formula hashes, solver binary,
source files, flags, cell order, exact bases, and limits. The [corrected
audit](audit.json) checks all 18 original receipts and confirms each solver
entered search with empty stderr. The [target-bound analysis](analysis.json)
binds every formula to its archived public point and workload ID. The
[Gaussian-width freeze](gauss25000.freeze.json) and
[audit](gauss25000.audit.json) bind the two additional N83 cells.

| Input | Exact curve and base | Original six settings | Exploratory wall interval | Peak child RSS interval |
| --- | --- | --- | ---: | ---: |
| N53 Q1410 ordinary target | `EC1N53Ckb1hf77aab617904`, Q1301 W≤3, `B=24062`, `K=227` | 6 `BOUNDED_UNKNOWN` | 30.017–30.114 s | 121.1–141.6 MiB |
| N83 Q1408 ordinary target | `EC1N83Ckb1h876c2921cb64`, Q1325 W≤5, `B=30977592`, `K=186612` | 6 `BOUNDED_UNKNOWN` | 30.015–30.110 s | 64.7–223.6 MiB |
| N83 Q1408 satisfiable control | same curve and base | 6 `BOUNDED_UNKNOWN` | 30.020–30.038 s | 80.5–261.8 MiB |

Each original cell used one solver thread, seed 0, a 200,000-conflict
internal limit, and a 30-second external wall cap. The settings were
default, 10,000-column Gaussian reasoning, VSIDS branching, VMTF
branching, geometric restarts, and Luby restarts. The original
Gaussian setting activated three matrices at N53. Its 10,000-column
limit rejected N83's 20,916-column matrix, so it did not test Gaussian
reasoning at N83. The separate 25,000-column follow-up did activate three
matrices on both N83 inputs; both still ended `BOUNDED_UNKNOWN` after
30.189 and 30.093 exploratory seconds, respectively. Its formula,
target, base, solver, thread count, and caps match the first cohort.

The [post-run host observation](host_observation.json) recorded a load
average of 127.74 with 6 logged-in users. Earlier observations during the
run ranged from about 100 to 118. This host has no isolation receipt. All
wall intervals include solver startup and formula loading; decompression
is recorded separately in each receipt. The cells cannot establish a CPU
speedup or natural relation-yield rate. The ordinary relation count observed
under these caps is zero; the known-satisfiable control was also censored.
No setting is promoted, and the [analysis](analysis.json) leaves the
complete N131 solve work exponent `null`.

The auditor frozen before the run had a chained-equality comparison error
in its base-digest check. Its bytes remain in [audit.py](audit.py), as
bound by the first freeze. [audit_v2.py](audit_v2.py) corrects that check,
verifies the preserved first auditor's hash, and generated the passing
audit without altering a producer, input, or solver receipt.

## Next solver gate

Run the N83 25,000-column setting and the matched default with a
conflict-bound stop on an isolated or demonstrably quieter host, retaining
complete conflict statistics and a checked satisfiable control. In
parallel, couple the exact field S3 root oracle to free-leaf search as an
external propagator. The first correctness gate is Q1419's N53/N83
`free_mids` controls, followed by an unpinned ordinary N53 relation and an
ordinary N83 relation on the exact Q1325 base. Charge every failed probe
and independently replay any N83 relation before fitting N131 solver work.
