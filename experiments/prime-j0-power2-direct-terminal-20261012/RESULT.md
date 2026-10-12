# Direct-terminal radix-256 scalar format

Fifteen six-unit radix-256 orbit rows and one direct terminal row give a
**177,174-point** fixed-generator secp256k1 format with at most sixteen
selected points per scalar. Its point payload is **11,339,136 bytes** at
64 bytes per point, 2,587,840 bytes below the radix-286 format's point
payload. The new layout also uses 30,378 fewer point entries than the
existing U16 all-window format. The native evaluator reports **11,652,560
retained bytes** including atlas and row metadata, 2,656,568 bytes below
the radix-286 evaluator's 14,309,128 bytes.

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

## Frozen native replay

Commit `598f4e57d461b0deabccff30d85285ac8909f4f4` froze the native
builder, evaluator, holdout generator, and verifier before the new panel
was drawn. [holdout.json](holdout.json) contains 512 distinct scalars
disjoint from earlier panels; its SHA-256 is
`55e0e3e39eb751ecd873f5e1d38e8645ccbdbe80763dd7205d0accf2b236fd8a`.
Commit `d79b5b7b6f585e00f1e145cb74d2de978634b15f` then froze
[holdout2.py](holdout2.py) and the three-panel verifier before a further
512 scalars were drawn. [holdout2.json](holdout2.json) has SHA-256
`b122c90b6ba7c8c9c6846d080db96a760534e813507257703f8ea0843e9ce591`;
the generator checks disjointness from the 4,096-scalar design panel and
eight earlier holdouts and records their digests. The [replay receipt](replay.json)
records complete-point agreement with the radix-286 evaluator and
independently generated points for all three panels. The same panels pass on macOS
ARM64 and Linux ARM64; [local-build.json](local-build.json) and
[linux-build.json](linux-build.json) retain the source and binary hashes.
[replay-two-panel.json](replay-two-panel.json) preserves the earlier
two-panel receipt.

| Panel | Cases | Direct-terminal noninitial additions | Radix-286 additions | Direct-terminal rotations | Radix-286 rotations | Direct-terminal retained bytes | Radix-286 retained bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Prior control | 512 | 7,679 | 7,680 | 1,021 | 1,024 | 11,652,560 | 14,309,128 |
| New frozen panel | 512 | 7,680 | 7,680 | 1,021 | 1,020 | 11,652,560 | 14,309,128 |
| Design-disjoint panel | 512 | 7,680 | 7,680 | 1,023 | 1,022 | 11,652,560 | 14,309,128 |

The native atlas audit checked all 65,536 residues and reported 177,174
point entries. The Linux replay used the pinned `rust:1.93.1-bookworm`
ARM64 image and an offline native build. Operation counts and retained
bytes are exact diagnostics for this implementation. The next experiment
is a paired online CPU measurement on a host that passes the repository's
isolation preflight; wall-time ordering remains unknown until then.
