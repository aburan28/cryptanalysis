// onb131_frob_j.v - the iteration's run-time Frobenius power.
//
// j lives in [ONB_JMIN, ONB_JMIN + ONB_JCNT - 1], so this is an eight-way mux
// over eight fixed shuffles of 131 wires.  Still no gates worth counting: the
// Frobenius is free in a normal basis, and that is the whole reason the
// ECC2K-130 iteration is built around it.

`include "onb131_defs.vh"

// The iteration's sigma^j, j in [ONB_JMIN, ONB_JMIN + ONB_JCNT - 1].
module onb131_frob_j (
    input  wire [`ONB_M-1:0] a,
    input  wire        [2:0] jsel,   // j = jsel + ONB_JMIN
    output reg  [`ONB_M-1:0] y
);
    wire [`ONB_M-1:0] fj [0:`ONB_JCNT-1];

    genvar k;
    generate
        for (k = 0; k < `ONB_JCNT; k = k + 1) begin : powers
            onb131_frob #(.J(`ONB_JMIN + k)) u (.a(a), .y(fj[k]));
        end
    endgenerate

    integer s;
    always @* begin
        y = fj[0];
        for (s = 0; s < `ONB_JCNT; s = s + 1)
            if (jsel == s[2:0]) y = fj[s];
    end
endmodule
