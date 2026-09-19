// tb_onb131_mul.v - the multiplier against the model's vectors.
//
// The testbench holds no arithmetic: it reads triples (a, b, a*b) produced by
// the golden model and requires the RTL to reproduce the third from the first
// two.  A multiplier that is wrong in the fold, in a rotation direction, or
// in the symmetric expansion fails on the basis-element cases at the top of
// the file long before the random ones.

`timescale 1ns / 1ps
`include "onb131_defs.vh"

module tb_onb131_mul;
    localparam integer M = `ONB_M;
    localparam integer DIGIT = `TB_DIGIT;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [M-1:0] a, b;
    reg          start;
    wire [M-1:0] y;
    wire         busy, done;

    onb131_mul #(.DIGIT(DIGIT)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .a(a), .b(b),
        .y(y), .busy(busy), .done(done)
    );

    integer fd, code, cases, fails, cycles, total_cycles;
    reg eof;
    reg [M-1:0] want;
    reg [1023:0] path;

    initial begin
        if (!$value$plusargs("vec=%s", path)) path = "vec/mul.vec";
        fd = $fopen(path, "r");
        if (fd == 0) begin
            $display("FAIL: cannot open %0s", path);
            $finish;
        end
        cases = 0; fails = 0; total_cycles = 0;
        start = 1'b0;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        eof = 1'b0;
        while (!eof) begin
            // $fscanf returns the number of items it matched; anything short
            // of three is the end of the file, or a malformed line, which is
            // a broken generator and equally a reason to stop.
            code = $fscanf(fd, "%h %h %h\n", a, b, want);
            if (code != 3) begin
                if (code > 0)
                    $display("FAIL: malformed vector line (%0d fields)", code);
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
                if (cycles > 4000) begin
                    $display("FAIL: multiplier never finished");
                    fails = fails + 1;
                    eof = 1'b1;
                    cycles = 0;
                end
            end
            total_cycles = total_cycles + cycles;
            cases = cases + 1;
            if (y !== want) begin
                fails = fails + 1;
                if (fails <= 3)
                    $display("FAIL case %0d:\n  a    = %h\n  b    = %h\n  got  = %h\n  want = %h",
                             cases, a, b, y, want);
            end
            end
        end

        $fclose(fd);
        if (cases == 0) begin
            $display("FAIL: no vectors were read from %0s", path);
            $fatal(1);
        end
        $display("onb131_mul DIGIT=%0d: %0d cases, %0d failures, %0d cycles/product",
                 DIGIT, cases, fails, total_cycles / cases);
        if (fails != 0) $fatal(1);
        $finish;
    end
endmodule
