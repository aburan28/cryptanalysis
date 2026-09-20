// tb_onb131_inv.v - Itoh-Tsujii inversion against the model's vectors, with
// the multiplier it shares with the rest of a core wired up exactly as the
// step unit wires it.
//
// The case that matters most is the last line of the file: inverting zero.
// In this walk a zero denominator is not a pathological input, it is the
// exceptional case sigma^j(R) == R, and a core that divides anyway would
// produce a point that is not on the curve and report it as a distinguished
// point.

`timescale 1ns / 1ps
`include "onb131_defs.vh"

module tb_onb131_inv;
    localparam integer M = `ONB_M;

    reg clk = 1'b0, rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [M-1:0] a;
    reg          start;
    wire [M-1:0] y;
    wire         busy, done, zero_input;

    wire              mul_start;
    wire [M-1:0]      mul_a, mul_b, mul_y;
    wire              mul_busy, mul_done;

    onb131_inv dut (
        .clk(clk), .rst_n(rst_n), .start(start), .a(a), .y(y),
        .busy(busy), .done(done), .zero_input(zero_input),
        .mul_start(mul_start), .mul_a(mul_a), .mul_b(mul_b),
        .mul_y(mul_y), .mul_done(mul_done)
    );

    onb131_mul #(.DIGIT(`TB_DIGIT)) u_mul (
        .clk(clk), .rst_n(rst_n), .start(mul_start), .a(mul_a), .b(mul_b),
        .y(mul_y), .busy(mul_busy), .done(mul_done)
    );

    integer fd, code, cases, fails, cycles, total;
    reg eof;
    reg [M-1:0] want;
    reg [1023:0] path;

    task run_one;
        begin
            @(posedge clk);
            start <= 1'b1;
            @(posedge clk);
            start <= 1'b0;
            cycles = 0;
            while (!done) begin
                @(posedge clk);
                cycles = cycles + 1;
                if (cycles > 20000) begin
                    $display("FAIL: inversion never finished");
                    fails = fails + 1;
                    eof = 1'b1;
                    cycles = 0;
                end
            end
        end
    endtask

    initial begin
        if (!$value$plusargs("vec=%s", path)) path = "vec/inv.vec";
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
            code = $fscanf(fd, "%h %h\n", a, want);
            if (code != 2) begin
                eof = 1'b1;
            end else begin
                run_one;
                total = total + cycles;
                cases = cases + 1;
                if (y !== want || zero_input !== 1'b0) begin
                    fails = fails + 1;
                    if (fails <= 3)
                        $display("FAIL case %0d:\n  a    = %h\n  got  = %h\n  want = %h  zero=%b",
                                 cases, a, y, want, zero_input);
                end
            end
        end
        $fclose(fd);

        // Zero: reported, not divided by.
        a = {M{1'b0}};
        run_one;
        if (zero_input !== 1'b1) begin
            $display("FAIL: inverting zero did not raise zero_input");
            fails = fails + 1;
        end

        if (cases == 0) begin
            $display("FAIL: no vectors were read");
            $fatal(1);
        end
        $display("onb131_inv DIGIT=%0d: %0d cases, %0d failures, %0d cycles/inversion",
                 `TB_DIGIT, cases, fails, total / cases);
        if (fails != 0) $fatal(1);
        $finish;
    end
endmodule
