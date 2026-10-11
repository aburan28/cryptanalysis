# A direct 2-adic index removes the orbit rank directory

The six-unit classes of the radix-1024 residue square have a direct
dense index. The [independent orbit check](index-check.json) enumerated
all **1,048,576** residues and verified **174,764** classes: one zero
orbit, one orbit of size three, and 174,762 orbits of size six. Every
computed transform maps its input to the unique class representative.

The resulting [full atlas](atlas-r1024-full-adic-orbit.bin) is
**856,512 bytes**, saving **196,616 bytes** against the prior quotient
atlas. It holds the same 83,051 seeds and the same 174,764 three-byte
codes, in direct-index order. The terminal atlas is byte-identical to
the earlier quotient terminal atlas. The [construction receipt](atlas-receipt.json)
binds the sources and assets.

The [exhaustive atlas replay](atlas-check.json) decoded every full
residue and found **zero differences** from the prior quotient decoder
in seed, tau exponent, unit, or signed digit. The exponent-two residue
count remains 64,674. Native point replay and retained-size
measurement are the next gates; this construction result contains no
CPU wall-time comparison.
