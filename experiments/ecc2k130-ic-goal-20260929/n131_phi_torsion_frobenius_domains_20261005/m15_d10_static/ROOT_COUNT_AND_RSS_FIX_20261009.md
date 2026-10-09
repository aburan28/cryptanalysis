# d10/m15 single-target producer corrections

The frozen N131 d10/m15 candidate now reaches its first ordinary
precomputation SAT query with the declared 4 GiB combined-RSS guard active.
The [v3 candidate manifest](d10_m15_candidate_manifest_v3.json) and
[run protocol](d10_m15_single_target_protocol_v3.json) bind the corrected
runner as a new candidate ID,
`IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0h91f3d222e01b`.
The 15-summand algebraic circuit, exact factor base, target workload,
solver flags, and per-query resource envelope retain their frozen values.

The [v1 run](single_target_runs/IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0hcaa3ab9d3890W3c1992b7c92fR1/failure.json)
ended `PRODUCER_FAILURE` before launching CryptoMiniSat. Its formula
guard compared `len(roots)` with the formula receipt's `roots: 524`.
The receipt counted four endpoint fields × 131 coordinate bits, while
the returned `roots` list contains 14 summation links × 131 bits =
1,834 chain-equation roots. The
[independent two-target diagnostic](diagnose_target_formula_counts_20261009.json)
reconstructed both the published Q and the first generated precomputation
query: each has 282,598 variables, 225,092 clauses, 208,783 native XOR
rows, 1,834 chain roots, and four 131-bit endpoint fields. The corrected
guard checks both counts under their own meanings. The original v1 runner
is archived as [run_d10_m15_single_target_v1.py](run_d10_m15_single_target_v1.py).

The [v2 run](single_target_runs/IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0h6d45eb00aeffW3c1992b7c92fR1/failure.json)
reached solver launch but ended `PRODUCER_FAILURE` when the parent RSS
monitor referred to `CryptoMiniSatCli`; the imported class is
`CryptoMinisatCli`. Its exception handler stopped and drained the child.
The v2 runner is archived as
[run_d10_m15_single_target_v2.py](run_d10_m15_single_target_v2.py).
The v3 [small satisfiable control](v3_solver_monitor_control/receipt.json)
exercises the actual CryptoMiniSat process, combined RSS sampling, stdout
drain, and returned assignment. The
[root-accounting regression](test_d10_v2_root_accounting.py) passes for
both independently reconstructed targets, and the v3 single-target
preflight is `READY`.

The v3 R1 directory records the checked Sage runtime and the exact first
precomputation XCNF. Its CryptoMiniSat process was observed live with
the checked-Sage runner as parent, after the parent passed its RSS monitor
control. Rank, relation yield, factor logs, and online recovery remain
pending terminal receipts. Preserve the v1 and v2 failures as distinct
run rows; the v3 process must be polled by its live handle or recorded PID
before interpreting the query outcome.
