# Exact second-link lookup on the N131 d13 public point

The audited second-link lookup was applied to **both complete first-link
roots** of the frozen d13/m12 public-point formula. Each branch reached its
285-second parent wall cap with `CENSORED_TIME` and zero model lines. The
[independent terminal audit](audit.json) passed every saved source and
formula hash, solver command, process identity and drain, output digest,
branch order, and phase sum. This closes a bounded search test of the
lookup-guided representation; the target-conditioned multi-pair search
remains the algorithmic bottleneck.

The exact curve is `EC1N131Ckb1heb5f1998f20b`, workload
`3c1992b7c92f`, with one supplied public point. The two branches share the
target-independent first leaf codes `(1948,651)` and fix the two complete
first-link S3 roots independently. The [lookup encoding
audit](../n131_d13_second_link_lookup_20261009/encoding_audit.json)
checks selector/output equivalence for all 4,134 valid third-leaf codes
on each branch. This run used those immutable XCNFs without changing
their records. [Protocol](protocol.json) and [checked Sage runtime](sage_runtime_info.json)
were saved before launch; the source and protocol were committed at
`034e2edbb` before any solver work. The independent terminal and potential
Sage-model replay programs were committed at `095f6de54` before the
terminal result.

| Exact first-link branch | Solver wall (s) | Sampled solver CPU (s) | Sampled parent-plus-solver peak RSS (B) | Status | Model lines |
| ---: | ---: | ---: | ---: | --- | ---: |
| 0 | 285.163 | 69.529 | 407,879,680 | `CENSORED_TIME` | 0 |
| 1 | 285.114 | 49.294 | 322,928,640 | `CENSORED_TIME` | 0 |

The **570.276-second solver-stage sum** charges both sequential attempts
to the same point. Source formula construction, target-dependent bridge and
projection work, lookup construction, and scalar verification were outside
these solver clocks, so complete one-target online cost is unknown. The
[run record](result.json) preserves the per-branch command, hashes,
exit code, cap reason, CPU and memory samples, and empty model status.
With no assignment in either raw log, `sage_replay.py` correctly remains
uninvoked; the independent encoding audit and checked-Sage full lookup
table audit are preserved as separate correctness evidence.

The host ran other CPU-intensive jobs during this panel, and no physical
CPU isolation receipt was obtained. The small sampled CPU times relative
to wall time make this an exploratory censored search result rather than a
controlled comparison with the earlier first-link-only formula. Both the
[N41 second-link control](../n41_phi_second_link_control_20261009/RESULT.md)
and this N131 panel reached their caps. The next candidate should use the
public target to generate or eliminate compatible outputs across several
still-free pair blocks, then prove a complete N131 work and memory bound
before another ordinary challenge-width search. This stage proposal keeps
`candidate_id` and `run_id` null; verified relation yield and useful rank
for this panel are zero observed within the stated caps.
