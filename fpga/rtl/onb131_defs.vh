// onb131_defs.vh - the field's shape, and the index arithmetic every
// permutation in this design is built from.
//
// F_{2^131} in a type-II optimal normal basis: an element is 131 bits, where
// bit i-1 carries the coefficient of beta_i = gamma^i + gamma^-i and gamma is
// a primitive 263rd root of unity.  Two facts do all the work:
//
//   beta_i * beta_j = beta_{i+j} + beta_{i-j}      (a cyclic convolution)
//   beta_i^2        = beta_{2i mod 263}            (a permutation: wiring)
//
// with indices folded by beta_{263-k} = beta_k and beta_0 = 0.  The folding
// is why fold_idx exists and why every module here indexes from 1.
//
// Both facts are checked against an independent construction of the field in
// ../model; the testbenches compare this RTL against that model value by
// value, so a change to these constants that breaks the field shows up as a
// mismatch rather than as a subtly wrong campaign.

`ifndef ONB131_DEFS_VH
`define ONB131_DEFS_VH

`define ONB_M    131   // field degree, and the number of basis elements
`define ONB_N    263   // 2m+1: the order of gamma, and the convolution length
`define ONB_DPW   34   // a point is distinguished when HW(x) <= this
`define ONB_JMIN   3   // the iteration's Frobenius power lives in [3, 10]
`define ONB_JCNT   8

// fold_idx(k): the basis index that gamma^k + gamma^-k belongs to.
// Returns 0 for k = 0 mod 263, where beta_0 = 0 -- callers must handle that,
// and in this design they never hit it because index 0 never carries a
// coefficient.
function automatic integer fold_idx;
    input integer k;
    integer r;
    begin
        r = k % `ONB_N;
        if (r < 0) r = r + `ONB_N;
        fold_idx = (r > `ONB_M) ? (`ONB_N - r) : r;
    end
endfunction

// pow2_mod(j): 2^j mod 263, the index multiplier of the j-th Frobenius power.
function automatic integer pow2_mod;
    input integer j;
    integer i, r;
    begin
        r = 1;
        for (i = 0; i < j; i = i + 1) r = (r * 2) % `ONB_N;
        pow2_mod = r;
    end
endfunction

`endif
