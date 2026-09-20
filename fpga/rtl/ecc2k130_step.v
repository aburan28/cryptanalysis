// ecc2k130_step.v - one iteration of the ECC2K-130 rho walk.
//
//     j  = ((HW(x) >> 1) & 7) + 3
//     R' = sigma^j(R) + R
//
// with sigma the Frobenius, which is wiring here, so the whole cost of a
// step is the affine addition: one inversion, two multiplications and a
// squaring.  The inversion is eight multiplications, so a step is about
// eleven -- and that ratio is the reason a production core batches the
// inversions of many walks with Montgomery's trick instead of inverting once
// per step.  This module does not; see README.md, which says what that
// costs and what it would take to change.
//
// The exceptional case sigma^j(R) == +-R makes the denominator zero.  It is
// not a corner case to be papered over: dividing anyway would produce a
// point that is not on the curve, and the core would then report it as a
// distinguished point and poison the corpus.  The step raises `exc` and the
// core restarts the walk from a fresh start point.
//
// One multiplier serves both this FSM and the inverter inside it.  They
// never run at the same time, so the arbitration is a mux and not a
// scheduler -- and the mux is written so that the inverter wins, which is
// the state the FSM is in whenever the inverter is busy at all.

`include "onb131_defs.vh"

module ecc2k130_step #(
    parameter integer DIGIT = 4,
    // The distinguished-point cutoff.  A campaign runs at `ONB_DPW (34);
    // simulation relaxes it, because at 34 a point appears about once in
    // 2^25 steps and no testbench is going to wait for that.
    parameter integer DPW   = `ONB_DPW
) (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              start,
    input  wire [`ONB_M-1:0] x_in,
    input  wire [`ONB_M-1:0] y_in,
    output reg  [`ONB_M-1:0] x_out,
    output reg  [`ONB_M-1:0] y_out,
    output reg               dp,      // the new point is distinguished
    output reg               exc,     // sigma^j(R) == +-R; no result
    output reg               busy,
    output reg               done,
    output reg         [2:0] j_out    // the Frobenius power used, for the tb
);
    localparam integer M = `ONB_M;

    // ---- the weight, and the j it selects ---------------------------------
    // A 131-input population count.  Synthesis builds an adder tree; it is
    // small next to the multiplier and it is on the path that decides both
    // the iteration and the distinguished-point test.
    function automatic [7:0] weight;
        input [M-1:0] v;
        integer i;
        begin
            weight = 8'd0;
            for (i = 0; i < M; i = i + 1) weight = weight + {7'd0, v[i]};
        end
    endfunction

    wire [7:0] w_in   = weight(x_in);
    wire [2:0] jsel   = w_in[3:1];            // ((HW >> 1) & 7)
    // The other bits of the weight are deliberately not used here: j depends
    // on bits 3:1 only, and the distinguished-point test uses the weight of
    // the *result*, not of the input.
    wire _unused_w_in = |{w_in[7:4], w_in[0]};
    wire [M-1:0] fx, fy;
    onb131_frob_j u_fx (.a(x_in), .jsel(jsel), .y(fx));
    onb131_frob_j u_fy (.a(y_in), .jsel(jsel), .y(fy));

    // ---- shared multiplier -------------------------------------------------
    reg         fsm_mul_start;
    reg [M-1:0] fsm_mul_a, fsm_mul_b;
    wire        inv_mul_start;
    wire [M-1:0] inv_mul_a, inv_mul_b;
    wire        inv_busy, inv_done, inv_zero;
    wire [M-1:0] inv_y;
    reg         inv_start;
    reg [M-1:0] inv_in;

    wire        mul_start = inv_busy ? inv_mul_start : fsm_mul_start;
    wire [M-1:0] mul_a    = inv_busy ? inv_mul_a     : fsm_mul_a;
    wire [M-1:0] mul_b    = inv_busy ? inv_mul_b     : fsm_mul_b;
    wire [M-1:0] mul_y;
    wire        mul_busy, mul_done;

    onb131_mul #(.DIGIT(DIGIT)) u_mul (
        .clk(clk), .rst_n(rst_n), .start(mul_start), .a(mul_a), .b(mul_b),
        .y(mul_y), .busy(mul_busy), .done(mul_done)
    );

    onb131_inv u_inv (
        .clk(clk), .rst_n(rst_n), .start(inv_start), .a(inv_in), .y(inv_y),
        .busy(inv_busy), .done(inv_done), .zero_input(inv_zero),
        .mul_start(inv_mul_start), .mul_a(inv_mul_a), .mul_b(inv_mul_b),
        .mul_y(mul_y), .mul_done(mul_done)
    );

    // ---- registers ---------------------------------------------------------
    reg [M-1:0] xr, yr, x2r, dyr, lam, x3;

    // lambda^2, a permutation of lam.
    wire [M-1:0] lam_sq;
    onb131_frob #(.J(1)) u_lamsq (.a(lam), .y(lam_sq));

    localparam [2:0] S_IDLE = 3'd0,
                     S_INV  = 3'd1,
                     S_LAM  = 3'd2,
                     S_X3   = 3'd3,
                     S_Y3   = 3'd4;
    reg [2:0] state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            busy          <= 1'b0;
            done          <= 1'b0;
            dp            <= 1'b0;
            exc           <= 1'b0;
            inv_start     <= 1'b0;
            fsm_mul_start <= 1'b0;
            x_out         <= {M{1'b0}};
            y_out         <= {M{1'b0}};
            j_out         <= 3'd0;
        end else begin
            done          <= 1'b0;
            inv_start     <= 1'b0;
            fsm_mul_start <= 1'b0;
            case (state)
                S_IDLE: begin
                    if (start && !busy) begin
                        xr    <= x_in;
                        yr    <= y_in;
                        x2r   <= fx;
                        dyr   <= y_in ^ fy;
                        j_out <= jsel;
                        exc   <= 1'b0;
                        dp    <= 1'b0;
                        busy  <= 1'b1;
                        if ((x_in ^ fx) == {M{1'b0}}) begin
                            // sigma^j(R) == +-R.  Report it; the caller
                            // restarts.  Note that on this curve -(x, y) =
                            // (x, x+y), so equal x is exactly the condition.
                            exc   <= 1'b1;
                            busy  <= 1'b0;
                            done  <= 1'b1;
                        end else begin
                            inv_in    <= x_in ^ fx;
                            inv_start <= 1'b1;
                            state     <= S_INV;
                        end
                    end
                end
                S_INV: begin
                    if (inv_done) begin
                        if (inv_zero) begin
                            // Cannot happen: the denominator was checked
                            // above.  If it ever does, stop rather than
                            // emit a point from a division that did not
                            // happen.
                            exc   <= 1'b1;
                            busy  <= 1'b0;
                            done  <= 1'b1;
                            state <= S_IDLE;
                        end else begin
                            fsm_mul_a     <= dyr;
                            fsm_mul_b     <= inv_y;
                            fsm_mul_start <= 1'b1;
                            state         <= S_LAM;
                        end
                    end
                end
                S_LAM: begin
                    if (mul_done) begin
                        lam   <= mul_y;
                        state <= S_X3;
                    end
                end
                S_X3: begin
                    // x3 = lambda^2 + lambda + x1 + x2   (a = 0 on this curve)
                    // lam_sq is combinational on the lam register, written
                    // last cycle, so it is valid here.
                    x3            <= lam_sq ^ lam ^ xr ^ x2r;
                    fsm_mul_a     <= lam;
                    fsm_mul_b     <= xr ^ (lam_sq ^ lam ^ xr ^ x2r);
                    fsm_mul_start <= 1'b1;
                    state         <= S_Y3;
                end
                S_Y3: begin
                    // y3 = lambda*(x1 + x3) + x3 + y1
                    if (mul_done) begin
                        x_out <= x3;
                        y_out <= mul_y ^ x3 ^ yr;
                        dp    <= (weight(x3) <= DPW[7:0]);
                        busy  <= 1'b0;
                        done  <= 1'b1;
                        state <= S_IDLE;
                    end
                end
                default: state <= S_IDLE;
            endcase
        end
    end

    // mul_busy is not used for arbitration: the inverter and this FSM never
    // hold the multiplier at the same time, which is what makes the mux
    // above sufficient.  Kept connected so a waveform shows it.
    wire _unused_mul_busy = mul_busy;
endmodule
