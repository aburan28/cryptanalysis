# Q1454: one-million-conflict phi5 search on the known-satisfiable N53 slice

Q1454 reruns Q1452's **byte-identical** ordinary N53 XCNF on the same
public target, raw preimage index 201, exact W≤4 base, curve
`EC1N53Ckb1hf77aab617904`, actual usable `B=324,042`, folded
`K=3,057`, CryptoMiniSat binary, and Gaussian settings. The selected
slice contains an archived, independently group-verified four-point
relation, but its four leaves are unpinned in this run. The
[frozen protocol](protocol.json) extends the global wall allowance to
480 seconds, retains the one-million-conflict cap per attempt, and asks
for detailed final solver statistics. This remains a `PDP4phi5` stage
proposal with `candidate_id: null` and `isogeny: "none"`.

The solver exited on its conflict cap after one attempt. Its native
output says `s INDETERMINATE` and contains final statistics. The frozen
runner classified exit code 15 as `solver_error` because that code was
not in its status map. The [supplementary cap audit](cap_interpretation.json)
retains that raw receipt and establishes the more specific outcome
`conflict_cap_indeterminate_no_model` from the native status line,
command, and exact counters. The [archive audit](verification.json)
checks the exact XCNF, raw logs, settings, and all returned models.

| N53 stage measurement | Value |
| --- | ---: |
| Exact final SAT conflicts | 1,000,002 (`log₂ = 19.9316`) |
| Exact final SAT decisions | 1,367,589 |
| Final propagations | `1021M`, rounded solver display |
| Active Gaussian matrices | 5 |
| Solver process wall time | 136.583 s, exploratory |
| Child user + system CPU | 121.054 s + 1.989 s |
| Target-dependent stage wall time | 136.863 s, exploratory |
| Peak child RSS | 157,089,792 bytes |
| Returned models / verified relations | 0 / 0 |

This is a censored search prefix on a known-satisfiable ordinary target
slice. It shows that this deterministic solver configuration did not
recover a relation within 1,000,002 SAT conflicts. SAT conflicts are
not field operations; the result does not measure an expected cost per
successful decomposition, natural relation yield, novel matrix rank,
or a complete N131 `2^x`.

The [Q1445 matched pair-table control](../q1445_matched_pair_table/README.md)
uses the same N53 curve, base, and ordinary public target and did recover
a four-point relation after 500,000 target-independent pair samples and
54,545 target-dependent pair samples. Its operation unit and preparation
boundary differ from Q1454's, and the host has no CPU-isolation receipt;
the two rows do not define a speed ratio. Q1454 strengthens the case for
a target-coupled multi-leaf or pair-output search rule before extending
the same SAT search budget again. The challenge gate remains closed.
