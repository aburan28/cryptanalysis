# Wide Gaussian admission reaches Q1420 search on six archived XCNFs

Raising CryptoMiniSat 5.14.7's Gaussian matrix limits admitted the large
native-XOR components on all four fixed six-leaf controls and both ordinary
Q0 circuits. Every cell entered search and ended `BOUNDED_UNKNOWN` at its
precommitted wall guard. The source ordinary circuit admitted a 17,665 ×
27,342 matrix, and the degree-263 descendant admitted a 17,754 × 27,561
matrix; the default transcripts rejected both on the row limit. This
establishes **matrix admission and active search**, while the capped Q0
attempts contribute zero verified relation rows at this gate.

The [protocol](PROTOCOL.md), [source pins](source.json), runner, and original
auditor were committed as `24ac06a11` before freezing inputs. The six complete
input SHA-256s were independently reconstructed and committed as `5bb6da459`
before solver launch. The auditor's transcript parser was corrected after
launch to read CryptoMiniSat's split-line matrix-0 dimensions; this changed
only evidence extraction. The [final audit](runs/R1/audit.json) verifies all
archived input bytes, solver flags, stdout/stderr hashes, terminal states,
guards, and search progress. No SAT model was emitted, so group-model replay
was not invoked in this panel. The [runtime receipt](runs/R1/runtime-info.json)
records the local OS/architecture, visible CPU count, binary hash, launch
command, and timing boundary.

The four fixed cells release all 131 bits of x0 or x5 while keeping the
verified six-distinct W24 witness's other coordinates and S3 intermediates
fixed. The ordinary cells are the first public Q1420 query of workload
`eee7f6ee5f6b` with six free selectors. The source curve is
`EC1N131Ckb1h136f03e58c98`; the oriented degree-263 descendant is
`EC1N131Cbinh833014327b07` along `IW1E263d1hadee4e69fa3d`. Each W24
factor base has `B=16,772,828` distinct subgroup-usable points before sign
folding. Q1420 remains a design proposal with `candidate_id: null`.

| Archived cell | Largest admitted XOR matrix | Restart rows | Wide status / guard | Wall s | CPU s | Peak sampled RSS MB | Default status |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| Source fixed x0 | 5,809 × 8,457 | 17 | `BOUNDED_UNKNOWN` / 40 s wall | 40.218 | 8.096 | 304.4 | `BOUNDED_UNKNOWN` / 20,000 conflicts |
| Descendant fixed x0 | 5,656 × 8,212 | 35 | `BOUNDED_UNKNOWN` / 40 s wall | 40.228 | 6.560 | 311.7 | `BOUNDED_UNKNOWN` / 20,000 conflicts |
| Source fixed x5 | 5,770 × 8,351 | 13 | `BOUNDED_UNKNOWN` / 40 s wall | 40.261 | 7.007 | 296.7 | `BOUNDED_UNKNOWN` / 20,000 conflicts |
| Descendant fixed x5 | 5,922 × 8,508 | 17 | `BOUNDED_UNKNOWN` / 40 s wall | 40.148 | 8.694 | 318.3 | `BOUNDED_UNKNOWN` / 20,000 conflicts |
| Source ordinary Q0 | 17,665 × 27,342 | 14 | `BOUNDED_UNKNOWN` / 150 s wall | 150.105 | 25.821 | 1,163.0 | `BOUNDED_UNKNOWN` / 120 s internal |
| Descendant ordinary Q0 | 17,754 × 27,561 | 25 | `BOUNDED_UNKNOWN` / 150 s wall | 150.153 | 30.242 | 1,156.9 | `BOUNDED_UNKNOWN` / 120 s internal |

The fixed cells used one thread, a 20,000-conflict limit, a 30-second
internal time limit, a 40-second external wall guard, and a sampled 4-GiB
RSS guard. Ordinary cells used one thread, 120/150-second internal/external
wall guards, and the same RSS guard. All six used
`--maxmatrixrows=20000 --maxmatrixcols=30000 --maxnummatrices=5
--autodisablegauss=0`. Each accepted five matrices and printed restart rows.
No RSS guard fired. There was one attempt per cell, no verified
decomposition, and therefore no relation-matrix row or rank increment to
measure. The host has no isolation receipt: wall/CPU numbers are exploratory
resource observations, and the default/wide timings are not promoted as a
speed comparison. In particular, the wide fixed cells consumed only
6.56–8.69 seconds of process CPU during roughly 40 seconds of wall time.

The next implementation gate is a selector-derived field-linear leaf cut:
for each W24 selector mask `s`, compute `w(s)` and `u(s)=halftrace(w(s))`,
then propagate `z=w(s)^(-1)` and `x=alpha+alpha/u(s)` for valid nonzero
selectors before solving the global S3 equations. First reproduce the four
full-x fixed controls without supplying archived x values; then apply the
same cut to held-out ordinary Q1420 queries and charge every selector branch,
failure, model check, verified relation, and novel-rank increment. Wide
Gaussian matrices can be retained as a measured solver option, but their
admission alone is not an end-to-end advantage. A quieter or isolated host
is required to compare CPU costs at matched search budgets.

Reproduce the archive-only audit with:

```sh
python3 -B experiments/ecc2k130-263-wide-gauss-20261010/audit.py --write
```
