// onb131_frob.v - the Frobenius endomorphism, as wiring.
//
// x -> x^(2^J) permutes the basis: beta_i -> beta_{2^J * i mod 263}, folded.
// So a Frobenius power costs no gates at all, only a shuffle of 131 wires.
// That is the property the whole ECC2K-130 attack is built on -- the
// iteration applies sigma^j on every step and it is free -- and it is the
// reason this design carries the field in a normal basis rather than in the
// polynomial basis a general binary-field core would use.
//
// onb131_frob is one fixed power; onb131_frob_j is the iteration's
// run-time-selected power j in [3, 10], which is an eight-way mux of eight
// fixed shuffles.

`include "onb131_defs.vh"

module onb131_frob #(
    parameter integer J = 1
) (
    input  wire [`ONB_M-1:0] a,
    output wire [`ONB_M-1:0] y
);
    genvar i;
    generate
        for (i = 1; i <= `ONB_M; i = i + 1) begin : perm
            assign y[fold_idx(pow2_mod(J) * i) - 1] = a[i-1];
        end
    endgenerate
endmodule
