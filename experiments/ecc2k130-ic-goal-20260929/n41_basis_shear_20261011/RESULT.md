# Source-basis arithmetic and affine shear shrink the public N41 circuit

Combining the exact `T=S+Z` quartic substitution with source-basis-aware
field arithmetic reduces the complete N41 public-target formula to
**59,860 AND gates and 91,112 variables**. The prior basis-aware compiler
used 72,710 AND gates and 109,913 variables; the shared-Horner compiler
used 120,929 and 196,923. The combined circuit accepts the full archived
twelve-point relation, and an independent curve-law replay verifies the
public sum and all twelve distinct folded columns. Its unpinned one-worker
query is `BOUNDED_UNKNOWN` at the frozen 60-second solver cap.

The curve is `y²+xy=x³+1` over `GF(2)[t]/(t^41+t³+1)`, subgroup order
`549756390943`, public point `(1458168294740,1672312028033)`, actual
factor base `B=384`, and 26 folded columns. The [circuit](circuit.py)
retains six-bit source seed and eleven-diagonal product expressions in
their known field bases while sparse, materializing 41 coordinates only
when a product becomes dense. It also substitutes `S=T+Z` into the
single-branch quartic `A+wB=0`, reducing `A` from 60 to 40 monomials, and
uses Horner order `(T,Q,a,Z,P)`. The complete three-block circuit makes
141 field-multiplication calls: 102 sparse and 39 generic, with 36,921
recorded sparse bilinear pair products. The final formula has 186,281 CNF
clauses and 30,892 native-XOR rows.

The [frozen protocol](protocol.json) binds source and input hashes, one
CryptoMiniSat worker, a 120-second construction cap, a 60-second solver
flag with five-second parent margin, and 4 GiB combined RSS. The
[arithmetic replay](arith_replay.json) evaluates the actual basis-aware
`A,B,wB` wires in seven fixed cases against an independent direct
polynomial evaluator. The [full assignment](control_result.json) checks
every clause and XOR row. The [group replay](control_replay_result.json)
reconstructs the twelve raw source points and exact public sum without
using the Boolean circuit. The [terminal audit](terminal_audit.json)
rebuilds the exact formula, checks its SHA-256, log hashes, phase sum,
correctness controls, and size against both earlier compilers.

| Same N41 public input | Shared Horner | Basis-aware | Basis-aware shear |
| --- | ---: | ---: | ---: |
| AND gates | 120,929 | 72,710 | **59,860** |
| Variables | 196,923 | 109,913 | **91,112** |
| CNF clauses | 369,488 | 224,831 | **186,281** |
| Native-XOR rows | 75,634 | 36,843 | **30,892** |
| XCNF bytes | 9,304,582 | 7,468,648 | **6,434,955** |
| Unpinned query | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` |

The [query receipt](query_result.json) records 0.552 seconds of formula
construction, 0.037 seconds to write and hash it, and 65.096 seconds from
solver launch through parent stop. [Stdout](solver.stdout.gz) shows active
search through 434 restart rows and approximately 301,000 conflicts, with
no terminal SAT or UNSAT line; [stderr](solver.stderr.gz) is empty. These
wall intervals are exploratory on an unisolated host. The exact operation
and formula-size counts are deterministic.

The source-basis advantage weakens at challenge width. A separately frozen
[N131 W15 block](../n131_basis_shear_block_20261011/RESULT.md) verified the
archived four-atom witness but emitted 216,341 AND gates for one arithmetic
block, with 45 generic multiplications and only two sparse ones. That
component alone exceeds the 77,021 AND gates in the earlier complete N131
direct six-pair control. The next algorithmic step needs target-conditioned
family rejection or a different decomposition representation before a
full N131 search; a smaller N41 circuit is not the one-target result.
This component retains `candidate_id: null`.

Reproduce the non-Sage checks with `python3.12 -B arith_replay.py`,
`python3.12 -B control_replay.py`, and `python3.12 -B verify.py` from this
directory. The public query used the `freeze`, `control`, then `query`
modes of `run.py`.
