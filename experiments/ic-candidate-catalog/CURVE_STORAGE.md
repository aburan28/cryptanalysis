# IC curve and artifact storage

The compact `IC1...` candidate name is a label for a complete method. It is
not a container for curve properties, point lists, maps, or measurements.
The exact records and their evidence live in the paths below. The
[JSON Schema](curves.schema.json) validates the registry metadata after YAML
parsing. The same `curves.yaml` and `curves.schema.json` bytes are mirrored in
the crypto repository at
`docs/curves/ic/curves.yaml`; cryptanalysis owns the source record and crypto
uses the mirror as a crosswalk to its ICV1 registry.

## Semantic metadata gate

Run `python3 experiments/ic-candidate-catalog/validate_semantics.py` from the
repository root. The `ic-semantic-metadata` CI job runs it for changes to the
registry, graph, archived IC1 candidates/workloads, or factor-base index. It
validates the JSON Schemas, recomputes full curve UIDs and compact EC1/IC1
hashes, checks actual `fb<B>` counts against the archive index, and checks
curve traits, link inventories, graph endpoints, ordered routes and proved
volcano directions. Historical multi-target workload files retain their
original IDs; the separate measurement contract governs new primary runs.

`mirror-lock.json` pins the bytes of `curves.yaml`, `curves.schema.json`,
`curve-links/link.schema.json`, and `scalar-multiplication.schema.json`.
Change it only with a reviewed edit to those files and copy the same files
and lock into crypto's `docs/curves/ic/`. With
both checkouts available, pass `--peer /path/to/crypto` to compare the mirrored
source files and policy guide byte for byte. Crypto CI also checks its mirror against this
repository's `main` branch, including the validator implementation itself.
Keep its negative tests mirrored as well. Merge a source update here before
its mirror PR.

This gate checks metadata integrity and evidence references. It does not
replay a map, prove a point order, certify a factor-base orbit, or measure a
DLP. Those claims still need the corresponding mathematical verifier and
run receipt.

| Object | Authoritative path | Identity and rule |
| --- | --- | --- |
| Exact curve representation | `curves.yaml` | `EC1...` and full `curve_uid` hash only `field` and `curve`. A change of basis, model, subgroup, or generator gets a new identity. |
| Typed representation links | `curve-links/` | Same-field isomorphisms, twists, and base changes are separate link records with map and subgroup proofs; see [typed link rules](curve-links/README.md). Isogeny edges stay in the graph. |
| Curve display name | `crypto/docs/curves/registry.json` | ICV1 slug/full string identifies the registered model. It is a model match, not an EC1 representation match. Keep the exact ICV1 snapshot and status in `curves.yaml`. |
| Isogeny graph | `isogeny_routes.json` | Each exact curve is a node; each directed edge carries degree, direction, source/target, map and certificates. An `IW1...` route has ordered edge IDs. The current degree-263 map lives in `../koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json`. |
| Factor base | `../fb-archive/index.csv`, `../fb-archive/bases/<curve-id>/` | The exact point set or lossless orbit encoding is compressed and content addressed. Large shards live in the archive's object store with hashes in manifests. Never inline a large base in YAML or infer `fb<B>` from a dimension. |
| Candidate and workload | `../ic-bench/candidates/`, `../ic-bench/workloads/` | Immutable method and input manifests. A proposed `Q...` is not an `IC1...` candidate. |
| Scalar multiplication policy | `scalar-multiplication.schema.json` and the candidate's `scalar_multiplication` field | New `/2` candidates declare every scalar role and a proved action reference for endomorphism methods; the exact policy enters the IC1 hash. See [policy rules](SCALAR_MULTIPLICATION.md). |
| Measurement | `../ic-bench/results/` and catalog run receipts | Every run preserves status, stage costs, correctness, resources and paired one-target rho evidence. No measured cost is inferred from a curve or candidate label. |

## Required curve record

For each new exact representation add a small `curves.yaml` entry with its
declared field encoding, exact Weierstrass coefficients, group order and trace
when known, subgroup order and cofactor, encoded generator, and target group.
Check the `EC1` suffix and full UID against sorted-key compact UTF-8 JSON of
`{"field": ..., "curve": ...}`. Keep the mutable annotations outside those
two hash fields: ICV1 crosswalk, endomorphism order conductor, Frobenius order
conductor, prime-specific volcano levels, proof references, and ordered
incoming/outgoing route IDs. Register a newly proved neighbor or twist as its own curve,
even if it shares a j-invariant or lies in the same isogeny class. Keep
unsearched relationships as `not_enumerated` inventories with `scope: null`.

For each tracked optional trait, use `{value: null, status: unknown|unmeasured|
not_evaluated|unproved_in_this_registry|not_applicable}` until evidence
supports a value. `null` means no established value; zero is a measured
number and `L0` is a proved surface. Do not use `?` in machine records.
A status such as `proved` or `derived_from_model` needs a proof/source
reference or an explicit derivation rule. The trait list is extensible;
`curves.yaml` currently tracks ordinary status, j-invariant,
endomorphism discriminant, volcano component and total depth alongside
the exact record's order, trace and subgroup data. The
`endomorphism.actions` inventory tracks verified maps and subgroup eigenvalues
separately from conductor data. Algorithm stages and
their costs belong to candidate/run manifests, not to a curve trait.

## Linking the existing stores

A factor base belongs to an exact `curve_uid`. Resolve an archive row's
`curve_id`, field/curve hash preimage, encoding, generator and subgroup before
adding it to `factor_base_refs`. If the preimages differ, record a proved
field/model/subgroup conversion and transformed point-set digest. An ICV1
slug or the same field degree does not establish a safe link. The existing
N131 factor-base archive uses `EC1N131Ckb1h856fd29cb4b4`, whereas the
degree-263 route's source is `EC1N131Ckb1h136f03e58c98`. Their compact
IDs differ; this registry leaves the link unresolved instead of assigning
the archived base to the route source.

A new isogeny walk must save every intermediate `curve_uid`, ordered edge
ID, map artifact digest, kernel/subgroup/log-transport evidence, degree,
separability and direction proof. Record conductor and `V<ell>L<level>`
per prime only when proved; characteristic-two degree-2 edges have no
ordinary `V2` level. Candidate `ISO1` points to a verified `IW1` route
and charges target-dependent transport in its run. Search-only neighbors
have `curve_id: null` and no `IW1` ID until exact curves and maps exist.

The crypto [factor-base browser](https://aburan28.github.io/crypto/browser/#factor-bases)
currently indexes `FB1` records from committed ecbench sessions. It is a
search view, not the bulk point archive. A browser `FB1` and a cryptanalysis
archive entry are cross-linked only after exact curve identity, point-set
encoding, point digest, folding policy and usable-point count agree. The
browser's generated data must be regenerated through its existing builder
when a verified link is added; do not hand-edit it.

## What remains to verify

This layout stores curve identities, known/unknown traits, large bases,
isogeny edges/routes, and end-to-end run records. It does not itself certify
that every mathematical trait has been found, that the crypto ICV1 registry
can name the general degree-263 codomain model, that the older archive's
N131 EC1 representation is equivalent to the route source, or that any
ISO1 one-target DLP has been measured. Those claims require separate
replay certificates and run receipts.
