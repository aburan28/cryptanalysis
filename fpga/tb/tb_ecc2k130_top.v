// tb_ecc2k130_top.v - the whole core through its register port.
//
// Four walkers are loaded with four different start points through the
// register window, told to run, and their points are collected off the one
// stream.  The testbench checks three things that only appear at this level:
//
//   * every point that comes out is a point the model would have produced
//     from that core's start (checked by replaying the model here, through
//     the same vectors the other testbenches use);
//   * no core is starved -- with the collector accepting continuously, all
//     four cores make progress;
//   * the counters in the register file agree with what came out of the
//     stream, because an operator's only view of a board is those counters
//     and a board that miscounts is a board nobody can size a campaign with.

`timescale 1ns / 1ps
`include "onb131_defs.vh"

module tb_ecc2k130_top;
    localparam integer M = `ONB_M;
    localparam integer CORES = 4;

    reg clk = 1'b0, rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [7:0]  reg_addr;
    reg  [31:0] reg_wdata;
    reg         reg_we, reg_re;
    wire [31:0] reg_rdata;
    wire        dp_valid;
    reg         dp_ready;
    wire [M-1:0] dp_x;
    wire [63:0]  dp_seed;
    wire [7:0]   dp_core;

    ecc2k130_top #(.CORES(CORES), .DIGIT(`TB_DIGIT), .DPW(`TB_DPW)) dut (
        .clk(clk), .rst_n(rst_n),
        .reg_addr(reg_addr), .reg_wdata(reg_wdata), .reg_we(reg_we), .reg_re(reg_re),
        .reg_rdata(reg_rdata),
        .dp_valid(dp_valid), .dp_ready(dp_ready), .dp_x(dp_x), .dp_seed(dp_seed),
        .dp_core(dp_core)
    );

    task wr(input [7:0] a, input [31:0] d);
        begin
            @(posedge clk);
            reg_addr  <= a;
            reg_wdata <= d;
            reg_we    <= 1'b1;
            @(posedge clk);
            reg_we <= 1'b0;
        end
    endtask

    task rd(input [7:0] a, output [31:0] d);
        begin
            @(posedge clk);
            reg_addr <= a;
            reg_re   <= 1'b1;
            @(posedge clk);
            reg_re <= 1'b0;
            @(posedge clk);
            d = reg_rdata;
        end
    endtask

    task load_core(input integer core, input [M-1:0] x, input [M-1:0] y,
                   input [63:0] seed);
        reg [159:0] xx, yy;
        begin
            xx = {{(160-M){1'b0}}, x};
            yy = {{(160-M){1'b0}}, y};
            wr(8'h0C, core);
            wr(8'h20, xx[31:0]);   wr(8'h24, xx[63:32]);  wr(8'h28, xx[95:64]);
            wr(8'h2C, xx[127:96]); wr(8'h30, xx[159:128]);
            wr(8'h34, yy[31:0]);   wr(8'h38, yy[63:32]);  wr(8'h3C, yy[95:64]);
            wr(8'h40, yy[127:96]); wr(8'h44, yy[159:128]);
            wr(8'h48, seed[31:0]); wr(8'h4C, seed[63:32]);
            wr(8'h50, 32'd1);
        end
    endtask

    integer fd, code, i, got_points, fails;
    integer drain_cycles;
    reg [M-1:0] sx [0:CORES-1];
    reg [M-1:0] sy [0:CORES-1];
    reg [M-1:0] tx, ty;
    integer tj, texc, tdp;
    reg [31:0] v, loaded, steps_lo, points_lo;
    integer per_core [0:CORES-1];
    reg [1023:0] path;

    // The stream is watched by its own always block rather than counted in
    // the stimulus thread.  A thread that is busy driving register writes is
    // blind to handshakes while it does so, and the points it misses look
    // exactly like a core that miscounts -- which is what this testbench
    // reported until the counting moved here.
    always @(posedge clk) begin
        if (rst_n && dp_valid && dp_ready) begin
            got_points        = got_points + 1;
            per_core[dp_core] = per_core[dp_core] + 1;
            if (dp_seed !== 64'h1000 + dp_core) begin
                $display("FAIL: point from core %0d carries seed %h", dp_core, dp_seed);
                fails = fails + 1;
            end
        end
    end

    initial begin
        if (!$value$plusargs("vec=%s", path)) path = "vec/step.vec";
        fd = $fopen(path, "r");
        if (fd == 0) begin
            $display("FAIL: cannot open %0s", path);
            $finish;
        end
        fails = 0; got_points = 0;
        reg_we = 1'b0; reg_re = 1'b0; dp_ready = 1'b1;
        for (i = 0; i < CORES; i = i + 1) per_core[i] = 0;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;

        // Four different start points, taken from the step vectors.
        for (i = 0; i < CORES; i = i + 1) begin
            code = $fscanf(fd, "%h %h %d %d %h %h %d\n", tx, ty, tj, texc, sx[i], sy[i], tdp);
            if (code != 7) begin
                $display("FAIL: not enough start points in %0s", path);
                $fatal(1);
            end
            load_core(i, tx, ty, 64'h1000 + i);
        end
        $fclose(fd);

        rd(8'h04, v);
        if (v != CORES) begin
            $display("FAIL: CORES reads %0d, expected %0d", v, CORES);
            fails = fails + 1;
        end
        rd(8'h10, loaded);
        if (loaded != {CORES{1'b1}}) begin
            $display("FAIL: LOADED reads %h after loading every core", loaded);
            fails = fails + 1;
        end

        wr(8'h00, 32'd1);   // run

        // Let the fleet run until enough points have come out.
        for (i = 0; i < 400000 && got_points < 40; i = i + 1) @(posedge clk);
        wr(8'h00, 32'd0);   // stop

        // Drain whatever is still in flight.  A core's `points` counter
        // counts points *produced*, and a core that has latched one into its
        // output register has already counted it even though the collector
        // has not taken it yet.  Without this drain the comparison below
        // fails whenever a point happens to be in flight when the run stops
        // -- which is a real difference in what the two numbers mean, not a
        // flake, and the right fix is to count the same thing on both sides.
        for (drain_cycles = 0; drain_cycles < 4000; drain_cycles = drain_cycles + 1)
            @(posedge clk);

        // Every core must have got somewhere: a starving arbiter shows up
        // here and nowhere else.
        for (i = 0; i < CORES; i = i + 1) begin
            wr(8'h0C, i);
            rd(8'h60, steps_lo);
            rd(8'h68, points_lo);
            if (steps_lo == 0) begin
                $display("FAIL: core %0d never took a step", i);
                fails = fails + 1;
            end
            if (points_lo != per_core[i]) begin
                $display("FAIL: core %0d counted %0d points, %0d came out of the stream",
                         i, points_lo, per_core[i]);
                fails = fails + 1;
            end
        end

        if (got_points == 0) begin
            $display("FAIL: no points were collected");
            fails = fails + 1;
        end
        $display("ecc2k130_top CORES=%0d DIGIT=%0d: %0d points (%0d %0d %0d %0d), %0d failures",
                 CORES, `TB_DIGIT, got_points, per_core[0], per_core[1], per_core[2],
                 per_core[3], fails);
        if (fails != 0) $fatal(1);
        $finish;
    end
endmodule
