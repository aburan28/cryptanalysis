// onb131_inv.v - inversion by Itoh-Tsujii, over the design's one multiplier.
//
//     a^-1 = a^(2^131 - 2) = (a^(2^130 - 1))^2
//
// built along the addition chain 1, 2, 4, 8, 16, 32, 64, 65, 130 from
//
//     a^(2^(m+n) - 1) = (a^(2^m - 1))^(2^n) * a^(2^n - 1).
//
// Eight multiplications and eight Frobenius powers.  The Frobenius powers
// cost nothing (they are permutations) and the multiplications are the whole
// cost, which is why an inversion is about eight times a multiplication and
// why a step of the walk -- one inversion plus two multiplications -- is
// dominated by it.
//
// Each step's second operand is either the accumulator (the doubling steps)
// or `a` itself (the single step from 64 to 65), which is the case split the
// model makes too.  Shared multiplier: this module drives the same
// onb131_mul the step unit uses, through a small arbitration in
// ecc2k130_step, so that a core has exactly one multiplier.

`include "onb131_defs.vh"

module onb131_inv (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                start,
    input  wire [`ONB_M-1:0]   a,
    output reg  [`ONB_M-1:0]   y,
    output reg                 busy,
    output reg                 done,
    output reg                 zero_input,   // a was zero: no inverse exists

    // the shared multiplier
    output reg                 mul_start,
    output reg  [`ONB_M-1:0]   mul_a,
    output reg  [`ONB_M-1:0]   mul_b,
    input  wire [`ONB_M-1:0]   mul_y,
    input  wire                mul_done
);
    localparam integer M = `ONB_M;

    // The eight chain steps: the Frobenius power to apply, and whether the
    // other operand is `a` rather than the accumulator.
    // add = 1, 2, 4, 8, 16, 32, 1, 65
    wire [M-1:0] f1, f2, f4, f8, f16, f32, f65;
    onb131_frob #(.J(1))  u_f1  (.a(acc), .y(f1));
    onb131_frob #(.J(2))  u_f2  (.a(acc), .y(f2));
    onb131_frob #(.J(4))  u_f4  (.a(acc), .y(f4));
    onb131_frob #(.J(8))  u_f8  (.a(acc), .y(f8));
    onb131_frob #(.J(16)) u_f16 (.a(acc), .y(f16));
    onb131_frob #(.J(32)) u_f32 (.a(acc), .y(f32));
    onb131_frob #(.J(65)) u_f65 (.a(acc), .y(f65));

    reg [M-1:0] acc;
    reg [M-1:0] areg;
    reg   [3:0] step;          // 0..7, the chain position
    reg         waiting;

    reg [M-1:0] shifted;
    reg [M-1:0] other;
    always @* begin
        case (step)
            4'd0: begin shifted = f1;  other = acc;  end
            4'd1: begin shifted = f2;  other = acc;  end
            4'd2: begin shifted = f4;  other = acc;  end
            4'd3: begin shifted = f8;  other = acc;  end
            4'd4: begin shifted = f16; other = acc;  end
            4'd5: begin shifted = f32; other = acc;  end
            4'd6: begin shifted = f1;  other = areg; end   // 64 -> 65
            default: begin shifted = f65; other = acc; end // 65 -> 130
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy       <= 1'b0;
            done       <= 1'b0;
            zero_input <= 1'b0;
            mul_start  <= 1'b0;
            step       <= 4'd0;
            waiting    <= 1'b0;
            acc        <= {M{1'b0}};
            areg       <= {M{1'b0}};
            y          <= {M{1'b0}};
        end else begin
            done      <= 1'b0;
            mul_start <= 1'b0;
            if (!busy) begin
                if (start) begin
                    if (a == {M{1'b0}}) begin
                        // Zero has no inverse.  Reporting it is not
                        // defensive programming: in this walk it means the
                        // step hit sigma^j(R) == R, and the core has to
                        // restart rather than divide.
                        zero_input <= 1'b1;
                        y          <= {M{1'b0}};
                        done       <= 1'b1;
                    end else begin
                        zero_input <= 1'b0;
                        acc        <= a;
                        areg       <= a;
                        step       <= 4'd0;
                        busy       <= 1'b1;
                        waiting    <= 1'b0;
                    end
                end
            end else if (!waiting) begin
                mul_a     <= shifted;
                mul_b     <= other;
                mul_start <= 1'b1;
                waiting   <= 1'b1;
            end else if (mul_done) begin
                acc     <= mul_y;
                waiting <= 1'b0;
                if (step == 4'd7) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                    // The last chain value still owes one squaring:
                    // a^-1 = (a^(2^130 - 1))^2.  It is applied to the value
                    // coming back from the multiplier rather than to `acc`,
                    // which has not been written yet this cycle.
                    y <= frob1(mul_y);
                end else begin
                    step <= step + 4'd1;
                end
            end
        end
    end

    // One squaring as a function, for the final step where the accumulator
    // register has not been written yet.
    function automatic [M-1:0] frob1;
        input [M-1:0] v;
        integer i;
        begin
            frob1 = {M{1'b0}};
            for (i = 1; i <= M; i = i + 1)
                if (v[i-1]) frob1[fold_idx(2*i) - 1] = 1'b1;
        end
    endfunction
endmodule
