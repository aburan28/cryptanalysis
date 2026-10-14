# Fourteen-window radix-286 axis format

This opt-in fixed-generator secp256k1 candidate uses the same certified
Eisenstein scalar representative, six-unit digit quotient, two terminal
axes, and canonical Karatsuba Solinas field kernel as the merged radix-152
candidate. Fourteen radix-286 ordinary windows replace sixteen radix-152
windows. The exact norm bound makes both terminal coordinates fit the
declared axis tables for every reduced scalar.

The exact search enumerates the finite interval `245..306` and proves the
two tails by monotonic lower bounds. It selects radix 286 uniquely for this
fourteen-window point-entry objective. `screen.py` audits all 81,796
ordinary residues and reconstructs the same frozen 4,096-scalar design
panel as the radix-152 control. The native builder copies all included
sources into a disposable crate and requires every parameter and CLI
anchor exactly once.

Development checks use prior public panels only. Freeze the builder,
verifier, proof sources, and holdout generator in a commit before drawing
a new disjoint 512-scalar panel. The native reference and candidate use
separate release builds. Compare every complete point with both the
radix-152 reference and an independent binary multiplier, preserving
source and output digests. Replay the portable receipt on Linux. Keep
table construction outside an online scalar call, and charge complete
recoding, lookup, point arithmetic, and affine recovery in any later CPU
comparison on a host passing the isolation preflight.
