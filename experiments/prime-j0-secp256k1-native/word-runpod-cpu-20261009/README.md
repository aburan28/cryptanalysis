# Signed-word unit-orbit recoder: Linux replay

The opt-in signed-word U14/U15/U16 benchmark CLI reproduced all 129
expected secp256k1 fixture points per format on RunPod CPU Pod
`zbeg026fw61so1`. One direct candidate case and one reference case per
format also passed. The [checker receipt](word-cli-check-linux.json) binds
the release binary (SHA-256
`def491150700063bf9aab700bc7d1beebee1d6653c497f3be1f4aea7fa5ddebf`)
to the exact source, fixture, protocol, and checker. The [build
log](word-build.log) and [checker log](word-check.log) preserve the command
outputs. Local timings from this correctness replay were discarded.

Three five-repetition manifests pair each prior BigInt recoder with the
signed-word recoder in the same binary and on the same nine scalars:

| Format | Manifest | SHA-256 |
| --- | --- | --- |
| U14 | [BigInt/word](u14-bigint-vs-word.json) | `45c6065e9dcc2e509dd37d7ffb6a45e888f1d2c10262b72212a681f1f36943d3` |
| U15 | [BigInt/word](u15-bigint-vs-word.json) | `c344afd879b2c07ab87ccfb3929ac7bbe84c9077c75448520d6a0e4a91a9112b` |
| U16 | [BigInt/word](u16-bigint-vs-word.json) | `4ace12f7fe0867583b601cb7325bca64138bfcd5acfd3867b72a10155d35c7b9` |

Each strict host preflight returned `ok: false` and 22 problems:
[U14](u14-bigint-vs-word-preflight.json),
[U15](u15-bigint-vs-word-preflight.json), and
[U16](u16-bigint-vs-word-preflight.json). The Pod is a Docker allocation
without the required host-level isolated CPU partition, fixed frequency,
`nohz_full`, and IRQ routing. No timing job was submitted. A controlled
online ratio remains unknown until these frozen methods and workload run
on a qualifying host.

The native recoder and protocol were frozen in `d0200bc8` before the
Linux replay. The release tests checked signed arithmetic at power-of-two
and sign boundaries, exact per-window digit parity and independently
expected points for all 129 fixture scalars per format, plus 256 fresh
full-range scalar outputs per format against the BigInt path.
