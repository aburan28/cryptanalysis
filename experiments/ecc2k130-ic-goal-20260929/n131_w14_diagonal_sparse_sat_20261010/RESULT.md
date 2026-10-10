# Ten diagonal W14 atoms in a reciprocal S3 circuit on ECC2K-130

The ten-atom reciprocal encoding now has a complete, group-verified N131
construction. It represents each raw diagonal atom
`D(w) = P(w) + Frobenius(P(w))` by the linear reciprocal coordinate
`1/x(D(w)) = w`; five same-rotation leaf pairs use sparse products of their
14-bit masks. The [constructed XCNF](constructed.xcnf.gz) has **126,481
variables, 72,815 AND gates, 676,759 CNF clauses, and 52,474 native-XOR
rows**. Its full assignment satisfies every clause and XOR row, and the
[independent Sage audit](sage_audit.json) verifies all ten leaf points, nine
joins, cofactor-four projection, and subgroup membership. The exact
uncompressed formula SHA-256 is
`22813420cc86e2144cb165f14e58e51867108cb82523a74c5a57a4e074fa6c24`.

The [published-point query](public_query_v2/result.json) used the exact
`EC1N131Ckb1heb5f1998f20b` curve, one fixed published `ecc2k-130` point,
and ten unpinned W14 masks. The projected factor base has **B = 82,200**
actual usable points and **K = 8,160** folded columns. Four raw preimages
of the public subgroup point were offered as one-hot alternatives; every
mask, intermediate reciprocal, and target-fiber choice was solver-controlled.
The [published XCNF](public_query_v2/system.xcnf.gz) has decompressed
SHA-256
`8e108f5fc42d45103196a6b288ac69bb75d443fa14b3be55fad5aec104f8a654`.

| Exact N131 stage diagnostic | Prior same-rotation W14 source frame | Diagonal reciprocal atoms |
| --- | ---: | ---: |
| Projected base points `B` | 82,200 | 82,200 |
| Folded columns `K` | 8,160 | 8,160 |
| Published formula AND gates | 59,049 | 72,785 |
| Published formula CNF clauses | 635,469 | 676,669 |
| Published formula XOR rows | 47,978 | 52,462 |
| Published formula variables | 108,219 | 126,439 |
| Published-point one-worker status at 120 s | `CENSORED_TIME` | `CENSORED_TIME` |

The diagonal reciprocal representation makes the leaf equations and the
existing [exact pair inverse](../n131_w14_diagonal_pair_inverse_20261010/RESULT.md)
available to one solver chain. In this full circuit, the upper S3 joins
dominate: the resulting published formula is larger than the earlier source
frame. The unpinned solver performed active search for **116.395 seconds**
after **2.677 seconds** of target formula construction and stopped at its
frozen cap, without a SAT or UNSAT line. The total bounded query wall was
**119.963 seconds**, sampled combined RSS peaked at **643,907,584 bytes**,
and stderr was empty. The [terminal audit](terminal_audit.json) verifies
both decompressed formula hashes, the exact public point, frozen source
hashes, solver logs, and the censored status. These are construction and
search-stage measurements on an ordinary host; no CPU isolation receipt
supports a wall-time speedup comparison.

The first constructed-formula attempt stopped on a Python module-name
collision before formula output; its [failure receipt](failure_v1.json) and
original [protocol](protocol.json) are preserved. The corrected construction
was frozen in [v2](protocol_v2.json) before execution. The first published
query likewise stopped before formula output on a separate `profile` import
collision; its [failure receipt](public_query/failure_v1.json) and
[protocol](query_protocol.json) are preserved. The executable public query
used the [v2 protocol](query_protocol_v2.json). The constructed control uses
the first five disjoint-column positive pair outputs from the independently
audited pair-inverse panel; the public query used the published point.

This is a bounded decomposition gate with `candidate_id: null`. It produced
zero verified public relations and zero novel matrix rows. The next
algorithmic step is to replace the five leaf SAT joins with a factored
pair-image membership and inversion gate: propose reciprocal pair outputs
from the upper chain, apply the exact W14 diagonal pair inverse to each,
and measure accepted public outputs, independent group replay, query cost,
and novel relation rank under the same 4-GiB envelope. The existing dense
N131 global pair polynomial would require over 4.5 GiB of coefficient
storage, so that gate needs a sparse or sharded representation. A successful
public decomposition would then feed the frozen ordinary-query yield and
factor-log stages before single-target online timing can be assessed.

Replay sources: [control and source freezer](prepare.py), [reciprocal
circuit](circuit.py), [constructed full-assignment check](profile.py),
[Sage group replay](sage_audit.py), [published query](query.py), and
[artifact audit](terminal_audit.py). All Sage invocations used the repository
`./sage` launcher; [runtime receipt](sage_runtime_info.json) records the
checked installed build.
