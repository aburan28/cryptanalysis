# Q20261010103500: exact fixed-output right-pair decisions at N53 and N83

The native S3 root scan completed the full normal-basis weight domain for
both selected N53 and N83 outputs. It found one right pair for each
known-solution control and no pair for either first ordinary outer-root
output. Checked Sage independently verified that each distinct control
pair extends to four subgroup-usable factor-base points with a signed
sum equal to its frozen public target after cofactor projection. The
second batch window repeated the same decisions.

## Exact inputs and measurements

The [protocol](PROTOCOL.md), [freeze](freeze.json), [native build
receipt](build_receipt.json), eight [input manifests](inputs), and
[run receipts](runs) bind the source, binary, field bridge, curve,
factor base, target, output, caps, and input law before timing. The
read-only [native audit](audit.py) and [checked Sage audit](audit_sage.py)
replay the committed results without replacing their receipts. The
N53 curve is `EC1N53Ckb1hf77aab617904`, Q1301 W≤3 with B=24,062
usable points and K=227 signed-Frobenius columns. The N83 curve is
`EC1N83Ckb1h876c2921cb64`, Q1325 W≤5 with B=30,977,592 and
K=186,612. `Q20261010103500` remains a proposal ID because the
relation collector, final matrix solver, and one-target descent are
not specified as a complete candidate. Every measured cell has its
own hashed workload ID; control and ordinary targets are distinct.

| Degree | Input | Window | Full masks / S3 calls | Scan seconds | Field mul | Field inv | Right pairs | Checked relations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | control | 4,096 | 24,857 | 0.0082 | 260,577 | 8 | 1 | 1 |
| N53 | control | 16,384 | 24,857 | 0.0047 | 260,589 | 4 | 1 | 1 |
| N53 | ordinary | 4,096 | 24,857 | 0.0061 | 260,577 | 8 | 0 | 0 |
| N53 | ordinary | 16,384 | 24,857 | 0.0037 | 260,589 | 4 | 0 | 0 |
| N83 | control | 4,096 | 30,967,383 | 84.72 | 325,139,937 | 7,563 | 1 | 1 |
| N83 | control | 16,384 | 30,967,383 | 90.31 | 325,156,944 | 1,894 | 1 | 1 |
| N83 | ordinary | 4,096 | 30,967,383 | 69.35 | 325,139,937 | 7,563 | 0 | 0 |
| N83 | ordinary | 16,384 | 30,967,383 | 104.16 | 325,156,944 | 1,894 | 0 | 0 |

The scan timer excludes process startup, input loading, exact bridge
construction, S3 linear-map setup, and Sage replay. Those intervals
and peak RSS are retained in the [run receipts](runs). The native
scan checks S3 roots and weight only; [Python verification](verification.json)
recomputes S3 algebra and the bridge for recorded pairs, and the
[checked Sage replay](sage_replay.json) checks curve points, exact-base
membership, subgroup order, cofactor projection, and four-point sums.
The two control rows per degree represent one distinct relation
repeated under two windows. Zero pairs decide only the selected
ordinary output. Other outer roots, lifts, and anchors may yield
relations. The ordinary cells give two complete fixed-output decisions,
not a natural relation-yield rate.

The 16,384 window cuts inversions by about fourfold. It uses 17,007
more field multiplications at N83 and about 5 MiB more peak RSS than
the 4,096 window. The N83 wall-time ratios are exploratory because the
host lacks a CPU-isolation receipt. Neither window is a controlled
wall-time speedup result.

## Conditional N131 work screen

The [analysis receipt](analysis.json) uses the exact Q1413 N131 W≤6
raw mask count `D=6,559,349,863` and folded columns `K=25,036,774`.
Each unordered raw x pair has at most two S3 output roots. If each
scanned fixed output has a uniform marginal over `F_2^131`, the mean
right-pair hits per output are at most `D(D+1)/2^131 < 2^-65.78`.
If each pair supplies at most one novel row and all K rows come from
complete fixed-output scans, at least `2^90.28` such scans and
`2^122.89` S3 root calls are required for a 95% chance of full rank.
That is **61.89 bits above `2^61` in root-call units** for this
specified collector and output law, before base construction, outer
query generation, relation checks, matrix work, and target descent.

The N53/N83 fixed outputs do not establish a uniform law for ordinary
N131 outer roots. The screen therefore guides the next algorithm
choice and is separate from a complete N131 solve projection. The
full cold and one-target online `2^x` values remain null in the
[analysis receipt](analysis.json). A useful next experiment is a
collector that avoids a complete raw x scan for every outer root,
with natural output and novel-rank measurements on the exact N83 base.
