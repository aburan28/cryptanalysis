# GLV10 paired panel: Linux replay and isolation decision

The fixed-base GLV10 benchmark CLI reproduced all 129 expected secp256k1
generator points on the existing RunPod CPU Pod `zbeg026fw61so1`. Its
[checker receipt](glv10-cli-check-linux.json) binds the result to the
same Linux release binary used for the earlier U14/U15/U16 replay:
SHA-256
`2643c2e7314ec473a3e6811683741317d00a3506b2f390ae79cf2eb09c8fe5c3`.
The [checker log](glv10-check.log) records completion. It discarded all
local timing values.

The GLV10/U14, GLV10/U15, and GLV10/U16
[manifests](glv10-vs-u14.json) use the same nine scalars, five
repetitions, fixture point assertions, and binary. Their SHA-256 hashes
are, respectively:

| Candidate | Manifest | SHA-256 |
| --- | --- | --- |
| U14 | [GLV10/U14](glv10-vs-u14.json) | `6de656060f8b3de730ffeb22b878ce451dd8ddfd600dfa30146c015f99bd78c7` |
| U15 | [GLV10/U15](glv10-vs-u15.json) | `8a239f06f8637c5741a85bc7cc2a98dc677a8b5c850cc146d2054cc01acfbf43` |
| U16 | [GLV10/U16](glv10-vs-u16.json) | `0d50846f23f6504bad1754f63297ef0546013dda0aac404dd872df8d6675f945` |

The exact [U14](glv10-vs-u14-preflight.json),
[U15](glv10-vs-u15-preflight.json), and
[U16](glv10-vs-u16-preflight.json) preflights each returned `ok: false`
with 22 host-isolation problems. The Pod remains a Docker allocation with
cgroup v1, no host-level isolated partition or `nohz_full` set, unfixed
CPU frequency, and overlapping IRQ affinity. The manifests were not
submitted to the timing queue. The controlled online comparison remains
unknown until the same source and workload are replayed on a host that
passes the preflight.

The generator and checker were frozen in `d7653b77` before this Linux
replay. The binary source matches the prior U14/U15/U16 Linux receipt
from `60d56390`; the new protocol did not change the executable.
