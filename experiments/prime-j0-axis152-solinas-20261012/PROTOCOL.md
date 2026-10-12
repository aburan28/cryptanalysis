# Canonical Karatsuba Solinas arithmetic for the radix-152 format

The candidate keeps the radix-152 representative, recoder, orbit atlas,
window count, selected group points, and terminal axes from the merged
axis-152 XYZZ evaluator. It changes the table coordinates from Montgomery
to canonical field residues and evaluates the selected point sum with the
existing `U256XYZZCanonical<true>` Karatsuba Solinas kernel.

The builder copies the merged sources to a disposable native crate and
requires each transformation anchor exactly once. The reference and
candidate use separate release target directories. Development checks may
use the existing public scalar panels. Freeze this builder, verifier, and
protocol in a commit before generating a new disjoint scalar panel. Then
compare every output point with both the reference and an independent
binary scalar multiplication, retaining source, binary, input, and output
digests. A second panel will be drawn after the portable receipt is frozen
if the first exposes a verifier error.

The ordinary-path source model charges ten field products or squares per
noninitial XYZZ mixed addition and one product per nonzero unit rotation.
The canonical Karatsuba kernel uses nine variable 64-bit products plus
seven constant-fold products per general field product; the Montgomery
kernel uses 36 variable 64-bit products per product. These are source
operation counts, not CPU timings. The complete online path also includes
recoding, lookup, exceptional branches, final inversion, and verification.
Promote a CPU wall-time comparison only after a paired isolated-host run.

The mathematical scalar reconstruction and point-table reachability are
the checked results mapped in `../prime-j0-axis152-20261012/PROOF.md`.
The canonical field reduction and Karatsuba product identities are mapped
in `../prime-j0-u14-solinas-20261012/PROOF.md` and
`../prime-j0-u14-karatsuba-20261012/PROOF.md`. This experiment applies
those existing identities to the same selected secp256k1 points.
