# Q1420 wide-Gaussian native-XOR gate

The archived CryptoMiniSat 5.14.7 transcripts reject large native-XOR
components under its default 2,000-row/1,000-column matrix limits. The
fixed-witness full x-release source transcript rejected components as large
as 5,809 × 8,457; the ordinary source Q0 transcript rejected a 17,665 ×
27,342 component. This experiment changes only Gaussian matrix admission and
automatic disabling on the **same six archived XCNFs**. A rejected component
is evidence of a solver configuration gate, not evidence that admitting it
improves decomposition search.

`source.json` pins the parent branch head, the source and oriented degree-263
descendant curves' W24 archives, the six-distinct finite witness, all four
width-131 unit deltas, both ordinary Q0 XCNFs and named-input maps, and the
CryptoMiniSat binary. The four fixed cells are x0/x5 on each curve; the two
ordinary cells use workload `eee7f6ee5f6b`'s first public target. Both bases
have 16,772,828 actual usable points before sign folding. These are Q1420
solver-stage gates (`candidate_id: null`), not complete IC candidates.

The sole intervention is
`--maxmatrixrows=20000 --maxmatrixcols=30000 --maxnummatrices=5
--autodisablegauss=0`; all cells use one thread and print the model. Fixed
cells retain the 20,000-conflict, 30-second internal, 40-second external
wall guards of the x-release ladder. Ordinary Q0 retains the parent
120-second internal, 150-second external wall guards. Each cell gets exactly
one attempt with sampled 4-GiB RSS protection. Solver wall and CPU times are
exploratory because the host has no verified CPU-isolation receipt. Record
matrix acceptance/rejection, search progress, exit status, caps, memory,
and every stdout/stderr byte, including failures and pre-search caps.

Commit this protocol, `source.json`, `experiment.py`, and `audit.py` before
freezing inputs. Run `python3 -B .../experiment.py freeze`, audit the six
reconstructed SHA-256s, and commit `runs/R1/cells.json` before launching a
solver. The frozen panel is write-once. Run
`python3 -B .../experiment.py all` under an environment that permits the
`ps` memory sampler; a failed preflight is preserved separately and does not
count as a solver attempt. Then run `python3 -B .../audit.py --write`.

The independent auditor rebuilds every fixed cell from its parent base XCNF
and semantically recomputed units; it decompresses both ordinary Q0 archives.
For SAT it verifies each ordinary clause and native XOR, decodes the six
leaves and projective S3 states, and replays the signed group sum against the
exact raw lift and public query. A solver-reported ordinary UNSAT remains a
reported status without an independently checked proof. A cap before search
is identified separately from search that reached its budget.

The decision gate is input- and status-based. If larger matrices are admitted
and a fixed control verifies SAT at width 131, inspect whether the ordinary
Q0 cells yield verified distinct decompositions; if so, collect held-out
ordinary queries and charge all failed attempts to measure relation yield and
novel rank. If large matrices are admitted but fixed controls remain capped,
prioritize selector-derived field-linear leaf elimination and partial
assignment policies. If matrices are rejected or initialization exceeds a
guard, use sparse-XOR elimination or circuit rewriting instead of simply
raising matrix limits further. No wall-time ratio from this unisolated host
is promoted as a speedup.
