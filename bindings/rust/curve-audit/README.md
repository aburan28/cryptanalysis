# `ca-curve-audit`: evidence-graded curve screening

`ca-curve-audit` is the big-integer curve-assessment binary in the
`cryptanalysis` Rust workspace. It accepts an exact JSON curve record and
emits one JSON row for each of the 61 versioned WeakCurves criteria. A row
states the observed condition, its evidence, and the next witness required
to advance the assessment. The catalog and its source revision are embedded
in the executable, so a report remains tied to the rules that produced it.

Build and run from the repository root:

```sh
cargo build --locked --manifest-path bindings/rust/Cargo.toml -p ca-curve-audit
bindings/rust/target/debug/ca-curve-audit catalog > criteria.json
bindings/rust/target/debug/ca-curve-audit audit \
  --input bindings/rust/curve-audit/examples/nist-p192.json --max-k 6 > p192-audit.json
```

The [P-192 input](examples/nist-p192.json) reproduces the parameters in
[NIST FIPS 186-4, Appendix D.1.2.1](https://nvlpubs.nist.gov/nistpubs/fips/nist.fips.186-4.pdf)
and demonstrates the 192-bit path.
The [anomalous F_101 input](examples/anomalous-101.json) exercises an exact
point-count and generator-order finding; the
[negative-trace input](examples/negative-trace-101.json) exercises a
nonanomalous result. Integers are strings in decimal or `0x` notation;
`a` and `b` may also be negative decimal strings for prime fields.

Input schema `ca.curve_input.v1`:

```json
{
  "schema": "ca.curve_input.v1",
  "name": "optional human label",
  "field": {"characteristic": "101", "degree": 1},
  "curve": {"model": "short_weierstrass", "a": "1", "b": "32"},
  "curve_order": "101",
  "subgroup": {"order": "101", "generator": {"x": "4", "y": "10"}}
}
```

The field representation is mandatory for extensions: set `degree > 1`,
`modulus`, and `element_encoding`. The first arithmetic backend handles
short Weierstrass curves over prime fields of characteristic greater than
three; extension-field and binary inputs retain all applicable catalog
rows as `unassessed` until their own arithmetic backends are added. The
parser rejects unknown keys, oversized integers, noncanonical prime-field
generator coordinates, and ambiguous JSON numbers for mathematical
parameters.

The backend checks the discriminant, generator-on-curve equation,
`[r]G = O`, bounded embedding degrees, small factors of the selected order,
and the same-field degree-two cover formula. It independently counts points
when the prime is at most `--point-count-limit` (default 100,000, maximum
1,000,000), then computes exact trace, twist order, cofactor and anomalous
or supersingular conditions. For larger primes, it records a fixed-base
probable-prime screen and labels any supplied curve order
`supplied_unverified`; generator annihilation alone does not prove the
whole curve order. The default embedding-degree bound is 32, with a maximum
of 256. A missing degree within the bound is reported as
`not_found_within_bound`, not as an all-degree result.

`condition_verified` means the current input and independently checked
arithmetic establish the stated mathematical condition. `structural_candidate`
means a prerequisite exists but the attack still needs its selected-subgroup
map, protocol behavior or full cost. `geometry_verified` records a cover or
special curve geometry, while `unassessed`, `outside_domain`, and
`not_found_within_bound` retain distinct meanings. The top-level verdict is
`invalid_parameters`, `weakness_condition_verified`, or
`incomplete_assessment`; it never silently converts unassessed methods into
a safety certificate.

For an optional isogeny-graph lookup, supply `--graph GRAPH.json` and an
exact `atlas_id` string in the input. The report records the graph hash,
matched node, and incident edges. `atlas_id` is supplied by the caller;
the binary does not derive an ICV1 identity from the coefficients, so graph
matches are `graph_record_unbound` until the identity and maps are replayed.
The bundled [catalog provenance](catalog/PROVENANCE.md) fixes the 23 indexed
criteria and 38 research checks imported from the WeakCurves atlas.

The next backend should verify prime-field point counts at 192–252 bits
with a reproducible certificate, then add extension-field arithmetic and
cover/isogeny transfer modules. Protocol and implementation attacks require
the actual parser, scalar multiplication and oracle behavior as inputs;
their rows expose those evidence requirements today.
