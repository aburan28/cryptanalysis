# `ca-curve-audit`: evidence-graded curve screening

`ca-curve-audit` is the big-integer curve-assessment binary in the
`cryptanalysis` Rust workspace. It accepts an exact JSON curve record and
emits one JSON row for each of the 61 versioned WeakCurves criteria. A row
states the observed condition, its evidence, and the next witness required
to advance the assessment. The catalog and its source revision are embedded
in the executable, and each report includes the compiled auditor source
digest, so a result remains tied to the rules and arithmetic that produced it.

Build and run from the repository root:

```sh
cargo build --locked --manifest-path bindings/rust/Cargo.toml -p ca-curve-audit
bindings/rust/target/debug/ca-curve-audit catalog > criteria.json
bindings/rust/target/debug/ca-curve-audit audit \
  --input bindings/rust/curve-audit/examples/nist-p192.json \
  --prime-certificates bindings/rust/curve-audit/examples/nist-p192-pratt.json \
  --max-k 6 > p192-audit.json
```

The [P-192 input](examples/nist-p192.json) reproduces the parameters in
[NIST FIPS 186-4, Appendix D.1.2.1](https://nvlpubs.nist.gov/nistpubs/fips/nist.fips.186-4.pdf)
and demonstrates the 192-bit path. The checked-in
[recursive prime certificates](examples/nist-p192-pratt.json) bind to the
input's exact SHA-256 digest. Generate equivalent certificates through the
repository's checked Sage launcher:

```sh
./sage -python bindings/rust/curve-audit/tools/generate_pratt.py \
  --input bindings/rust/curve-audit/examples/nist-p192.json \
  --output bindings/rust/curve-audit/examples/nist-p192-pratt.json
```

The Rust auditor verifies these certificates without Sage. Each large-prime
node checks the complete factorization of `n-1`, recursively proved prime
factors, and a Lucas witness of order `n-1`; factors at most `10^12` use
exact trial division. A supplied certificate with the wrong input hash or
an invalid witness stops the audit with an error.
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
1,000,000). For larger prime fields, it can certify a supplied order `N`
using the prime certificates, a checked nonidentity point `G` with
`[r]G=O`, `r | N`, `|N-(p+1)|² ≤ 4p`, and `r² > 16p`. Since `r` is prime,
`G` has exact order `r`. Lagrange's theorem makes the true curve order a
multiple of `r`; Hasse's interval has width `4√p < r`, so `N` is its unique
multiple of `r`. The resulting status is
`hasse_unique_multiple_certificate`. This route certifies the checked-in
P-192 order and yields its trace, quadratic-twist order, and downstream
arithmetic checks. Without a certificate, a larger prime receives the
fixed-base probable-prime screen and any supplied order remains
`supplied_unverified`. The default embedding-degree bound is 32, with a maximum
of 256. A missing degree within the bound is reported as
`not_found_within_bound`, not as an all-degree result.

The [Lean theorem](formal/HasseUnique.lean) proves the interval uniqueness
step for arbitrary natural-number multiples and an interval width less than
`r`. Its exact hypotheses are `n=k*r`, `m=l*r`, `n≤m+width`,
`m≤n+width`, and `width<r`; it concludes `n=m`. The proof map is therefore
**partial** for the full elliptic-curve theorem: the Lucas primality
criterion, the elliptic group law, Lagrange divisibility, Hasse's bound,
and the conversion of the squared inequalities into interval bounds remain
outside this Lean module. The Rust certificate verifier checks the concrete
P-192 arithmetic, and an independent checked-Sage point count confirms its
order and trace. The pinned Lean toolchain and build/axiom output are in
[`formal/`](formal/). `lean4checker --fresh` was unavailable on this host.

Independent replay command (run through the repository launcher):

```sh
./sage -python -c 'import json; from sage.all import GF, EllipticCurve, Integer; x=json.load(open("bindings/rust/curve-audit/examples/nist-p192.json")); p=Integer(x["field"]["characteristic"]); a=Integer(x["curve"]["a"]); b=Integer(x["curve"]["b"]); r=Integer(x["subgroup"]["order"]); E=EllipticCurve(GF(p),[a,b]); G=E(Integer(x["subgroup"]["generator"]["x"]),Integer(x["subgroup"]["generator"]["y"])); N=E.cardinality(); print(json.dumps({"p_prime":bool(p.is_prime(proof=True)),"r_prime":bool(r.is_prime(proof=True)),"curve_order":str(N),"generator_order":str(G.order()),"trace":str(p+1-N),"twist_order":str(2*p+2-N),"matches_claim":bool(N==Integer(x["curve_order"]))}))'
```

It returned `curve_order = generator_order =
6277101735386680763835789423176059013767194773182842284081`,
`trace = 31607402316713927207482677199`, and
`twist_order = 6277101735386680763835789423239273818400622627597807638479`.
The [replay receipt](examples/nist-p192-sage-replay.json) retains these
values, the exact input and certificate digests, and the checked Sage
runtime manifest digest. The [complete audit report](examples/nist-p192-audit.json)
is the current 61-criterion result for this input and certificate.

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

The next backend should extend the certified-order path to independently
sampled 192–252-bit controls, then add extension-field arithmetic and
cover/isogeny transfer modules. Protocol and implementation attacks require
the actual parser, scalar multiplication and oracle behavior as inputs;
their rows expose those evidence requirements today. The exact acceptance
criteria and next control are tracked in the [large-field audit problem](../../../problems/curve-audit-large-field-certificates-and-extension-transfer.md).
