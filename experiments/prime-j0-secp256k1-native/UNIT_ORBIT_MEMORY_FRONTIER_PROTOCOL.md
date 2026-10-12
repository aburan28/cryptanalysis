# Unit-orbit fixed-base memory frontier: frozen protocol

## Contribution under test

Use the same nearest Eisenstein representative and six-unit residue-orbit
maps as the 14-window fixed-generator method. Vary only the positional
radix schedule. The purpose is to measure the cost of replacing one or
two online mixed additions with a smaller resident point table.

| Format | Ordered window widths | Total bits | Orbit point slots | Maximum mixed additions |
| --- | --- | ---: | ---: | ---: |
| U14 | `10` three times, then `9` eleven times | 129 | 1,004,904 | 13 |
| U15 | `8` six times, then `9` nine times | 129 | 458,772 | 14 |
| U16 | `8` fifteen times, then `9` once | 129 | 207,552 | 15 |

The radix-256 orbit map has 10,924 entries and the radix-512 map has
43,692. The U15 point payload is 33,031,584 bytes and U16 is
14,943,744 bytes at 72 bytes per slot. Both use a 1,310,720-byte pair
of four-byte residue maps and 218,464 bytes of canonical digit pairs,
before table-vector metadata and allocator rounding. The U14 data and
source snapshot are preserved in PR #542; this protocol does not
retroactively change its receipt.

For both new schedules, every radix is at least 256 and the product is
`2^129`. The nearest-digit norm is at most `B^2/3`, so after the final
window the Eisenstein norm's square root is strictly below

`1/(2*sqrt(3)) + 256/(255*sqrt(3)) < 1`.

The final coefficient pair is therefore exactly zero in the integer
lattice, and the group point equals `[k]G` after reducing the scalar
modulo the subgroup order.

## Verification and measurement boundary

Implement separate opt-in CLI modes for U15 and U16. Verify the exact
residue map for both radices, all retained point slots against
independently built group sums, the existing 6,492-case scalar corpus
against U14, 256 fresh independent `[k]G` points from
`random.Random(20261009515)`, and the 129 expected fixture points.
Record source and binary hashes, per-format retained payload bytes,
exact outputs, nonidentity-window counts, and failures. The two new
formats are valid if all checks pass and their retained payloads fit
the 90 MiB cap.

The local point-operation proxy is a deterministic diagnostic only.
The acceptance criterion for an online CPU speedup is a paired,
correctness-checked wall-time panel for the same public scalars and
resource envelope on a host passing the isolated benchmark preflight.
The interval includes decomposition, residue lookup, unit action,
table access, point work, and recovery verification. Preserve U14 as
the reference and keep U15/U16 opt-in until such timing is available.
