# Q1430: actual partial-pair trail gate

Q1429's span rejections used synthetic partial leaves and independently
uniform intermediates. Q1430 asks whether the frozen Q1427 solver reaches
comparable **weight-unsaturated** states while searching its actual public
targets. It copies Q1427's exact CNF, reverse-root propagator, decision order,
target-preimage lists, curve and factor-base identities, and limits. The added
observer emits no clause and changes no decision. It runs after each observed
SAT assignment and records:

- notifications with the second pair intermediate fixed and both leaves
  partial;
- those notifications with at least one weight unit left on each leaf;
- a narrower window with one or two units left and at most 14 free bits per
  leaf at N53 or 20 at N83.

The window admits arbitrary free-coordinate positions, unlike Q1429's
synthetic suffixes. It retains up to the first 256 distinct states and writes
the first 16 snapshots per cell. Notification counts can revisit the same
state. The snapshots are selected by solver order and are not a random
sample of all window states.

The [frozen protocol](protocol.json) pins the N53/N83 `EC1` curve IDs, actual
usable base sizes `B`, folded columns `K`, enumerated-set digests, workload
IDs, public targets, source and binary hashes, checked Sage runtime, and
60-second/one-million-conflict caps. This is proposal `Q1430`, with
`candidate_id: null` and `isogeny: "none"`. Its `PS1...` labels are solver
stage IDs, not complete `IC1` pipeline candidates.

## Archived result

Both known-witness freed-partner controls returned independently verified
four-point relations. Both unpinned ordinary queries reached the 60-second
wall cap without a relation. The [post-run audit](audit_verification.json)
reconstructed all four CNFs and receipts, replayed both controls, and applied
Q1428's sound span test to the first 16 saved distinct ordinary states per
degree.

| Degree | Curve ID | Actual `B` | Folded `K` | Ordinary result | Both partial notifications | Unsaturated notifications | Window notifications | First snapshots rejected by span |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 | 60 s cap; 0 relations | 311,876 | 311,869 | 207,522 | 16/16 |
| 83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 | 60 s cap; 0 relations | 150,830 | 150,830 | 81,765 | 16/16 |

At most 256 distinct window states were retained in memory per cell. The
first 16 are the only states tested offline; `16/16` is evidence that the
necessary-condition filter can reject real trail states, **not** an estimate
of its rejection rate across the search. The observer did not pay for a span
check while solving, so these counts show reachability rather than net work
savings. Both ordinary cells are censored; natural relation yield, an N53/N83
solve-growth fit, and the complete N131 `2^x` remain unknown. CPU wall times
on this host are exploratory under the isolation gate.

The preregistered `verify_archive.py` contains a chained-comparison typo:
it compares the integer window count to a parenthesized Boolean. It fails on
ordinary cells. The separate `audit_archive.py` fixes that assertion and
checks the unmodified frozen protocol, receipts, and original verifier hash.
Its own source digest is in the audit result. No solver source, protocol, or
run receipt was changed after the ordinary runs.

## Next gate

Implement a sound guarded partial-span propagator on the same frozen
ordinary N53/N83 targets. On each rejected state, the clause must be guarded
by every fixed leaf bit and the fixed intermediate so it cannot remove a
valid decomposition. Verify solution preservation with exhaustive small-field
cases and the archived witnesses. Charge the filter's field operations and
memory alongside saved reverse-root calls, then compare matched runs under
fixed work and resource limits. A useful result either recovers the known
representable N53 target or demonstrates a lower *total charged* cost at a
matched search-progress boundary. N83 still needs an independently verified
ordinary relation before any growth projection.

## Reproduction

From the repository checkout, build the local binary and check the frozen
runtime and protocol:

```sh
python3 experiments/compact-s3-m4-20261003/q1430_partial_trail/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1430_partial_trail/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1430_partial_trail/audit_archive.py --require-complete --emit
```

The [run order and limits](protocol.json) describe the original measurements.
`run_stage.py` refuses to overwrite an archived cell. All Sage jobs use the
checked repository launcher; the saved `sage_runtime_info.json` was captured
before the measured cells.
