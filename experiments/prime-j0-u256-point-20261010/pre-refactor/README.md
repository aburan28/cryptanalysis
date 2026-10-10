# Initial whole-table conversion record

The first implementation built the complete 78,470,208-byte Eisenstein U14
table and then converted its point rows to four-limb Montgomery coordinates.
Its 79/79 release tests and both 129-point fixture modes passed. The
[source-bound receipt](verification.json) identifies the executed binary as
`1ffe8248f942e0512c008bae021ae13770cc07d7801ea34ab8bf87b1eebfe581`.
The archived [builder source](unit_orbit_windows.rs) has SHA-256
`7681689d519e007282bdb1daa285fa44da460f5b1843e89e59fe001e5477cc21`,
matching the source hash in that receipt.

The matched one-case macOS resource commands recorded a peak resident set
of **387,989,504 bytes** for this candidate and **345,849,856 bytes** for
mode 125. The extra table during conversion raised setup memory. The raw
commands and counters are in `candidate-resource.*` and
`reference-resource.*`; their local CPU times have no isolation receipt.
An earlier sandboxed `/usr/bin/time -l` invocation could not query
`kern.clockrate`; its nonzero exit and output are retained as
`candidate-resource-sandbox.*`.

The current implementation builds and converts one window at a time. Its
separate source-bound receipt and resource record belong in the parent
directory.
