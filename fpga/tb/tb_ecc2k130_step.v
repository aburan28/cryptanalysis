// tb_ecc2k130_step.v - one rho iteration against the model.
//
// Each vector is a point, the j the iteration selects for it, whether the
// step is exceptional, the resulting point and whether that point is
// distinguished.  All five are compared: a core that computes the right
// point but the wrong distinguished-point flag reports nothing and looks
// like a slow machine, which is the failure that would take longest to
// notice in a running campaign.

`timescale 1ns / 1ps
`include "onb131_defs.vh"

module tb_ecc2k130_step;
    localparam integer M = `ONB_M;

    reg clk = 1'b0, rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [M-1:0] x_in, y_in;
    reg          start;
    wire [M-1:0] x_out, y_out;
    wire         dp, exc, busy, done;
    wire   [2:0] j_out;

    ecc2k130_step #(.DIGIT(`TB_DIGIT), .DPW(`TB_DPW)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .x_in(x_in), .y_in(y_in),
        .x_out(x_out), .y_out(y_out), .dp(dp), .exc(exc),
        .busy(busy), .done(done), .j_out(j_out)
    );

    integer fd, code, cases, fails, cycles, total;
    reg eof;
    reg [M-1:0] wx, wy;
    integer wj, wexc, wdp;
    reg [1023:0] path;

    initial begin
        if (!$value$plusargs("vec=%s", path)) path = "vec/step.vec";
        fd = $fopen(path, "r");
        if (fd == 0) begin
            $display("FAIL: cannot open %0s", path);
            $finish;
        end
        cases = 0; fails = 0; total = 0; start = 1'b0; eof = 1'b0;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        while (!eof) begin
            code = $fscanf(fd, "%h %h %d %d %h %h %d\n", x_in, y_in, wj, wexc, wx, wy, wdp);
            if (code != 7) begin
                eof = 1'b1;
            end else begin
                @(posedge clk);
                start <= 1'b1;
                @(posedge clk);
                start <= 1'b0;
                cycles = 0;
                while (!done) begin
                    @(posedge clk);
                    cycles = cycles + 1;
                    if (cycles > 40000) begin
                        $display("FAIL: step never finished");
                        fails = fails + 1;
                        eof = 1'b1;
                        cycles = 0;
                    end
                end
                total = total + cycles;
                cases = cases + 1;

                if (j_out + `ONB_JMIN !== wj) begin
                    fails = fails + 1;
                    $display("FAIL case %0d: j = %0d, want %0d", cases, j_out + `ONB_JMIN, wj);
                end
                if (exc !== (wexc != 0)) begin
                    fails = fails + 1;
                    $display("FAIL case %0d: exc = %b, want %0d", cases, exc, wexc);
                end
                if (!exc) begin
                    if (x_out !== wx || y_out !== wy) begin
                        fails = fails + 1;
                        if (fails <= 3)
                            $display("FAIL case %0d:\n  x  = %h want %h\n  y  = %h want %h",
                                     cases, x_out, wx, y_out, wy);
                    end
                    if (dp !== (wdp != 0)) begin
                        fails = fails + 1;
                        $display("FAIL case %0d: dp = %b, want %0d", cases, dp, wdp);
                    end
                end
            end
        end
        $fclose(fd);

        if (cases == 0) begin
            $display("FAIL: no vectors were read");
            $fatal(1);
        end
        $display("ecc2k130_step DIGIT=%0d: %0d cases, %0d failures, %0d cycles/step",
                 `TB_DIGIT, cases, fails, total / cases);
        if (fails != 0) $fatal(1);
        $finish;
    end
endmodule
