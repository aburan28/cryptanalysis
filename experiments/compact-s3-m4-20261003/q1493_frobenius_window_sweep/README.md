# Q1493: Frobenius-swept first-window compact S3 search

Q1493 tests a complete symmetry reduction for the Q1481 window-orbit
factor base. It fixes the **first** raw leaf's cyclic window to start zero,
then searches the Frobenius orbit of the ordinary public target. It leaves
all four raw leaf x values, both pair midpoint x values, the other three
window selectors, and the target-preimage selector unpinned. The compact
three-link S3 chain and Q1482 native solver are unchanged; no expanded S5
or full pair table is constructed.

For any original relation, the first leaf lies in a cyclic window starting
at some `s`. Applying Frobenius to all four raw leaves and the target by
`n-s` moves that first window to zero. The Q1481 base is a union of
Frobenius orbits, so a sweep of all `n` target rotations covers every
original four-point relation. A found model would be inverse-Frobenius
transported and verified on the original public point. This is a
mathematical coverage statement for an **uncapped** sweep. The finite
search caps below do not prove a relation absent.

The [design](design_protocol.json) and [frozen protocol](protocol.json)
retain the exact Q1481/Q1482 curves and factor bases:

| Degree | Exact curve ID | Actual usable `B` | Folded `K` | Set SHA-256 |
| ---: | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 430,360 | 4,060 | `42e746657e39ea4d07aafc873110339e314cd685b3bd8493eb3c60aed1354ba5` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 348,006,384 | 2,096,424 | `f2d7771988cbd03fa4ea3145fc3870e5a3fc44171b9a57165257f016cdeb19d4` |

Q1493 remains a proposal with `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. The ordinary public target and raw target-preimage set
come from Q1482, then are transformed by the declared Frobenius exponent.
Each rotated CNF adds exactly one unit clause to Q1482's compact formula:
the first leaf's window-zero selector. The native cap is 5 seconds per
rotation in the full sweeps, with a separate 60-second positive control.

The [known-witness preflight](known_witness_preflight.json) verifies that
rotation 44 maps Q1490's ordinary N53 raw witness into the first-window-zero
cell, selects the correctly rotated raw target preimage, and transports the
public relation back. After the search runs, a separately [frozen rotated-CNF
control](control_protocol.json) then pins that exact witness into the
Q1493 rotation-44 CNF. Its [SAT receipt](control/r1/receipt.json) records
zero conflicts, 51,155 propagations, and an independently replayed
four-distinct-column relation after inverse Frobenius transport. This
proves the actual rotated CNF accepts the ordinary witness. The same
formula with leaf, midpoint and target-choice pins removed reached its
60-second native cap without a model. The pinned result is a correctness
control, not an unpinned cost observation.

## Frozen ordinary results

| Cell | Rotations tried | Result | Charged stage time, exploratory | Native field mul calls | Direct right-S3 evaluations |
| --- | ---: | --- | ---: | ---: | ---: |
| N53 known-positive rotation 44 | 1 | 60 s cap, no model | 60.227 s | 572,023,829 | 142,979,200 |
| N53 ordinary full sweep | 53 | all 5 s caps, no model | 277.061 s | 2,533,791,065 | 632,029,632 |
| N83 ordinary full sweep | 83 | all 5 s caps, no model | 450.794 s | 2,166,602,753 | 539,336,752 |

The [independent accounting audit](archive_audit.json) checks every
rotation attempt, native `wall_cap` status, original public target,
factor-base identity, source custody, operation sum, exclusive phase sum,
and zero verified relations. The source-bound replay rebuilds every
rotated CNF and target list from the frozen inputs. Target rotation and
formula construction are included in the charged stage interval. These
wall values are exploratory because the host has no isolation receipt;
field multiplication counts at different degrees are not calibrated to a
common work unit.

Q1493 gives a full-base search *policy* and measured bounded ordinary
attempts at both degrees. It does **not** give a successful N53 or N83
compact decomposition, natural relation yield, cost per useful row,
late-rank behavior, final matrix cost, target descent, or a complete
N131 `2^x`. The complete work field remains `null`, and the challenge
gate remains closed. The Q1488 pair table found one relation on the same
N53 target with separately charged preparation; Q1493's zero-relation
sweep cannot form a per-relation speed ratio with it.

The next solver change needs a way to reason over many coupled four-leaf
window domains at once. Q1483's one-orientation slice and this
Frobenius-complete sweep show that window-position symmetry breaking
alone has not crossed the unpinned correctness gate.

## Reproduce custody checks

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1493_frobenius_window_sweep/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1493_frobenius_window_sweep/run.py --preflight --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1493_frobenius_window_sweep/freeze_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1493_frobenius_window_sweep/run_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1493_frobenius_window_sweep/run.py --cell n53_known_rotation_44 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1493_frobenius_window_sweep/run.py --cell n53_sweep --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1493_frobenius_window_sweep/run.py --cell n83_sweep --check
python3 experiments/compact-s3-m4-20261003/q1493_frobenius_window_sweep/audit.py --check
```
