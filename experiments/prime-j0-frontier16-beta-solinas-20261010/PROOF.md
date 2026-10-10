# Three-fold reduction for a fixed cube-root multiplier

Let `B = 2^256`, `c = 2^32 + 977`, and `p = B - c`, the secp256k1 field
prime. The native compact table stores a selected x coordinate in Montgomery
form, `x_M = xB mod p`. The cube-root unit has canonical residue `beta` and
Montgomery residue `beta_M = beta B mod p`. Ordinary Montgomery multiplication
returns `x_M * beta_M * B^-1 = x_M * beta mod p`. The same equality holds for
`beta^2`. The new unit path therefore multiplies the Montgomery x word by the
canonical unit constant using direct reduction modulo `p`.

For canonical inputs `0 <= a,k < p`, write the full product as `ak = L + BH`,
with `0 <= L,H < B`. Since `B = c mod p`, the residue is `L + cH mod p`.
Set `v0 = L + cH`; then `0 <= v0 < (c+1)B`, so its high part `h0` is at most
`c`. One fold replaces `v` by `(v mod B) + c floor(v/B)`.

After the first fold, `v1 < B + c^2`, and `c^2 < B`; therefore its high part
`h1` is either zero or one. After the second fold, `v2 < B + c`. If `v2` still
has a high bit, its low part is below `c`, and the third fold gives
`v3 < 2c < B`. Thus three fixed folds always remove the high part. The result
is in `[0,B)` and is congruent to `ak mod p`; since `p > B/2`, one conditional
subtraction of `p` produces the unique canonical residue.

The implementation uses `U256::mul_wide` for the sixteen 64-by-64 products,
four products by the fixed `c` in the initial fold, and three further fixed
fold products: **23 source-level integer products** for a nontrivial unit.
The generic `U256::mont_mul` source has sixteen product-scan products,
sixteen reduction products, and four low-limb inverse products: **36
source-level integer products**. Compiler instruction selection can change
their machine cost; these counts describe the executed source loops, not a
CPU wall-time ratio.

The reducer has fixed loop bounds and a conditional move for the final
subtraction. The unit selector follows the existing scalar-dependent unit
path. The three canonical constants retain 96 bytes in addition to the
compact table and atlas. The release test compares 65,540 field words under both nontrivial
cube-root powers against Montgomery multiplication, checks 1,024 of them
against independent big-integer modular multiplication, and checks all six
unit images for 1,024 native table points. A separate test replays 4,096
scalars against the preceding compact affine evaluator and independently
checks the first 128 points by binary scalar multiplication.
