// onb131_mul.v - the field multiplier: a digit-serial cyclic convolution.
//
// beta_i * beta_j = beta_{i+j} + beta_{i-j}, so with A the symmetric 263-bit
// expansion of a (index i and index 263-i both carrying coefficient i) the
// product is
//
//     C = sum over j with b_j = 1 of  [ rot(A, j) xor rot(A, -j) ]
//
// taken over j = 1..131 only, because B is symmetric and the two halves of
// the convolution are equal.  That halving is the difference between 263 and
// 131 iterations and it is exact, not an approximation; the model does the
// same sum in the same order so that the two can be compared digit by digit.
//
// DIGIT sets how many j values are folded into one cycle: area grows roughly
// linearly in DIGIT and the latency is ceil(131 / DIGIT) + 2.  DIGIT = 1 is
// the smallest useful core and DIGIT = 131 is a single-cycle multiplier that
// no FPGA will close timing on; the interesting range is 2 to 16.
//
// Handshake: pulse `start` with `a` and `b` valid.  `busy` falls and `done`
// pulses for one cycle when `y` is valid.  A `start` while busy is ignored,
// which is a deliberate choice -- the callers here are FSMs that own the
// multiplier, and silently restarting mid-product would corrupt a result
// nobody would think to check.

`include "onb131_defs.vh"

module onb131_mul #(
    parameter integer DIGIT = 4
) (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                start,
    input  wire [`ONB_M-1:0]   a,
    input  wire [`ONB_M-1:0]   b,
    output reg  [`ONB_M-1:0]   y,
    output reg                 busy,
    output reg                 done
);
    localparam integer N     = `ONB_N;
    localparam integer M     = `ONB_M;
    localparam integer STEPS = (M + DIGIT - 1) / DIGIT;
    localparam integer CW    = (STEPS <= 1) ? 1 : $clog2(STEPS + 1);

    // The symmetric expansion of `a`: free, it is wiring.
    wire [N-1:0] a_sym;
    genvar gi;
    generate
        assign a_sym[0] = 1'b0;                  // beta_0 = 0
        for (gi = 1; gi <= M; gi = gi + 1) begin : expand
            assign a_sym[gi]     = a[gi-1];
            assign a_sym[N - gi] = a[gi-1];
        end
    endgenerate

    reg [N-1:0]  acc;      // the convolution so far
    reg [N-1:0]  apos;     // rot(A, jbase)
    reg [N-1:0]  aneg;     // rot(A, -jbase)
    reg [M-1:0]  breg;     // the remaining digits of b, shifted right
    reg [CW-1:0] cnt;

    // rot_left(v, k) for the DIGIT lanes of this cycle, combinational.
    function automatic [N-1:0] rot_left;
        input [N-1:0] v;
        input integer k;
        integer i;
        begin
            rot_left = {N{1'b0}};
            for (i = 0; i < N; i = i + 1)
                rot_left[(i + k) % N] = v[i];
        end
    endfunction

    // This cycle's contribution: up to DIGIT terms, each the pair of
    // rotations that one coefficient of b selects.
    reg [N-1:0] lane;
    integer k;
    always @* begin
        lane = {N{1'b0}};
        for (k = 0; k < DIGIT; k = k + 1)
            if (breg[k])
                lane = lane ^ rot_left(apos, k) ^ rot_left(aneg, N - k);
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            done <= 1'b0;
            acc  <= {N{1'b0}};
            apos <= {N{1'b0}};
            aneg <= {N{1'b0}};
            breg <= {M{1'b0}};
            cnt  <= {CW{1'b0}};
            y    <= {M{1'b0}};
        end else begin
            done <= 1'b0;
            if (!busy) begin
                if (start) begin
                    // j starts at 1, so the first rotations are +-1.
                    acc  <= {N{1'b0}};
                    apos <= rot_left(a_sym, 1);
                    aneg <= rot_left(a_sym, N - 1);
                    breg <= b;
                    cnt  <= STEPS[CW-1:0];
                    busy <= 1'b1;
                end
            end else begin
                acc  <= acc ^ lane;
                apos <= rot_left(apos, DIGIT);
                aneg <= rot_left(aneg, N - DIGIT);
                breg <= breg >> DIGIT;
                cnt  <= cnt - 1'b1;
                if (cnt == 1) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                    // Fold: the result is symmetric and index 0 is always
                    // zero for symmetric inputs with no index-0 component,
                    // so reading indices 1..131 is the whole reduction.
                    y <= fold_result(acc ^ lane);
                end
            end
        end
    end

    function automatic [M-1:0] fold_result;
        input [N-1:0] c;
        integer i;
        begin
            fold_result = {M{1'b0}};
            for (i = 1; i <= M; i = i + 1) fold_result[i-1] = c[i];
        end
    endfunction

`ifdef ONB131_ASSERT
    // Index 0 of the accumulator must stay zero: if it ever sets, the inputs
    // were not a valid pair of field elements and the fold above would be
    // dropping a real term.
    always @(posedge clk)
        if (rst_n && busy && (acc[0] !== 1'b0))
            $error("onb131_mul: index 0 of the convolution is set");
`endif
endmodule
