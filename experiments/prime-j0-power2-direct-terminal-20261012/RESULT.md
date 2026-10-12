# Direct-terminal radix-256 scalar format

Fifteen six-unit radix-256 orbit rows and one direct terminal row give a
**177,174-point** fixed-generator secp256k1 format with at most sixteen
selected points per scalar. Its point payload is **11,339,136 bytes** at
64 bytes per point, 2,587,840 bytes below the radix-286 format's point
payload. The new layout also uses 30,378 fewer point entries than the
existing U16 all-window format. Preparation cost and complete resident
bytes remain to be measured in the native implementation.

The [exact census](search.json) checks all 79,879 terminal pairs, their
13,314 unit orbits, contiguous row ranks, and all unit-code images. The
[design replay](design.json) audits all 65,536 ordinary residues and
reconstructs the same 4,096 frozen secp256k1 scalar representatives as
the radix-286 control. It selects 65,534 terms versus the control's
65,536. The representative, source, input, row, and atlas digests are
retained in that receipt and [design-rows.jsonl](design-rows.jsonl).

The fifteen-step scalar identity, congruence, terminal cap, sector
uniqueness, and direct-domain coverage have checked Lean declarations
mapped in [PROOF.md](PROOF.md). The exact terminal count and row rank
have an exhaustive integer audit; their Lean bridge remains open.

The next gate is a source-frozen native implementation and a new disjoint
512-scalar panel with independent complete-point replay. A controlled
online CPU comparison follows on a host that passes the repository's
isolation preflight. The present result is a format and correctness-design
screen, with CPU wall-time ordering still unknown.
