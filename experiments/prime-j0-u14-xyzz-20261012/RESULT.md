# U14 sector digit with one XYZZ accumulator

Format 158 evaluates the existing U14 sector-digit table with one XYZZ
accumulator and Solinas unit rotations. The table is 64,314,112 bytes; its
Solinas constants bring candidate retained state to **64,314,208 bytes**,
below the 64 MiB cap. Format 130 supplies the same representative, recoding,
table, and grouped unit order with its Jacobian accumulator.

| Correctness check | Result |
| --- | --- |
| Release unit test `sector_xyzz_replays_full_panel_and_independent_points` | 4,096/4,096 complete format-130 versus format-158 records matched, excluding the intentional 96-byte retained-state difference |
| Independent binary multiplication | First 128 points in the frozen panel matched |
| Release CLI fixture `--check-scalar-unit-orbit-u256-sector14-xyzz-fixed-fixture` | 129/129 cases verified; each raw line is retained in `cli-fixture.txt` |
| Host and compiler | Local Darwin arm64; Rust/Cargo 1.93.1 |

The same-panel source formula model in
`../prime-j0-u14-u12-paired-20261012/README.md` assigns 19,357,121 limb
products to the U14 XYZZ path, versus 20,530,564 for split-terminal U12 XYZZ
and 21,380,220 for current U14 Jacobian, on ordinary nonexceptional paths.
These are static source-loop estimates. The next run pairs formats 130 and
158 on the same scalar fixture with full operation timing and a passing
host-isolation receipt.

Source and replay identities (SHA-256):

| Artifact | Digest |
| --- | --- |
| `src/bin/eisenstein_fixed.rs` (final CLI dispatch and prewarm) | `7903931f939aab31529e30d277186b115c62743dfc811288071ffe210f45b8a7` |
| `src/bin/eisenstein_fixed/unit_orbit_windows.rs` (native evaluator and test) | `56398052b45da11f70617ec7775543b83c82215398230d990ac318ebf65bdd44` |
| Final release CLI binary | `5391a97ea197f0046d2418f2f68fa9382707c9820e19c3447af676f0cdf38827` |
| 4,096-scalar panel | `1dd3d17f3485c144f045cf0a81394b8d129095b74ac2de9a06e06d6f4ef2cd99` |
| 129-case CLI fixture | `2895d9c40912b090f0e6ce85ef8bb4d92822a83a5626fb376fcb552a556981fb` |
| 129-case CLI output | `f8990de72b76c5ed3518fdc91322203ac6536fbaa1e5c1b73c78d81d4d3f0e77` |

The unit test ran on the same evaluator source. The final CLI source adds
prewarming for format 158; its point-evaluation code is unchanged from the
passing unit test. CPU wall-time qualification remains pending a host that
passes `../../docs/ISOLATED_BENCHMARKS.md`.
