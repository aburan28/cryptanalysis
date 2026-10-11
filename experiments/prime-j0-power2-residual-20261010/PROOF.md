# Exact terminal-residual scalar reconstruction

Twelve radix-1024 Eisenstein digits followed by one direct residual lookup
reconstruct every certified secp256k1 scalar representative. The quotient
updates are shifts, and the terminal table covers **80,521 exact integer
pairs** with norm below `149²`. A six-unit/tau chain cover needs **10,061
terminal seeds**. With 87,383 seeds in each of the twelve full rows, the
format retains **1,058,657 affine slots** and 72,663,400 bytes under the
declared binary layout.

For `z=(a,b)`, let `N(z)=a²+3ab+3b²`. The nearest representative satisfies
`3N(z0) <= n`, where `n` is the secp256k1 subgroup order. At each of twelve
rows, the full atlas returns `d_i ≡ z_i (mod 1024)` with
`N(d_i) <= 1024²`, so `z_(i+1)=(z_i-d_i)/1024` is integral. Write

`P=1024^12=1329227995784915872903807060280344576`

and

`S=sum_(i=0)^11 1024^(i+1)=1330527338889299954891005307651097600`.

The norm triangle inequality gives

`sqrt(N(z12)) <= (sqrt(n/3)+S)/P < 149`.

The final strict step is the exact integer certificate

`3(149P-S)²-n = 309431403037209215953426872383235547876095686117994391104566500358054592191 > 0`.

The same test with 148 gives

`3(148P-S)²-n = -1254217886552278051303570985876882277533546049325355825160887109918029922625`.

Thus the terminal pair is an integer element of the open norm disk
`N(a,b)<149²`; no final modular recoding is needed. The exact disk has
80,521 pairs and 13,421 six-unit classes. Its largest represented norm is
22,197. A compact row index stores, for each `b` from −172 to 172, the
smallest valid `a`, the contiguous row length, and the code offset. This
indexes each exact pair without a hash probe. The terminal binary has a
20-byte header, 345 eight-byte row records, 80,521 four-byte codes, and
10,061 four-byte signed seed pairs: **365,108 bytes**.

For the full residue atlas, multiplication by tau has determinant three,
coprime to 1024, and permutes the 174,764 six-unit residue classes. Its
cycles have lengths `1,2,4,8,16,32,64,128,256,512`. Every class is
eligible for a seed to cover itself and its tau successor under the
`N(d)<=1024²` bound. Covering each cycle with adjacent pairs uses the
minimum `ceil(L/2)` seeds. Summed over all 513 cycles, this is 87,383
seeds: 87,381 two-class segments and two singletons. The maximum decoded
norm is 1,046,532, below `1024²=1,048,576`.

On the exact terminal disk, tau triples the norm. Its directed action on
nonzero unit classes is injective and cannot cycle, so the classes form
finite chains. Each seed covers its class and, when inside the disk, the
next tau class. A chain of length `L` needs at least `ceil(L/2)` seeds;
pairing adjacent classes attains this bound. The 8,943 chains have length
histogram `1:5957, 2:1993, 3:662, 4:220, 5:73, 6:26, 7:8, 8:3, 10:1`.
Including the identity seed gives 10,061 terminal seeds.

The [generator](build_atlas.py) encodes a seed index, tau exponent, and
six-unit code for every full residue and exact terminal pair. The
[independent verifier](verify_atlas.py) re-enumerates all 1,048,576 full
residues and 80,521 terminal pairs, checks each decoded value, recomputes
the two minimum-cover counts, and checks both binary hashes. The full atlas
is 4,543,844 bytes. Twelve copies of its 87,383 seed points plus 10,061
terminal seed points have a 67,754,048-byte affine payload. Adding the two
atlas binaries and 400 bytes of native metadata gives 72,663,400 bytes.

For row base `G_i=[1024^i]G`, a seed pair `(u,v)` stores
`[u+v lambda_tau]G_i`. The six-unit automorphisms and tau commute with
scalar multiplication, so the decoded code gives `[d_i]G_i`. The terminal
row uses `G_12` and the exact residual pair `z12`. Accumulating all terms
in tau-exponent buckets and returning `B0+tau(B1)` evaluates the original
scalar. A separate affine group replay checks this identity and the
grouped-unit gauge against independent binary multiplication.
