# N41 fill-limited XCNF WDSat gate

A capacity-sized WDSat build accepted the exact fill-limited N41 W4/m7
public-point formula and returned the full known assignment when every
projected variable was fixed. The independent XCNF replay passed. On the
same public-point formula without fixed variables, the one-worker search
reached its frozen 240-second wall limit with zero model output. The
[terminal audit](independent_terminal_audit.json) checks the frozen inputs,
binary and source hashes, run commands, raw output hashes, and both terminal
classifications.

| Gate | XCNF variables | CNF / XOR records | Solver wall | Sampled peak group RSS | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Full known-assignment control | 40,313 | 210,984 / 3,946 | 0.843 s | 505.7 MB | Complete model; all records pass |
| Unpinned ordinary public Q | 40,313 | 170,671 / 3,946 | 240.011 s | 519.5 MB | `CENSORED_TIME`; zero models |

Both gates used the N41 curve
`EC1N41Ckb1hf5a3eea408f4`, workload `2fa2f1e7c5fc`, one solver process,
and a 4 GiB combined-RSS guard. The source XCNF digest is
`5aee4bcb6534409bfb1ec00af23513151dbdca362cc611e530157ddeb1800275`.
It has 98,400 usable factor-base points before folding and 1,200 signed
Frobenius columns. The pinned gate added 40,313 unit clauses using the
previously checked model; it is a parser and exact-assignment control.
The ordinary solver received only the frozen public XCNF. The parent sent
SIGINT at the wall cap, and the solver returned code `-2`; the empty stdout
and stderr are preserved in `ordinary/`.

The timing interval is process launch through terminal state and includes
XCNF input loading. Formula construction, projection, and independent model
verification are outside this solver-stage clock. The checked Sage runtime
receipt was saved before both runs. These host timings are exploratory; both
this WDSat stage and the earlier CryptoMiniSat stage on the same XCNF were
censored at 240 seconds, so they provide no measured solver speed ratio.
Candidate and run IDs remain null because this method gate did not complete
an ordinary relation and full IC pipeline. The frozen [protocol](protocol.json),
[runner](run_gate.py), [pinned receipt](pinned/receipt.json), and
[ordinary receipt](ordinary/receipt.json) retain the capacities, hashes,
resource policy, and raw results.

The next method gate is an exact target-conditioned restriction on the leaf
or intermediate-point choices, checked first against the known N41 W4/m7
group witness and then against a fresh unpinned N41 public query. Its
promotion to the degree-131 challenge requires an independently checked
ordinary relation under the frozen N131 envelope; a smaller XCNF or a solver
family change alone does not pass that gate.
