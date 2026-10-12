# E-1 sparse26 root-directory capacity at 29.9 million N83 states

The 26-bit sparse bitmap-rank directory indexed **29,900,000** sampled
pair states, stored **59,799,706** distinct root keys, and completed the
same one-target scan under a **5,500 MiB** RSS cap. Against the committed
24-bit capacity receipt on workload `63dd0929cf33`, it reduced exact
full-key probes from **320,593,637 to 69,190,310**. Both runs retained the
same first-witness lookup sample, target/root counts, correctness control,
and `state_cap_no_relation` status.

This is proposal `Q2026101131` on curve `EC1N83Ckb1h876c2921cb64`,
field size `2^83`, subgroup order `2417851639230796216685689`, and the
same public target `(7378557141477440425043731,
6374944737560147782643405)` in polynomial encoding. The factor base has
30,977,592 usable points and 186,612 folded columns. The complete IC
candidate ID remains `null` for this bounded point-decomposition stage.

| Measurement | Sparse24 receipt | Sparse26 receipt |
| --- | ---: | ---: |
| Index states; distinct root keys | 29,900,000; 59,799,706 | 29,900,000; 59,799,706 |
| Root-table allocation | 1,027,054,592 bytes | 1,237,818,368 bytes |
| Target full-key probes | 320,593,637 | 69,190,310 |
| Target process CPU | 65.097 s | 46.410 s |
| Target-stage wall | 145.423 s | 342.694 s |
| Index build process CPU | 21.519 s | 21.237 s |
| Index build wall | 38.790 s | 292.825 s |
| Observed peak RSS | 5,355,683,840 bytes | 3,656,941,568 bytes |
| Native status | `state_cap_no_relation` | `state_cap_no_relation` |

The wall clocks show substantial host contention between these separately
timed macOS runs. The observed peak RSS also moved opposite the allocated
root-table size, so the table allocations and each run's cap check are the
useful structural memory evidence; the RSS difference is retained as an
observation. The process CPU contrast is exploratory. No host-isolation
receipt accompanies either run.

The target clock starts after index construction and x/y cache preparation.
Sparse26's target query preparation, partner generation, partner checking,
and recorded residual sum to its charged target-stage wall time. The raw
[producer output](run_sparse26_cachedxy_29900000.json) and
[run record](run_record.json) retain the phase clocks, operation counts,
source and binary digests, cap, and raw status. Source SHA-256 is
`8a57c4d994c47344d7093c1103bfadc80e48f666e49f346bf729b80404132b05`;
the rebuilt binary SHA-256 is
`1944005d907ee2c3f02512fcad741b22db689874021a5c6ebe6ae36af892e4f0`.
The same source passed a complete 4-million-pair, 8-million-root partner
audit on the frozen 2M-state workload in the [sparse26 candidate receipt](../packed_index_e1_sparse26_cachedxy_cpu_20261011/README.md).

`python3 verify.py` checks the frozen source/input and workload hashes,
raw output digest, all counts and phase sums, the cap, and equality of the
target and lookup invariants to the [sparse24 capacity receipt](../packed_index_e1_capacity_20261011/README.md).
The reference is pinned to commit `b3287843e` and raw-output SHA-256
`19341c67bb113c9d5b80b44f1ea22d3d687405c246eb34dde463a55dbabea7b4`.
To replay without overwriting the recorded run, copy `capacity_probe.py`
and `verify.py` into a new sibling experiment directory, build the parent
sparse26 source there or use an exact binary, then run `prepare` followed
by `run` with `--binary` pointing to that binary.
