# Local validation and measurement status

The opt-in independent preparation candidate passed the frozen physical Apple
M4 Pro correctness run. This does not establish a speedup.

- All ten native variants compiled with warnings treated as errors, including
  UBSan, transform/locality audits and explicit budget/fallback builds.
- All 30 unit groups passed, including stale and changed-input generations,
  exact mask representation binding, malformed/incomplete proofs, soft-budget
  reconstruction, owned buffers, concurrent contexts, producer/preparation
  failures and mandatory worker drain before close.
- The 6,001-system corpus produced 72,012 control executions across CPU, CPU
  UBSan and physical Metal with partial/projection toggles. There were 71,796
  verified bases and 216 expected root-limit inconclusive results. Every outcome
  matched round52; the inconclusive calls also drained preparation.
- All 648 complete queries passed: 216 each for serial, synchronous preparation
  and overlap. The panel covers 18 frozen public inputs through 27 variables,
  CPU/CPU UBSan/Metal, both symmetry modes and full/tile16 transforms. Proofs,
  bases, roots, selected witnesses and old integer counters matched round52.
- The separate Python original-ANF audit passed every query record, covering
  35 distinct proofs and exact reduced Boolean bases. All 490 executed source,
  receipt and binary bindings remained unchanged. Actual GPU dispatch was also
  checked for every query, including the intended wide-equation CPU fallback.

The first preregistered performance attempt admitted zero queries. Its two
admission windows observed one-minute loads from 19.665 to 23.694 against the
frozen threshold of 14. Both rejected admissions and 34 unrun trials are retained.
There are zero qualified timing trials and the primary acceptance gate is false.
The load threshold was not relaxed. The candidate stays opt-in; no speedup,
automatic routing change, asymptotic result or complete IC/rho result is claimed.

Evidence hashes:

| Artifact | SHA-256 |
| --- | --- |
| `physical-correctness-v2.json.gz` | `7b8ae8b56bbffc6979650972ea4683b5050238322194336623499b6c145c29a1` |
| `independent-audit-v2.json` | `35ffbbf06cf5bae0bf9fec5bf65a936f3e1e19f1838e700cf2c292e8967d8031` |
| `performance-analysis-v1.json` | `c2d30384763c662965190a92fb916b92344b1876593a637768572d26c1a0eda5` |
| `unit-tests-frozen-v2.log` | `a1f97218e1a125753169bbde9c01542924cb884a26522aefffd0355ba7b66800` |

The local artifacts reside in
`/private/tmp/cryptanalysis-overlap-evidence-20261003`. The complete validation and
measurement scripts and frozen plan are versioned in this directory. Native CI
will rebuild on each runner and retain complete artifacts; cross-platform CI
results are pending at this source snapshot. Physical timing claims require a
qualifying run of the unchanged paired plan after correctness and audits finish.
