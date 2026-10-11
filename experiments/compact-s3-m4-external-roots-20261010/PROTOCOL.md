# Q20261010131600: exact S3 roots for free pair intermediates

The experiment reuses Q1419's exact N53 and N83 balanced-S3 `free_mids`
controls. Their four sparse leaf x coordinates and public target selector
are fixed; the two pair-intermediate coordinates remain for SAT to choose.
For each leaf pair, solve its S3 quadratic in the field and constrain the
intermediate to one of its roots with a selector. Preserve every original
CNF and native XOR row. This adds two variables and `4n` binary CNF clauses,
with no S5 expansion and no witness midpoint supplied to the solver.

N53 is `EC1N53Ckb1hf77aab617904`, Q1301 W<=3, actual `B=24062`,
`K=227`. N83 is `EC1N83Ckb1h876c2921cb64`, Q1325 W<=5, actual
`B=30977592`, `K=186612`. The freeze records each enumerated-set digest,
target point, source and formula hashes, solver binary, limits, and stage
operation counts. This is proposal `Q20261010131600` with `candidate_id`
and `run_id` null and `isogeny: "none"` (`ISO0`).

Run CryptoMiniSat with one thread, seed zero, a 1,000,000-conflict internal
limit, and a 60-second external wall cap. Record all statuses, stdout,
stderr, conflict count when reported, child RSS, wall time, and model replay.
The auditor checks exact root constraints, the serialized XCNF, and full
group-law relation. The host lacks an isolation receipt, so wall times are
exploratory. These fixed-leaf controls establish the root-implication gate;
an ordinary-query solver must generate leaf pairs and charge failed search.
