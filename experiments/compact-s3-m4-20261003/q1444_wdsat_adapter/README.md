# Q1444: sound WDSat adapter diagnostic for the joint-witness gate

This is a bounded comparison of a dedicated XOR-aware SAT solver with the
archived compact chained-`S3` formulas. It is a **stage diagnostic**, not a
new target-conditioned search theorem or complete index-calculus candidate.
The formulas fix one raw anchor, leave the other three leaves free, and use
two factored `S3` links. No `S5` is expanded. The two control formulas use
an archived witness anchor and pin the adjusted-target choice; the two
ordinary formulas use independent fixed anchors and unpinned choices. The
N53 ordinary public target is known representable on the exact base, but
its independent anchor is not known to occur in a relation. The N83
ordinary target is not the planted control target.

The upstream WDSat CNF implementation builds implications only for clauses
of size 1 through 4. Feeding an archived formula directly can therefore
produce an apparent assignment that violates the unhandled longer clauses.
The adapter replaces every longer OR clause with shared-prefix binary OR
gates, each defined by all three clauses of its equivalence. It leaves XOR
rows unchanged. The [independent audit](verify_factor_xcnf.py) reconstructs
each gate expression from the converted clauses and checks every source
clause, every XOR row, header, variable, and clause count. It also extends
the archived known-witness CryptoMiniSat models through the gates and checks
that both original and converted formulas are satisfied.

The [frozen protocol](protocol.json) pins the exact source XCNFs, converted
hashes, curve IDs, actual `B`, folded `K`, factor-base set digests, public
targets, workload IDs, upstream WDSat commit, local patch, built binaries,
accepted Sage runtime, run order, and 60-second cap per cell. WDSat is built
from its pinned clean commit with the [local patch](wdsat_adapter.patch):
the patch allocates its large undo lists lazily, checks the unit-propagation
return value, and logs a branch counter checkpoint every 65,536 increments.
The adapter checks any returned model
against both Boolean formulas. It then uses the repository's checked Sage
launcher to replay the four-point relation against the public subgroup point
and distinct folded columns. Raw failures and timeouts remain receipts.

N53 uses `EC1N53Ckb1hf77aab617904`, W≤4, actual B=324,042 and folded
K=3,057. N83 uses `EC1N83Ckb1h876c2921cb64`, W≤6, actual B=408,131,750
and folded K=2,458,625. The exact set digests are in the protocol and
Q1438's base receipts. This remains proposal `Q1444`, with
`candidate_id: null` and `isogeny: "none"`. Its solver walls are exploratory
on an unisolated host. A known-witness result is a correctness control;
neither it nor a censored ordinary run estimates natural relation yield.

## Reproduction

Use the pinned upstream WDSat checkout at the protocol's commit. The
converter and build scripts refuse to overwrite existing output. Before
measured cells, save the accepted runtime information through the repository
launcher and freeze the protocol:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1444_wdsat_adapter/sage_runtime_info.json
python3 experiments/compact-s3-m4-20261003/q1444_wdsat_adapter/freeze_protocol.py --scratch /path/to/frozen-builds --check
```

Run each cell separately with `run_cell.py --cell CELL --binary BINARY`,
using the degree-specific built binary. The runner rebuilds and audits the
factored formula from its archived source. It refuses to overwrite a run.
All returned models are independently checked; a valid Boolean model is
only a verified relation after the Sage curve replay. The final N131
complete-work exponent, natural yield, cost per useful row, and challenge
gate remain unknown until a joint target-conditioned method succeeds on
ordinary N53/N83 queries and all later pipeline stages are charged.

## Frozen result

The [post-run archive audit](verification.json) rechecks all four frozen
inputs and every receipt, including the source and converted XCNF hashes,
gate equivalences, XOR rows, binary identities, raw solver output, and
branch-counter checkpoints. Each cell reached its 60-second external cap
without a Boolean model. The branch count is the last checkpoint and is a
**lower bound** on this WDSat build's search-node counter, not a field-operation
count. Peak RSS is the child-process high-water value on this macOS host.

| Cell | Input role | Result | Branch-counter lower bound | Peak RSS |
| --- | --- | --- | ---: | ---: |
| N53 choice pinned | known satisfiable control | timeout; 0 relations | 5,505,024 | 106,020,864 bytes |
| N53 ordinary | independent anchor | timeout; 0 relations | 917,504 | 95,371,264 bytes |
| N83 choice pinned | known satisfiable control | timeout; 0 relations | 786,432 | 374,587,392 bytes |
| N83 ordinary | independent anchor | timeout; 0 relations | 524,288 | 327,712,768 bytes |

The controls were known satisfiable before solving because archived,
independently verified witnesses satisfy their original and converted
formulas. Their timeouts are evidence about this bounded solver run, not
mathematical evidence of nonexistence. The ordinary cells likewise provide
no natural relation yield or successful-solve cost. A longer cap or another
SAT encoding does not address the missing target-conditioned search rule.
The archived pair-table comparator uses the older W≤3/W≤5 bases, while these
cells use Q1438's W≤4/W≤6 bases, so they do not support a controlled solver
speed ratio on matched factor-base inputs.
The next method must constrain both sparse pairs with the public target
before completing either pair, then recover an ordinary relation and measure
useful rank on a frozen target panel. The complete N131 `2^x` remains null
and the challenge gate stays closed.
