# Names for isogenous curves and volcano positions

The immutable `EC1...h<digest>` curve ID in [AGENTS.md](../../AGENTS.md)
identifies the exact field representation, curve model, and DLP subgroup. Do
not put a volcano level or a relative move into that ID: a curve can be reached
by several routes, and a level assertion can change when new evidence arrives.
Use a **position alias** and an **isogeny-walk ID** alongside the curve ID.

## Position alias

For a proved ordinary `ell`-isogeny volcano with `ell` different from the
field characteristic, append `V<ell>L<level>` to the exact curve ID in displays:

`<curve-id>V3L2`

Here `V3` specifies the 3-isogeny graph, and `L2` means level two below its
surface (`L0`). Levels are absolute within that prime's volcano, not relative
to the curve where a search started. Equivalently, the level is
`v_ell(f_End(E))`, the valuation of the **endomorphism-order** conductor in the
maximal order. The conductor of `Z[pi]` is a different number. When several
prime-specific positions are proved, list their segments in increasing prime
order, for example `<curve-id>V3L2V5L1`. The bare curve ID remains the
canonical identity; the alias is a certified annotation. If a level is unknown,
store JSON `null` and omit its `V...L...` segment. Never write `L0` to mean
"unknown." The component, total depth, and conductor may also be unknown.

Two siblings can both have `V3L2`; their different exact curve IDs distinguish
them. A `j`-invariant or level alone does not identify an exact model, twist,
field encoding, generator, or subgroup. Record the Frobenius trace and a
component reference when proved, because one isogeny class can contain several
volcano components.

## Ordered isogeny walk

Name a verified route `IW1E<ell><direction><count>...h<12hex>`. `IW` and `E`
are structural tags; direction values are lowercase:

| Segment | Meaning | Required level change per edge |
| --- | --- | --- |
| `E3d1` | one degree-3 descending edge | `+1` |
| `E3u1` | one degree-3 ascending edge | `-1` |
| `E3h1` | one degree-3 horizontal edge | `0` |
| `E3x1` | one degree-3 edge with direction unresolved | none asserted |
| `E2p1` | one characteristic-prime degree-2 edge over `F_(2^n)` | no volcano level asserted |

For example, `IW1E3d2E3u1h<digest>` describes two descents then an ascent
in a 3-volcano. The digest is the first 12 lowercase hex digits of SHA-256 over
the canonical ordered route record, extended on collision. Include exact
source and target curve IDs, every intermediate curve ID, every edge ID,
degree, direction, separability, explicit map and dual-map references when
available, kernel proof, and subgroup/log transport certificate in that
record. A repeated segment count is merely compact display syntax: retain
every ordered edge in the record. The existing candidate tag `ISO1` still
means "uses a specified route"; it does not encode direction or identify the
route. Store its `IW1...` ID in the candidate manifest.

A verified `d` edge must increase the certified level by one; `u` must lower
it by one; `h` must preserve it. Classify direction from endomorphism orders
or another accepted proof, not solely from neighboring `j` values. A path may
move down, sideways, and up; net depth never substitutes for its ordered
edges. Search-only paths may describe intended degrees, but have no `IW1`
verified-route ID until their endpoints, maps, and transport are established.

## Applicability to ECC2K-130

ECC2K-130 is over characteristic two. Ordinary `ell`-volcano labels here
require `ell != 2`. The catalog's proposed degree-2 search can remain an
isogeny search, but a degree-2 edge receives `p` and **no** `V2L...` or
up/down/horizontal claim. It must record separability separately; `p` only
states that the degree equals the field characteristic. The degree-3 search
could receive `V3L...` and `d`/`u`/`h` labels after the source and codomain
levels and explicit maps are verified. Neither search currently has those
proofs, so no actual position alias or verified walk ID is issued.

The mathematical level and direction convention follows Andrew Sutherland's
[Isogeny volcanoes](https://msp.org/obs/2013/1-1/obs-v1-n1-p25-s.pdf),
Definition 1 and Sections 2.7, 2.11–2.12. Its ordinary volcano graph is
defined for prime degree different from the field characteristic.
