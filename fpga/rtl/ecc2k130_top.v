// ecc2k130_top.v - N walkers, one register file, one stream of points.
//
// This is the boundary between the part of the design that is about the
// attack and the part that is about a particular board.  Everything above
// the register port and the point stream is vendor-neutral RTL that any
// FPGA toolchain can take; below them sits whatever the platform provides --
// AXI4-Lite and AXI4-Stream on a Zynq or an Alveo shell, a PCIe DMA engine,
// or a UART on a small board.  Nothing here knows which, which is why the
// core can be simulated end to end without a vendor library.
//
// The collector is round robin, and it is round robin for a reason rather
// than for fairness: with a fixed priority, a core near the top of the list
// that produced points quickly would starve the rest, and a starved core
// stops walking (its own back-pressure stops it) -- so an arbiter that
// "favours the fast core" would silently reduce the fleet to one walker.
//
// Register map (32-bit words; every register reads back what it holds):
//
//   0x00  CTRL      bit0 run (all cores), bit1 clear counters
//   0x04  CORES     read-only: the number of cores in this build
//   0x08  STATUS    bit0 any core stopped on an exception, bit1 all loaded
//   0x0C  SELECT    which core the load window below addresses
//   0x10  LOADED    bitmap: cores that hold a point
//   0x14  STOPPED   bitmap: cores stopped on an exception
//   0x20..0x30      LOAD_X[0..4]   131 bits, little-endian words
//   0x34..0x44      LOAD_Y[0..4]
//   0x48, 0x4C      LOAD_SEED lo, hi
//   0x50  LOAD_GO   write 1 to hand the window to the selected core
//   0x60, 0x64      STEPS lo, hi     of the selected core
//   0x68, 0x6C      POINTS lo, hi
//   0x70, 0x74      EXCEPTIONS lo, hi

`include "onb131_defs.vh"

module ecc2k130_top #(
    parameter integer CORES = 4,
    parameter integer DIGIT = 4,
    parameter integer DPW   = `ONB_DPW
) (
    input  wire              clk,
    input  wire              rst_n,

    // register port
    input  wire        [7:0] reg_addr,
    input  wire       [31:0] reg_wdata,
    input  wire              reg_we,
    input  wire              reg_re,
    output reg        [31:0] reg_rdata,

    // distinguished points out
    output wire              dp_valid,
    input  wire              dp_ready,
    output wire [`ONB_M-1:0] dp_x,
    output wire       [63:0] dp_seed,
    output wire        [7:0] dp_core
);
    localparam integer M  = `ONB_M;
    localparam integer SW = (CORES <= 1) ? 1 : $clog2(CORES);

    reg          run;
    reg  [31:0]  load_x_w [0:4];
    reg  [31:0]  load_y_w [0:4];
    reg  [63:0]  load_seed;
    reg  [SW-1:0] sel;
    reg  [CORES-1:0] load_pulse;

    wire [M-1:0] load_x = {load_x_w[4][M-129:0], load_x_w[3], load_x_w[2],
                           load_x_w[1], load_x_w[0]};
    wire [M-1:0] load_y = {load_y_w[4][M-129:0], load_y_w[3], load_y_w[2],
                           load_y_w[1], load_y_w[0]};

    wire [CORES-1:0] c_dp_valid, c_loaded, c_exc, c_step;
    wire [M-1:0]     c_dp_x   [0:CORES-1];
    wire [63:0]      c_dp_seed[0:CORES-1];
    wire [63:0]      c_steps  [0:CORES-1];
    wire [63:0]      c_points [0:CORES-1];
    wire [63:0]      c_exceptions[0:CORES-1];
    wire [M-1:0]     c_pt_x   [0:CORES-1];
    wire [M-1:0]     c_pt_y   [0:CORES-1];
    reg  [CORES-1:0] c_dp_ready;

    genvar g;
    generate
        for (g = 0; g < CORES; g = g + 1) begin : cores
            ecc2k130_core #(.DIGIT(DIGIT), .DPW(DPW)) u_core (
                .clk(clk), .rst_n(rst_n),
                .load(load_pulse[g]), .load_x(load_x), .load_y(load_y),
                .load_seed(load_seed),
                .run(run),
                .dp_valid(c_dp_valid[g]), .dp_ready(c_dp_ready[g]),
                .dp_x(c_dp_x[g]), .dp_seed(c_dp_seed[g]),
                .loaded(c_loaded[g]), .exc(c_exc[g]),
                // The live point is brought out of each core for a logic
                // analyser and for bring-up; nothing in this design reads it.
                .pt_x(c_pt_x[g]), .pt_y(c_pt_y[g]), .step_done(c_step[g]),
                .steps(c_steps[g]), .points(c_points[g]),
                .exceptions(c_exceptions[g])
            );
        end
    endgenerate

    // ---- round-robin collector ---------------------------------------------
    reg [SW-1:0] rr;          // the core that has priority this cycle
    reg [SW-1:0] grant;
    reg          grant_valid;

    integer k;
    reg [SW-1:0] cand;
    always @* begin
        grant_valid = 1'b0;
        grant       = rr;
        // Scan from rr upward, wrapping: the first core with a point wins,
        // and rr advances past it on the handshake, so no core can be
        // starved by a faster neighbour.
        for (k = 0; k < CORES; k = k + 1) begin
            cand = rr + k[SW-1:0];
            if (!grant_valid && c_dp_valid[cand]) begin
                grant       = cand;
                grant_valid = 1'b1;
            end
        end
    end

    assign dp_valid = grant_valid;
    assign dp_x     = c_dp_x[grant];
    assign dp_seed  = c_dp_seed[grant];
    assign dp_core  = {{(8-SW){1'b0}}, grant};

    always @* begin
        c_dp_ready = {CORES{1'b0}};
        if (grant_valid && dp_ready) c_dp_ready[grant] = 1'b1;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rr <= {SW{1'b0}};
        else if (grant_valid && dp_ready) rr <= grant + 1'b1;
    end

    // ---- registers -----------------------------------------------------------
    // Which of the five words of the load window an address selects.
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            run        <= 1'b0;
            sel        <= {SW{1'b0}};
            load_seed  <= 64'd0;
            load_pulse <= {CORES{1'b0}};
            for (i = 0; i < 5; i = i + 1) begin
                load_x_w[i] <= 32'd0;
                load_y_w[i] <= 32'd0;
            end
        end else begin
            load_pulse <= {CORES{1'b0}};
            if (reg_we) begin
                case (reg_addr)
                    8'h00: run <= reg_wdata[0];
                    8'h0C: sel <= reg_wdata[SW-1:0];
                    // Written out rather than decoded arithmetically: a
                    // register map is read by people, and five explicit
                    // addresses are easier to check against the header
                    // comment than an index expression is.
                    8'h20: load_x_w[0] <= reg_wdata;
                    8'h24: load_x_w[1] <= reg_wdata;
                    8'h28: load_x_w[2] <= reg_wdata;
                    8'h2C: load_x_w[3] <= reg_wdata;
                    8'h30: load_x_w[4] <= reg_wdata;
                    8'h34: load_y_w[0] <= reg_wdata;
                    8'h38: load_y_w[1] <= reg_wdata;
                    8'h3C: load_y_w[2] <= reg_wdata;
                    8'h40: load_y_w[3] <= reg_wdata;
                    8'h44: load_y_w[4] <= reg_wdata;
                    8'h48: load_seed[31:0]  <= reg_wdata;
                    8'h4C: load_seed[63:32] <= reg_wdata;
                    8'h50: if (reg_wdata[0]) load_pulse[sel] <= 1'b1;
                    default: ;
                endcase
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_rdata <= 32'd0;
        end else if (reg_re) begin
            case (reg_addr)
                8'h00: reg_rdata <= {31'd0, run};
                8'h04: reg_rdata <= CORES[31:0];
                8'h08: reg_rdata <= {30'd0, (&c_loaded), (|c_exc)};
                8'h0C: reg_rdata <= {{(32-SW){1'b0}}, sel};
                8'h10: reg_rdata <= {{(32-CORES){1'b0}}, c_loaded};
                8'h14: reg_rdata <= {{(32-CORES){1'b0}}, c_exc};
                8'h60: reg_rdata <= c_steps[sel][31:0];
                8'h64: reg_rdata <= c_steps[sel][63:32];
                8'h68: reg_rdata <= c_points[sel][31:0];
                8'h6C: reg_rdata <= c_points[sel][63:32];
                8'h70: reg_rdata <= c_exceptions[sel][31:0];
                8'h74: reg_rdata <= c_exceptions[sel][63:32];
                default: reg_rdata <= 32'd0;
            endcase
        end
    end

    // Tied off rather than left dangling, so that lint stays clean and the
    // debug taps above do not quietly disappear in synthesis without anybody
    // deciding that they should.
    wire _unused_step = |c_step;
    wire _unused_pt   = |c_pt_x[0] | |c_pt_y[0];
endmodule
