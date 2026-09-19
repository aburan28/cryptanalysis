// tb_ecc2k130_core.v - a walker following the model's chain.
//
// The model walks one start point for a few hundred steps and writes every
// point it passes through, with a flag for the distinguished ones.  The core
// is loaded with the same start and has to visit the same points in the same
// order and raise dp on exactly the same ones.
//
// The testbench also holds dp_ready low for a while when a point appears, to
// check the property the corpus depends on: back-pressure stops the walk, it
// does not drop points.  A dropped point is walk time that was paid for and
// silently lost, and nothing downstream could detect it.

`timescale 1ns / 1ps
`include "onb131_defs.vh"

module tb_ecc2k130_core;
    localparam integer M = `ONB_M;

    reg clk = 1'b0, rst_n = 1'b0;
    always #5 clk = ~clk;

    reg          load, run, dp_ready;
    reg  [M-1:0] load_x, load_y;
    reg   [63:0] load_seed;
    wire         dp_valid, loaded, exc, step_done;
    wire [M-1:0] dp_x, pt_x, pt_y;
    wire  [63:0] dp_seed, steps, points, exceptions;

    ecc2k130_core #(.DIGIT(`TB_DIGIT), .DPW(`TB_DPW)) dut (
        .clk(clk), .rst_n(rst_n),
        .load(load), .load_x(load_x), .load_y(load_y), .load_seed(load_seed),
        .run(run),
        .dp_valid(dp_valid), .dp_ready(dp_ready), .dp_x(dp_x), .dp_seed(dp_seed),
        .loaded(loaded), .exc(exc), .pt_x(pt_x), .pt_y(pt_y), .step_done(step_done),
        .steps(steps), .points(points), .exceptions(exceptions)
    );

    integer fd, code, cases, fails, dp_seen, held;
    reg eof;
    reg [M-1:0] wx, wy;
    integer wdp;
    reg [1023:0] path;
    reg saw_backpressure;

    initial begin
        if (!$value$plusargs("vec=%s", path)) path = "vec/chain.vec";
        fd = $fopen(path, "r");
        if (fd == 0) begin
            $display("FAIL: cannot open %0s", path);
            $finish;
        end
        cases = 0; fails = 0; dp_seen = 0; eof = 1'b0; saw_backpressure = 1'b0;
        load = 1'b0; run = 1'b0; dp_ready = 1'b1;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        // The first line is the start point.
        code = $fscanf(fd, "%h %h\n", load_x, load_y);
        if (code != 2) begin
            $display("FAIL: no start point in %0s", path);
            $fatal(1);
        end
        load_seed = 64'h1234_5678_9abc_def0;
        @(posedge clk);
        load <= 1'b1;
        @(posedge clk);
        load <= 1'b0;
        run  <= 1'b1;

        while (!eof && cases < 200) begin
            code = $fscanf(fd, "%h %h %d\n", wx, wy, wdp);
            if (code != 3) begin
                eof = 1'b1;
            end else begin
                // Wait for the next completed step.
                @(posedge clk);
                while (!step_done) @(posedge clk);
                cases = cases + 1;
                if (pt_x !== wx || pt_y !== wy) begin
                    fails = fails + 1;
                    if (fails <= 3)
                        $display("FAIL step %0d:\n  x = %h want %h\n  y = %h want %h",
                                 cases, pt_x, wx, pt_y, wy);
                    eof = 1'b1;
                end
                if (wdp != 0) begin
                    dp_seen = dp_seen + 1;
                    // Every tenth point, refuse to take it and check that the
                    // walk waits rather than moving on.
                    //
                    // The deassert is a blocking assignment on purpose.  A
                    // non-blocking one lands after this edge, so the core's
                    // very next edge still samples dp_ready high, takes the
                    // point, and walks on -- and the check then reports a
                    // core that "kept walking while a point was unread" when
                    // in fact the point had been read.  That is exactly what
                    // happened in CI at DIGIT=16, where the walk is fast
                    // enough for the handshake to win the race; at DIGIT=4 it
                    // passed and hid the bug.
                    if (dp_seen % 10 == 3) begin
                        dp_ready = 1'b0;
                        // Wait for the core to present the point it just
                        // produced, then confirm it stays presented and the
                        // step counter stops.
                        while (!dp_valid) @(posedge clk);
                        held = steps;
                        repeat (200) @(posedge clk);
                        if (steps != held) begin
                            $display("FAIL: the core kept walking while a point was unread (%0d -> %0d)",
                                     held, steps);
                            fails = fails + 1;
                        end else if (!dp_valid) begin
                            $display("FAIL: the core dropped a point the collector had not taken");
                            fails = fails + 1;
                        end else begin
                            saw_backpressure = 1'b1;
                        end
                        dp_ready = 1'b1;
                        @(posedge clk);
                    end
                end
            end
        end
        $fclose(fd);

        if (cases < 20) begin
            $display("FAIL: only %0d steps were compared", cases);
            $fatal(1);
        end
        if (points != dp_seen) begin
            $display("FAIL: core reported %0d points, the model has %0d", points, dp_seen);
            fails = fails + 1;
        end
        if (!saw_backpressure)
            $display("note: no point landed on the back-pressure check in this run");
        if (exceptions != 0) begin
            $display("FAIL: %0d exceptions in a chain the model walked without one", exceptions);
            fails = fails + 1;
        end
        $display("ecc2k130_core DIGIT=%0d: %0d steps, %0d points, %0d failures",
                 `TB_DIGIT, cases, dp_seen, fails);
        if (fails != 0) $fatal(1);
        $finish;
    end
endmodule
