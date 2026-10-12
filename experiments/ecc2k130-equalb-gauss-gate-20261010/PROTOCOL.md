# Equal-B ordinary-query Gaussian-matrix gate

This experiment tests whether admitting the larger native-XOR components into
CryptoMiniSat's Gaussian elimination materially changes search on the exact
six-summand, four-lift ordinary query zero. It uses the archived normal4
four-threshold counter and W24 balanced-S3 formulas. Both have exactly
11,743,888 usable factor-base points on `EC1N131Ckb1h136f03e58c98` and the
same four checked target lifts. `CONFIG.json` pins the parent commit, input
archive and raw hashes, solver binary hash, commands, order, and caps.

The existing default-setting transcripts did enter search. Their first
`GJ matrices: 0` message is a preprocessing line; later initialization used
five small matrices. Larger components, including about 8,100 rows by
13,000 columns, were rejected at the default 2,000-row limit. The precise
question here is whether a 9,000-row, 14,000-column limit admits those
components within 4 GiB and changes bounded search progress. The two
settings on each formula are the paired comparison; formula-to-formula
comparisons are structural diagnostics because their encodings differ.

Run `python3 experiments/ecc2k130-equalb-gauss-gate-20261010/run_gate.py
--check` before `--run`. The runner verifies both compressed and raw formula
hashes, source receipts, all four lifts, the installed solver hash and version,
then starts four one-thread attempts in the frozen order. Each attempt has a
60-second solver limit, 70-second external wall guard, and 4 GiB RSS guard.
Solver time begins after archive decompression; setup and input verification
are recorded separately. Preserve stdout, stderr, exit code, last live restart
row, matrix initialization lines, wall time, and peak RSS for every cell.

Promotion requires a verified ordinary relation and independent point replay.
A SAT answer without that replay is `SAT_UNVERIFIED`; a capped or solver-unknown
cell is `BOUNDED_UNKNOWN`. This diagnostic cannot establish natural relation
yield, novel matrix rank, target descent, or an IC versus rho speedup. Host
isolation is unverified, so CPU timing ratios stay exploratory. If the large
matrix setting uses at least one previously excluded component and shows
materially better progress without breaching the cap, the next gate should
use multiple preregistered ordinary queries and independently verify every
candidate relation. Otherwise prioritize changing the PDP encoding or
decomposition geometry over repeating the same solver settings.
