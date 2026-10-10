# Separate leaf and projective-state releases both sustain bounded SAT search

The Q1420 exceptional-witness controls now isolate the two unfixed input
blocks of the complete six-summand native-XOR circuit. On both the ECC2K-130
source and degree-263 descendant-native curves, fixing the six masks and leaf
x/z coordinates while releasing only four projective intermediate states
reached the 150-second external wall guard with active CryptoMiniSat search.
Fixing masks and intermediates while releasing only leaf x/z coordinates did
the same. The fully fixed witness remains an independently checked SAT model
in the [parent gate](../ecc2k130-263-projective-s3-sat-20261010/RESULT.md).
The result points to propagation/search costs in **both** released blocks,
rather than isolating a single block that the frozen solver quickly resolves.

| Curve policy | Released block | Added fixed units | Status / stop | Wall | Child peak RSS | Last printed restart / conflicts |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| Source W24 prefix | Four projective states | 1,718 | `BOUNDED_UNKNOWN` / external wall guard | 150.061 s | 214,138,880 B | 836 / `342K` |
| Source W24 prefix | Six leaf x/z pairs | 674 | `BOUNDED_UNKNOWN` / external wall guard | 150.273 s | 273,072,128 B | 1,638 / `1124K` |
| Descendant-native W24 | Four projective states | 1,718 | `BOUNDED_UNKNOWN` / external wall guard | 150.296 s | 272,220,160 B | 887 / `402K` |
| Descendant-native W24 | Six leaf x/z pairs | 674 | `BOUNDED_UNKNOWN` / external wall guard | 150.292 s | 234,258,432 B | 1,641 / `1025K` |

`K` is CryptoMiniSat's rounded printed unit, not an exact conflict count. The
external SIGKILL prevented final exact conflict and restart summaries in all
four cells. Their last printed restart rows establish that search began. No
RSS guard fired. The solver commands used `--maxtime=120`, one thread, and the
pinned CryptoMiniSat 5.14.7 binary; all four were stopped by the separate
150-second wall guard before a terminal SAT/UNSAT/INDETERMINATE line. The
source and descendant mask-only parent controls instead returned explicit
`s INDETERMINATE` at 122.340 and 121.717 seconds, with exact final conflict
counts of 473,345 and 598,278. The host was an Apple M4 Pro running macOS
26.6 without a host-isolation receipt, so these walls and conflict-throughput
differences are exploratory solver-stage data.

The [frozen protocol](PROTOCOL.md) and [config](CONFIG.json) were pushed before
the four outcomes. `make_cells.py` required the new unit sets' intersection to
equal the parent's 146-unit mask-only control and their union to equal its
2,246-unit fully fixed positive control. The two 1,718/674-unit deltas and
four exact XCNF SHA-256 digests were committed before solver launch. The
parent's two archived base XCNFs are reused by hash; all four complete stdout
streams, stderr files, resource receipts, and unit deltas are archived in
`runs/R1`. The [archive-only audit](runs/R1/audit.json) reconstructs all four
inputs, verifies source/input/solver and transcript hashes, checks the exact
released-variable partitions independently, and records the parent controls
and last printed search rows. Its post-run progress-row extension is described
in [AUDIT_AMENDMENT.md](AUDIT_AMENDMENT.md); it did not change or repeat a
solver cell. The first audit result and replay from committed archives are
byte-identical. The exact environment record is
[runs/R1/environment.json](runs/R1/environment.json).

This leaves `candidate_id`, natural relation yield, novel rank, single-target
online IC time, and matched rho ratio null. A bounded witness search is not
evidence about ordinary-query yield. The next encoding experiment should
replace the relational leaf/S3 subcircuits with explicit sign-lift and
projective-addition choices, then compare it against this exact witness and
one frozen ordinary query under the same cap. A smaller first diagnostic is
to release one leaf pair or one S3 intermediate at a time from the fully fixed
witness, locating the earliest propagation failure. Only a verified ordinary
relation and its rank contribution can promote that encoding toward the
end-to-end IC comparison.

Replay the audit without the local full XCNFs or raw stdout:

```sh
python3 -B experiments/ecc2k130-263-projective-s3-blocks-20261010/audit.py \
  --run-dir experiments/ecc2k130-263-projective-s3-blocks-20261010/runs/R1 \
  --out /private/tmp/ecc2k130-projective-s3-blocks-audit-replay.json \
  --scratch-dir /private/tmp
cmp /private/tmp/ecc2k130-projective-s3-blocks-audit-replay.json \
  experiments/ecc2k130-263-projective-s3-blocks-20261010/runs/R1/audit.json
```
