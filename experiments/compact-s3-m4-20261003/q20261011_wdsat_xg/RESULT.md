# Q1471: WDSat XOR-Gauss on exact four-summand queries

The pinned WDSat `-x` Gaussian mode returned independently replayed SAT
models on both N53 and N83 full-lock controls. On the matched ordinary
queries, both runs started search and reached the 120-second CPU cap before
the $2^{20}$ left-branch cap. This resolves the option as a high-cost kernel
under the current source, formulas, and resource limits.

| Field degree | Full-lock control | Ordinary status | Last branch checkpoint | Next checkpoint absent | XG user CPU | Plain user CPU at $2^{20}$ branches |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 53 | `SAT_REPLAYED_XCNF` | `CPU_CAP_SEARCH_STARTED` | $2^{14}$ | $2^{15}$ | 118.343 s | 7.531 s |
| 83 | `SAT_REPLAYED_XCNF` | `CPU_CAP_SEARCH_STARTED` | $2^{12}$ | $2^{13}$ | 118.860 s | 10.026 s |

The four instrumented `conf[0]++` sites print and flush checkpoints at powers
of two. Thus the N53 XG run attempted at least $2^{14}$ and fewer than
$2^{15}$ counted left branches; N83 attempted at least $2^{12}$ and fewer
than $2^{13}$. Including initialization and propagation, the XG user-CPU
cost per reached branch was **more than 503×** the matched plain N53 value
and **more than 1,517×** the N83 value. These are lower bounds from censored
branch counts, not completed-solve ratios. The host lacks an isolation
receipt, so CPU and wall observations remain exploratory.

Q1471 reuses the exact Q1469 binary, selected priority array, curve, actual
factor base, folded columns, target, source XCNF, and width-four XCNF at each
degree. The only solver change is WDSat's `-x` command flag. Each run has the
same $2^{20}$ branch, 120/121-second CPU soft/hard, and 900-second wall
limits as the plain baseline. [The freeze](freeze.json) binds the binary and
input receipts; [the validator](validate.py) passed all four run receipts,
including model replay against the transformed and original XCNFs. The
stage remains a `PDP4sat` proposal with `candidate_id: null` and
`isogeny: "none"`.

The ordinary XG rows are CPU-censored, so natural relation yield and a
complete decomposition exponent remain unknown. [The analysis](analysis.json)
keeps the N131 full-solve exponent and gap to $2^{61}$ as `null`. The
separate conditional N131 full pair-index reference remains $2^{86.1847}$
counted pair-add attempts, 25.1847 bits above a $2^{61}$ pair-add
reference; no XG timing ratio changes that count.

The next solver experiment should spend its budget on finding a verified
ordinary four-point relation with the faster plain kernel. A frozen restart
or phase schedule on one previously unseen target can charge all failed
attempts to that target. Any SAT model must pass both XCNF replays, exact
factor-base membership, distinct-column checks, and the four-point group
sum before entering a useful-relation cost estimate.
