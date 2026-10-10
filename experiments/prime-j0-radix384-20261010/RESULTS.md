# Radix-384 local correctness result

The fifteen-window radix-384 evaluator reconstructs the certified
Eisenstein representative and computes the same secp256k1 point as U15
on a fresh 4,096-scalar panel. Its orbit map has 24,578 entries per
window, and the implementation retains **24,283,336 bytes** across its
point tables, atlas and descriptors. That is 5,078,344 bytes (17.30%)
less than U15's 29,361,680-byte retained table, with the same bound of
fourteen mixed additions. The extra radix-384 divisions remain part of
the eventual online timing comparison.

| Local check | Result |
| --- | --- |
| Exact reconstruction inequality | passed |
| Residues and independent point-table sums | 147,456 residues; 368,670 point slots passed |
| Fresh panel | 4,096 points matched U15; first 128 matched independent binary multiplication |
| Mixed additions in fresh panel | 4,095 cases used 14; one used 13 |
| Release suite | 92 passed, zero failed |
| Fixed fixture | 129 radix-384 points verified; U15 rows matched after removing mode labels |

The implementation, protocol and deterministic input generator were
frozen in commit `9fee6b4c144a2daf476d98ed92c25dc8973bff57` before
the panel was generated. The panel's scalar stream SHA-256 is
`6ed364dd9df2c63b825a5680e9c224b4a2c8cc2cf8b2b49273f93e71c7bd611c`.
The [local receipt](evidence/local/receipt.json) binds the source,
binary, input and raw log hashes. The local host was macOS ARM64 and
these checks establish correctness and retained allocation, not a
controlled CPU wall-time ratio. The RunPod Linux replay is dispatched
separately through the serial queue; its container fails the host-level
isolation preflight, so its output is also a correctness receipt.
