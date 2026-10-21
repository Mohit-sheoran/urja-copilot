`timescale 1ns/1ps

module tb_uart_top;

    reg clk;
    reg reset;
    reg [7:0] tx_data;
    reg tx_start;
    wire tx_serial;
    wire tx_busy;
    wire [7:0] rx_data;
    wire rx_done;

    // Connect top module (Loopback: tx_serial directly to rx_serial)
    uart_top dut (
        .clk(clk),
        .reset(reset),
        .tx_data(tx_data),
        .tx_start(tx_start),
        .tx_serial(tx_serial),
        .tx_busy(tx_busy),
        .rx_serial(tx_serial),
        .rx_data(rx_data),
        .rx_done(rx_done)
    );

    // Clock generator (20ns period)
    always #10 clk = ~clk;

    initial begin
        clk = 0;
        reset = 1;
        tx_data = 8'h00;
        tx_start = 0;

        #40 reset = 0;

        // Test Byte 1: 0xA5 (10100101)
        #50;
        tx_data = 8'hA5;
        tx_start = 1;
        #20;
        tx_start = 0;

        @(posedge rx_done);
        $display("[SIM] Byte 1 Received: 0x%h (Expected: 0xA5)", rx_data);

        // Test Byte 2: 0x3C (00111100)
        #200;
        tx_data = 8'h3C;
        tx_start = 1;
        #20;
        tx_start = 0;

        @(posedge rx_done);
        $display("[SIM] Byte 2 Received: 0x%h (Expected: 0x3C)", rx_data);

        #300;
        $finish;
    end

endmodule
