# A fixed-memory doubled-orbit scalar cover

The radix-1024 secp256k1 cover gains a **norm-four doubling image** of its
existing seeds. It retains **67,338 seeds** and the same **968,428-byte
class cover** as the compressed parent. Doubling supplies **1,416** classes
previously assigned to the norm-seven map, reducing those assignments from
**6,094 to 4,678**. The [constructor](construct.py) and
[independent verifier](verify.py) bind the cover SHA-256
`fca12339ee85d55f155f08e80abd671063e7745d487533e34e1d0e511f5de7c2`.
The verifier checked the selected minimum-norm doubling provider for each
changed class and all **1,048,576 residues**.

## Representation and branch choice

A seed `(a,b)` now offers `(2a,2b)` when its norm-four image satisfies
`N(2a,2b) <= 1024^2`. Unit rotation commutes with doubling, so the same
six-unit quotient and stored seed point support the new map. Map code `4`
is carried in the existing four-bit class-code field. The original maps
`0,1,2,3` retain their exact assignments elsewhere.

The proposed scalar path first recodes with the doubled cover. If that path
activates both the doubling and norm-seven buckets, it uses the original
compressed-cover path for that scalar. This avoids adding a fifth active
bucket alongside norm-seven. The [inherited-panel screen](design-screen.json)
is a design diagnostic: 281 of 4,096 paths replace an active norm-seven
bucket with doubling alone, while 110 activate both under the static
doubled cover and select the parent path under the adaptive rule.

In the direct XYZZ source-call model, an ordinary nonidentity doubling uses
`6M+3S`, while direct norm-seven uses `9M+5S+2C`, where `M` is a general
field multiplication, `S` a square, and `C` a fixed-constant product. The
adaptive choice also incurs recoding work; the fresh panel and native replay
are needed to account for its exact operation path. CPU wall-time comparisons
require the host-isolation gate in `docs/ISOLATED_BENCHMARKS.md`.

## Fresh scalar panel

The [fresh-panel protocol](holdout.py) froze the construction and verifier
sources in commit `bd810e31095618988d9b528862a560f5358f0750` before
drawing **4,096** new scalars. The [input receipt](holdout-inputs.json)
checks modular disjointness from the listed prior panels. The
[independent path verifier](verify_holdout.py) reconstructed every scalar,
checked each selected digit and atlas assignment, and compared the first
**128** point sums with independent binary multiplication. Its
[receipt](holdout-check.json) passed and binds the frozen input, path, cover,
source, and point-output hashes.

| Paired fresh panel | Active norm-seven paths | Norm-seven digits | Active doubling paths | Doubling digits | Full-window terms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Compressed parent | 1,411 | 1,687 | 0 | 0 | 49,152 |
| Static doubled cover | 1,110 | 1,296 | 381 | 395 | 49,152 |
| Adaptive doubled cover | **1,110** | **1,372** | **301** | **313** | 49,152 |

The adaptive policy selected the parent path in **80** mixed cases. It
replaced an active norm-seven bucket with doubling alone in **301** cases
on the fresh panel, with no scalar activating both branches under that
policy. These are exact recoding and correctness counts. Native replay will
check the implementation's bucket combination and retained-memory receipt;
controlled wall-time evidence will price the extra recoding work.
