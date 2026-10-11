# Typed links between exact curve representations

A curve node is its exact `EC1`/full UID. Keep the field representation,
Weierstrass model, subgroup, and generator in the curve's hashed `field` and
`curve` records. Keep relationships outside that hash: a new proof about a
neighbor must not rename either endpoint. `ICV1` is a model display identity;
shared degree, order, or j-invariant does not establish a link.

The mirrored `curves.yaml` gives each node three relationship inventories:
`same_field_isomorphisms`, `twists`, and `base_changes`. An empty
`links: []` with `status: not_enumerated` means no search or complete
enumeration is claimed. `scope: null` means the search scope is not fixed.
A `complete_for_declared_scope` inventory must name its scope. Do not turn
an empty list into evidence that no neighbor exists.

| Kind | Evidence needed before a verified link | DLP use |
| --- | --- | --- |
| Same-field model or basis isomorphism | Exact field/coordinate maps and inverses over the base field, endpoint UIDs, and independent point replay | Map `G` and `Q`; if the destination uses another generator, verify its scalar relation before reusing logs. |
| Twist | Exact twist model and parameter/class, extension field and embedding, explicit isomorphism over that extension, endpoint UIDs, order/trace and subgroup checks | A twist is generally not an isomorphism of the two base-field point groups. Do not use it as an `ISO1` DLP route. |
| Base change | Exact field extension and embedding, changed curve record, point map, subgroup/order checks | The extension-field curve gets a new UID. Account for conversion and target-dependent transport if used. |
| Isogeny | Use `isogeny_routes.json`: source/target UIDs, degree, separability, kernel, forward and dual maps or explicit dual status, ordered edge IDs, and subgroup/log transport proof | Only a verified, transportable `IW1` route may enter `ISO1`. Record every intermediate curve and charge the route. |
| Endomorphism action | Exact self-map, subgroup eigenvalue or action, orbit rule, and replay | Keep the action and folding proof in the factor-base/candidate manifest; it is not a new curve node. |

When a non-isogeny link is actually constructed, validate it against
[link.schema.json](link.schema.json) and store one small
`curve-links/<full-link-sha256>.json` manifest. Hash sorted-key compact
UTF-8 JSON of its exact mathematical record, excluding the link ID,
paths, timestamps, and measurements. At minimum retain `kind`, exact
endpoint UIDs, field of definition, map/embedding artifact and digest,
inverse or dual status, verification status and proof references,
subgroup/generator transport, and any scalar conversion. Keep run costs
in a run receipt. Proposed links retain `target_curve_uid: null` and
`status: proposed`; they are not verified transport. The crypto repo
mirrors only small manifests and references bulky proofs in cryptanalysis.
For schema version 1, the filename digest input is exactly
`{schema_version,kind,source_curve_uid,target_curve_uid,map_sha256,details}`.
`details` contains `generator_relation` for a same-field isomorphism,
`twist_kind`, `twist_parameter`, and `extension_degree` for a twist, or
`extension_degree` for a base change. The metadata validator recomputes this
digest and requires both endpoint inventories to list the manifest. Proof
status, artifact paths and run costs stay outside that identity.

A twist can share a j-invariant with its source while having a different
trace, group order and usable DLP subgroup. In characteristic two, a
quadratic twist's isomorphism may require adjoining a root of
`u^2 + u + D`. This extension map does not by itself carry arbitrary
`E(F_q)` points to rational points of the twist over `F_q`. A twist
therefore gets its own exact curve record only after its field, model,
order, subgroup and generator are fixed. Until then the inventory stays
`not_enumerated` with no invented `EC1` or `ICV1` name.

For an isogeny volcano, record prime-specific level and edge direction
only when proved. An upward edge, downward edge, horizontal edge, a
characteristic-prime edge, and a twist are different relationship types.
The existing degree-263 ECC2K-130 route remains in
`isogeny_routes.json`; no duplicate isogeny identity is issued here.

The twist definition and characteristic-two construction follow
[Sage's elliptic-curve documentation](https://doc.sagemath.org/html/en/reference/arithmetic_curves/sage/schemes/elliptic_curves/ell_field.html);
the level/direction terminology follows
[Sutherland's isogeny-volcano treatment](https://msp.org/obs/2013/1-1/obs-v1-n1-p25-s.pdf).
