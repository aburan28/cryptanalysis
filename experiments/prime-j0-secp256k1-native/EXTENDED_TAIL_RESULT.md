# Extended exact shared-Z scalar tail

This optional secp256k1 scalar path extends the exact sixfold-symmetric
`Z[τ]` action atlas from norm 4,096 to norm 65,536. The actions and group
formulas are unchanged. The larger atlas replaces more of the high-state
greedy policy with offline minimum-cost decisions. It is a research variant,
not a measured CPU speedup or an established academic novelty claim.

## Construction and verification

`generate_shared_z_tail65536.py` solves 79,242 pending-τ state/action slots
over 39,621 canonical ring points. All transitions above norm 49 strictly
decrease norm, so the generator processes those points in increasing norm.
It excludes ten nondecreasing candidate actions at norm at most 49, then
compares its costs with the older Dijkstra solution at every one of the
29,688 states under norm 4,096. All costs match. The maximum decoded tail
length is ten actions.

The immutable `shared-z-tail65536.bin` has 81,286 bytes and SHA-256
`896738c79d42a03e4b7fdc8fb318119713098d518848e8e29e32b2f7fc104538`.
It stores one action byte for each pending-τ state, plus two-byte row offsets
and minima. The extra footprint over the 4,096 atlas is 75,957 bytes.

The native unit test reconstructs all 475,452 oriented ring states with both
pending flags. All 44 crate tests pass. Sequential release-binary replay
matched the independently frozen affine point on all 256 cases in each of
four panels (1,024/1,024), plus all 30 cases in `edge-fixture.json`,
including the zero scalar. Source operation totals from native execution
match the Python generator exactly:

| Frozen panel | Norm 4,096 M+S | Norm 65,536 M+S | Reduction |
| --- | ---: | ---: | ---: |
| Fresh | 333,095 | 332,735 | 360 (0.108%) |
| Coset | 332,943 | 332,642 | 301 (0.090%) |
| Linked fresh | 332,749 | 332,359 | 390 (0.117%) |
| Zero-τ | 332,844 | 332,548 | 296 (0.089%) |

The 64-case design panel is 83,240 versus 83,129 M+S. `M+S` counts the
implemented field multiplication and squaring formulas, including seed
preparation, common-Z alignment, scalar steps, and digit additions. It does
not account for table locality, recoder instructions, or memory traffic.

## Controlled timing handoff

`make_shared_z_tail65536_manifest.py` produces 256 paired, five-repetition
jobs for the [isolated benchmark service](../../docs/ISOLATED_BENCHMARKS.md).
It compares `--benchmark-shared-z-degree-seven-tail-case` against
`--benchmark-shared-z-degree-seven-tail65536-case` on the same frozen point
and executable. The manifest passes the service schema validator; one timed
command from each arm returned the frozen point and an `online_ms` field.
The internal timer starts before scalar and base parsing, and stops after
the affine result is independently checked. Fixture loading, process launch,
and lazy constants are outside it. No host-qualified isolation receipt has
been collected, so CPU speedup is unknown. The larger table may erase its
small field-operation benefit through cache misses.

The recoder is variable time and is unsuitable for secret scalar use.
