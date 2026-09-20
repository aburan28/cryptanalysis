// ecc2k130_core.v - one walker: a point, a step unit, and a way out for the
// distinguished points it finds.
//
// The core holds the walk state and nothing else.  It does not know the
// campaign, it does not track the exponents (a, b), and it cannot solve
// anything -- a collision is resolved by replaying two walks from their
// seeds on a host, which is the trade every ECC2K-130 implementation makes:
// carrying the exponents would double the state and the output bandwidth for
// something that is needed once per campaign.
//
// Three behaviours are worth stating because they are what makes a fleet of
// these usable:
//
//   * **Back-pressure stops the walk.**  If the collector cannot take a
//     distinguished point, the core stops rather than dropping it.  A
//     dropped point is a walk that was paid for and lost, and nothing
//     downstream could ever detect it.
//   * **The exceptional case stops the walk too.**  sigma^j(R) == +-R has no
//     ordinary sum; the core raises `exc` and waits for the host to load a
//     new start point.  It does not invent one: the host's choice of start
//     points is what makes a unit reproducible.
//   * **Counters are free and answer the only question an operator has.**
//     steps, points and exceptions, 64 bits each, so "is this board working
//     and how fast" is a register read and not an inference from the output
//     rate.  `points` counts points *produced*: a point that has been latched
//     into the output register is already counted even though the collector
//     has not taken it yet, so a host that compares the counter against what
//     it has received must drain the stream first.

`include "onb131_defs.vh"

module ecc2k130_core #(
    parameter integer DIGIT = 4,
    parameter integer DPW   = `ONB_DPW
) (
    input  wire              clk,
    input  wire              rst_n,

    // Loading a start point.  `load` takes effect immediately and overrides
    // whatever the core was doing, which is how a host recovers a core that
    // has stopped on an exception.
    input  wire              load,
    input  wire [`ONB_M-1:0] load_x,
    input  wire [`ONB_M-1:0] load_y,
    input  wire       [63:0] load_seed,

    input  wire              run,      // hold high to walk

    // Distinguished points out, with back-pressure.
    output reg               dp_valid,
    input  wire              dp_ready,
    output reg  [`ONB_M-1:0] dp_x,
    output reg        [63:0] dp_seed,

    // Status
    output wire              loaded,
    output wire              exc,
    output wire [`ONB_M-1:0] pt_x,
    output wire [`ONB_M-1:0] pt_y,
    output reg               step_done,   // one pulse per completed step
    output reg        [63:0] steps,
    output reg        [63:0] points,
    output reg        [63:0] exceptions
);
    localparam integer M = `ONB_M;

    reg [M-1:0] x, y;
    reg [63:0]  seed;
    reg         have_point;
    reg         stopped;      // an exception is pending; waiting for a load

    wire [M-1:0] sx, sy;
    wire         s_dp, s_exc, s_busy, s_done;
    wire   [2:0] s_j;
    reg          s_start;

    ecc2k130_step #(.DIGIT(DIGIT), .DPW(DPW)) u_step (
        .clk(clk), .rst_n(rst_n), .start(s_start), .x_in(x), .y_in(y),
        .x_out(sx), .y_out(sy), .dp(s_dp), .exc(s_exc),
        .busy(s_busy), .done(s_done), .j_out(s_j)
    );

    assign loaded = have_point;
    assign exc    = stopped;
    assign pt_x   = x;
    assign pt_y   = y;

    // The core may issue a step when it has a point, is running, is not
    // stopped on an exception, and is not holding a point the collector has
    // not taken yet.
    wire can_step = have_point && run && !stopped && !s_busy && !s_start && !dp_valid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            x          <= {M{1'b0}};
            y          <= {M{1'b0}};
            seed       <= 64'd0;
            have_point <= 1'b0;
            stopped    <= 1'b0;
            s_start    <= 1'b0;
            dp_valid   <= 1'b0;
            dp_x       <= {M{1'b0}};
            dp_seed    <= 64'd0;
            step_done  <= 1'b0;
            steps      <= 64'd0;
            points     <= 64'd0;
            exceptions <= 64'd0;
        end else begin
            s_start   <= 1'b0;
            step_done <= 1'b0;

            if (dp_valid && dp_ready) dp_valid <= 1'b0;

            if (load) begin
                x          <= load_x;
                y          <= load_y;
                seed       <= load_seed;
                have_point <= 1'b1;
                stopped    <= 1'b0;
            end else if (s_done) begin
                steps     <= steps + 64'd1;
                step_done <= 1'b1;
                if (s_exc) begin
                    // No ordinary sum exists.  Stop and say so; the host
                    // loads a new start.
                    stopped    <= 1'b1;
                    exceptions <= exceptions + 64'd1;
                end else begin
                    x <= sx;
                    y <= sy;
                    if (s_dp) begin
                        dp_x     <= sx;
                        dp_seed  <= seed;
                        dp_valid <= 1'b1;
                        points   <= points + 64'd1;
                    end
                end
            end else if (can_step) begin
                s_start <= 1'b1;
            end
        end
    end

    wire _unused_j = |s_j;
endmodule
