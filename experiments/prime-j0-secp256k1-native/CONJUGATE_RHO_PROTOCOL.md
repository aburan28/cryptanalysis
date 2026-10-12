# Simultaneous conjugate degree-seven seed screen

The linked width-four τ atlas needs `A=(2−ω)P` and
`B=ω(2−ω²)P`, plus `2P`. The [Xu et al. τ-method paper](https://eprint.iacr.org/2024/1906)
gives a direct Jacobian formula for `ρP=(2−ω)P`. Apply the same formula
with `β²` for the conjugate. Since `1+β+β²=0`, the second formula's
`β²A` and `β²B` inputs can be formed from the first formula's `βA`
and `βB` by field additions. Rotate only the conjugate result's X
coordinate by `β` to obtain the linked seed `B`.

The frozen design screen implements both direct formulas and the
doubling identity from the same paper. It shares `X³`, `Y²`, `A²`,
`B²`, `βA`, and `βB` between the degree-seven outputs. With the current
field API it computes `Y⁴` separately for doubling. Count the executed
source expressions before screening: common inputs `3M+4S`, two
degree-seven outputs `12M`, the final `ω` rotation `1M`, and doubling
`3M+1S`, totaling **19M+5S = 24 `M+S`** for the three outputs. The
current two-output mixed-add construction plus `2P` costs
`19+7=26 M+S`. Five further seed doublings and nine orbit-image
multiplications would give a proposed full preparation cost of
`5*7+24+9=68 M+S`, versus the existing twin path's 70.

Check the symbolic formula at homogeneous projective scales 1, 2, 3,
and 7 against independent Sage point coordinates already frozen in
the original and earlier linked fixtures. These are **retrospective
correctness controls**. A passing screen proves neither a CPU win nor
academic novelty. Before native promotion, independently audit all
integer-constant field additions and implement the same formula in
Rust, then replay prepared seeds and complete scalar outputs. The
paired CPU interval must include all preparation, scalar reduction,
recoding, evaluation, affine conversion, and answer checking under a
physical-host isolation receipt.

The two direct degree-seven formulas are established in Xu et al.;
shared-input point arithmetic also has prior art. Any novelty claim
would have to isolate the exact multi-output specialization and pass
a wider literature comparison.
