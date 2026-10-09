# Thirteen-window radix-943 unit-orbit format

The optional radix-943 format reconstructs every reduced secp256k1 scalar
in thirteen Eisenstein windows and evaluates it with at most twelve mixed
point additions. The exact covering-radius certificate in
[`radix943-screen-result.json`](radix943-screen-result.json) passed, and the
native implementation retained **142,873,744 bytes (136.255 MiB)**,
including its 1,926,717 affine point entries, residue atlas, digit list,
and table metadata. It fits the declared 140 MiB cap.

| Frozen check | Result |
| --- | ---: |
| Radix-943 residue pairs with congruence and norm checked | 889,249 / 889,249 |
| Exact scalar reconstructions, including five boundaries | 4,101 / 4,101 |
| Native scalars matched against same-binary U14 | 4,230 / 4,230 |
| Independent scalar-point checks | 261 / 261 |
| Independent table-entry group-sum checks | 1,926,717 / 1,926,717 |
| Release native test suite | 60 / 60 |

The native point replay includes the existing 129-case fixture, 4,096
deterministic full-range scalars, and five boundary scalars. Across those
4,230 inputs, U14 used **54,925** mixed additions and radix-943 used
**50,700**, saving 4,225 additions (7.69%) at this operation boundary.
Each of the 4,096 full-range cases used twelve additions in radix-943.
The [native receipt](radix943-native-final-result.json) records the exact
binary and source hashes, point digest, input digest, retained memory, and
both addition totals. The full release test command was:

```sh
cargo test --offline --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed -- --test-threads=1
```

Its [raw test log](radix943-full-tests.log) records all sixty test results.

The point-operation reduction costs **64,403,616 more retained bytes** than
the U14 format's 78,470,128-byte payload. The two formats use different
fixed-base table sizes, so the comparison is a memory/operation frontier,
with table preparation excluded from the per-scalar online interval and
reported separately. The source currently uses BigInt remainder/division
by 943; recoding and larger-table lookup traffic may offset the saved point
addition. A CPU wall-time comparison requires a paired manifest from
[`make_radix943_isolated_manifest.py`](make_radix943_isolated_manifest.py) on
a host that passes the strict isolation and noise gates. The current RunPod
Pod's rejected host preflight cannot supply that measurement.

The six-unit table symmetry and Eisenstein expansions have prior art in the
paper supplied for this project. Academic priority for the specific
thirteen-window fixed-base layout remains to be assessed.

The follow-up [complex-radix capacity screen](../prime-j0-complex-radix-20261009/RESULT.md)
proves that changing radices within the same thirteen-window norm-covering
certificate can save at most 67,248 affine point bytes. It also gives the
exact twelve-slot capacity requirement under the 140 MiB table target.
