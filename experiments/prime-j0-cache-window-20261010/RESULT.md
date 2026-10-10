# Cache-sized U15 and U16 sector scalar formats

U15 and U16 evaluate the same secp256k1 scalar map as canonical-sector U14
with 29,361,680 and 13,283,616 retained point-table bytes, respectively,
versus 64,314,112 bytes for U14. The schedules trade at most one or two
additional mixed additions for smaller tables. They share the certified
Eisenstein representative, unit quotient, four-limb field arithmetic, and
grouped accumulator gauge. Their 129-bit reconstruction and exact table
allocations are derived in [PROOF.md](PROOF.md).

| Format | Widths | Point slots | Retained bytes | Maximum mixed additions | Peak process RSS on arm64 macOS |
| --- | --- | ---: | ---: | ---: | ---: |
| U14, mode 130 | `10*3,9*11` | 1,004,904 | 64,314,112 | 13 | 272,138,240 B |
| U15, mode 131 | `8*6,9*9` | 458,772 | 29,361,680 | 14 | 88,801,280 B |
| U16, mode 132 | `8*15,9` | 207,552 | 13,283,616 | 15 | 72,548,352 B |

The release suite passed 90 tests on Darwin arm64 with Rust 1.93.1.
It includes all 65,536 radix-256 residue comparisons; independent group-sum
checks for 666,293 nonidentity U15/U16 table entries; and 4,096 new,
disjoint scalars checked across all three formats, including full recoding
choices and operation counts. The first 128 panel points matched an
independent binary scalar path. Each format also matched all 129 points of
the frozen secp256k1 fixture. The run-level source, input, binary, raw
output, and RSS hashes are in [verification.json](verification.json).
The source commit before the panel was `a86c1aa9`; the replay source
commit is `0bdfdfe2`. The panel scalar digest is
`3ccb0456d56853ad829e0fce79ca0738d6a0eab15582b42d2a30f82e90e2d028`,
and the release executable SHA-256 is
`dfc64477ed8fad5211dd9b2d39f27443c9d612781f7bcf75abab618bebfaa752`.

The first resource-recording attempt failed because macOS denied
`/usr/bin/time -l` access to `kern.clockrate`; its output and failed
receipt are retained under [attempt1](attempt1). Per-child `wait4`
resource accounting then passed and is preserved under [attempt2](attempt2)
and the final receipt. The final generator also passed schema validation
for separate nine-case, five-repetition U14/U15 and U14/U16 manifests.

The Linux correctness replay is queued as
`20261010T072902Z_prime-j0-cache-window-0bdfdfe_GVK1E7` on the existing
RunPod serial worker, after the active N131 job and two earlier j=0 jobs.
Its 59-file source archive matched every SHA-256 on transfer; archive hash
`82b98593374db39ec9ef870a7e0ff63384745a54a25d8370544694decb26f5e2`.
That job will run the Linux release suite, all three fixture arms, and a
read-only host-isolation probe. A separate read-only
[host inspection](remote-host-inspection.json) found that the current Pod
exposes `tmpfs` at `/sys/fs/cgroup`, has no cgroup v2
`cpuset.cpus.partition` file, and stores `/workspace` on an overlay.
Consequently, this Pod cannot pass the service's strict isolated-partition
gate; its job is a Linux correctness replay. A CPU online ratio enters the
result table only after an administrator-controlled host passes the CPU,
NUMA, IRQ, frequency, and noise checks in
[ISOLATED_PANEL.md](ISOLATED_PANEL.md).
