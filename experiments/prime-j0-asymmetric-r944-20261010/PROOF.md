# Exact radix-944 cover and termination certificate

Thirteen radix-944 windows reconstruct every certified nearest Eisenstein
representative of a secp256k1 scalar. The first twelve rows admit digit norm
at most `944²`; the final row admits norm at most `550²`. The two-bucket tau
atlases use **993,953 affine seed slots**: 74,263 seeds in each full row and
102,797 in the final row. The 64-byte point payload is 63,612,992 bytes;
the two binary atlases add 7,837,344 bytes.

For `z=(a,b)` set `N(z)=a²+3ab+3b²`. The certified scalar representative
has `3N(z0) <= n`, where `n` is the secp256k1 subgroup order. Every atlas
code decodes a digit `d_i` congruent to `z_i` in both coordinates modulo
`R=944`, with `N(d_i) <= D_i²`, where `D_i=944` for `i<12` and `D_12=550`.
Thus `z_(i+1)=(z_i-d_i)/R` is integral. With

`P=R^13=472754776958324375956990884894772035584`

and

`S=sum_i D_i R^i=275941084146884712287907240062833839280`,

the norm triangle inequality gives

`sqrt(N(z_13)) <= (sqrt(n/3)+S)/P < 1`.

The final strict inequality follows from the integer certificate

`3(P-S)²-n = 414799796911014803435708694641699760084903148172378800964234923140356286911 > 0`.

An integral Eisenstein pair with norm below one is zero, so the recoder
terminates after the thirteenth digit. Replacing the final bound 550 by 551
reverses this particular sufficient inequality.

Modulo 944, the six units identify 148,524 residue classes. The degree-three
endomorphism `tau(a,b)=(-3b,a+3b)` has determinant three, coprime to 944,
and therefore permutes these classes. Its quotient action has 829 cycles.
Each seed contributes its unit orbit and, when `3N(seed) <= D²`, the unit
orbit of its tau image. On each cycle, choosing a seed is either a singleton
or a permitted edge to the next class. The minimum seed count is the number
of vertices minus the maximum matching size of this circular edge graph.
The generator uses a circular segment dynamic program; the independent
verifier recomputes the matching count by a separate path recurrence and
checks that both atlases attain it.

The full-row atlas has 74,261 two-class segments and two singletons. Its
largest decoded digit norm is 890,193, below `944²=891,136`. The final
atlas has 45,727 two-class segments and 57,070 singletons. Its largest
decoded norm is 302,484, below `550²=302,500`. The generator and independent
verifier each decode all **891,136 residues per atlas**, checking the exact
congruence, bound, tau exponent and unit image. The binary hashes and exact
cycle histogram are in `atlas-receipt.json` and `independent-check.json`.

For a row base point `G_i=[944^i]G`, a seed pair `(u,v)` stores
`[u+v lambda_tau]G_i`. Applying a six-unit curve automorphism and optionally
tau to this point gives the group element for the decoded digit because the
endomorphisms commute. Accumulating terms in exponent buckets and returning
`B0+tau(B1)` therefore evaluates the reconstructed scalar. The subsequent
independent affine replay checks this group identity on frozen inputs.
