//============================================================================
//
//  JR-100 real-core top (JR100_MiSTer): the structure the MiSTer emu
//  module wraps in Phase E.
//
//  Clocking: one system clock (nominally 57.27272 MHz = 4x NTSC burst,
//  8x pixel clock). Clock enables divide it exactly as the real
//  machine's 14.31818 MHz crystal chain does:
//      cen_cpu = clk / 64  (894.886 kHz, AGENTS.md §3.1)
//      cen_pix = clk / 8   (7.159 MHz)
//
//  Memories are on-chip BRAMs (jr100_mem). The BASIC ROM image
//  (8 KiB: char ROM 0000-03FF + BASIC E400-FFFF) is streamed in via
//  the loader port while `downloading` holds the core in reset; on
//  release the CPU performs the real MC6800 reset sequence
//  (vector_reset).
//
//  cpu_hold is a simulation aid that freezes CPU/VIA while the video
//  keeps scanning (frame capture); tie low in the MiSTer wrapper.
//
//  Copyright (C) 2026 Zabaglione
//  SPDX-License-Identifier: GPL-2.0-or-later
//
//============================================================================

module jr100_top
(
    input  logic        clk,         // system clock (8x pixel, 64x CPU)
    input  logic        rst,
    input  logic        downloading, // ROM upload in progress
    input  logic        cpu_hold,    // sim aid: freeze CPU/VIA

    // ROM loader (8 KiB image)
    input  logic        loader_we,
    input  logic [12:0] loader_addr,
    input  logic [7:0]  loader_data,

    // PROG container loader (user programs, CPU frozen while active)
    input  logic        prg_download,
    input  logic        prg_wr,
    input  logic [7:0]  prg_data,
    output logic        prg_wait,

    // JR-100 inputs
    input  logic [44:0] key_matrix,
    input  logic [7:0]  joy_status,   // CC02 value (AGENTS.md §4)

    // audio: raw PB7 and the band-limited output stage (AGENTS.md §3.4).
    // The gate only affects the output; VIA internals never stop.
    output logic        pb7,
    output logic        audio,

    // video
    output logic        vid_pixel,
    output logic        vid_de,
    output logic        vid_hs,
    output logic        vid_vs,
    output logic [8:0]  vid_hcnt,
    output logic [8:0]  vid_vcnt,

    // clock enables (CE_PIXEL for the MiSTer video pipeline)
    output logic        cen_pix_out,

    // debug/trace (same set as jr100_core)
    output logic        cen_cpu_out,
    output logic        boundary,
    output logic [15:0] dbg_pc,
    output logic [15:0] dbg_sp,
    output logic [15:0] dbg_ix,
    output logic [7:0]  dbg_a,
    output logic [7:0]  dbg_b,
    output logic [7:0]  dbg_cc,
    output logic [7:0]  dbg_ora,
    output logic [7:0]  dbg_orb,
    output logic [7:0]  dbg_ddra,
    output logic [7:0]  dbg_ddrb,
    output logic [7:0]  dbg_acr,
    output logic [7:0]  dbg_pcr,
    output logic [7:0]  dbg_ifr,
    output logic [7:0]  dbg_ier,
    output logic [7:0]  dbg_sr,
    output logic [15:0] dbg_t1,
    output logic [15:0] dbg_t1l,
    output logic [15:0] dbg_t2,
    output logic [15:0] dbg_t2l
);

    // ------------------------------------------------------------------
    // Clock enables
    // ------------------------------------------------------------------
    logic [5:0] cen_cnt;
    logic cen_cpu, cen_pix;
    always_ff @(posedge clk) begin
        if (rst) cen_cnt <= '0;
        else     cen_cnt <= cen_cnt + 6'd1;
    end
    logic prg_busy;
    assign cen_cpu = (cen_cnt == 6'd63) && !cpu_hold && !prg_busy;

    // Output band limiting (AGENTS.md §3.4): the square wave frequency is
    // 894886.25/(latch1+2)/2 Hz. Against a 48 kHz PCM output (24 kHz
    // Nyquist) it aliases when latch1+2 <= 18, so mute below latch1=17.
    // Sound is produced only in T1 mode 3 (ACR[7:6]=11, BASIC ACR=E0).
    assign audio = pb7 && (dbg_acr[7:6] == 2'b11) && (dbg_t1l >= 16'd17);
    assign cen_pix = (cen_cnt[2:0] == 3'd7);
    assign cen_cpu_out = cen_cpu;
    assign cen_pix_out = cen_pix;

    logic core_rst;
    assign core_rst = rst | downloading;

    // ------------------------------------------------------------------
    // Core + memories
    // ------------------------------------------------------------------
    logic [15:0] ext_addr;
    logic [7:0]  ext_wdata;
    logic        ext_we;
    logic [7:0]  ext_rdata;
    logic [15:0] vid_addr;
    logic [7:0]  vid_rdata;

    jr100_core core
    (
        .clk        (clk),
        .rst        (core_rst),
        .cen        (cen_cpu),
        .vector_reset (1'b1),
        .init_pc    (16'h0000),
        .init_sp    (16'h0000),
        .init_ix    (16'h0000),
        .init_a     (8'h00),
        .init_b     (8'h00),
        .init_cc    (8'hD0),
        .ext_addr   (ext_addr),
        .ext_wdata  (ext_wdata),
        .ext_we     (ext_we),
        .ext_rdata  (ext_rdata),
        .key_matrix (key_matrix),
        .pb7        (pb7),
        .cen_vid    (cen_pix),
        .vid_addr   (vid_addr),
        .vid_rdata  (vid_rdata),
        .vid_pixel  (vid_pixel),
        .vid_de     (vid_de),
        .vid_hs     (vid_hs),
        .vid_vs     (vid_vs),
        .vid_hcnt   (vid_hcnt),
        .vid_vcnt   (vid_vcnt),
        .boundary   (boundary),
        .dbg_pc     (dbg_pc),
        .dbg_sp     (dbg_sp),
        .dbg_ix     (dbg_ix),
        .dbg_a      (dbg_a),
        .dbg_b      (dbg_b),
        .dbg_cc     (dbg_cc),
        .dbg_ora    (dbg_ora),
        .dbg_orb    (dbg_orb),
        .dbg_ddra   (dbg_ddra),
        .dbg_ddrb   (dbg_ddrb),
        .dbg_acr    (dbg_acr),
        .dbg_pcr    (dbg_pcr),
        .dbg_ifr    (dbg_ifr),
        .dbg_ier    (dbg_ier),
        .dbg_sr     (dbg_sr),
        .dbg_t1     (dbg_t1),
        .dbg_t1l    (dbg_t1l),
        .dbg_t2     (dbg_t2),
        .dbg_t2l    (dbg_t2l)
    );

    // PROG loader shares the CPU memory port (CPU frozen meanwhile),
    // so its writes see the same writable-region decode as the CPU.
    logic        prg_mem_we;
    logic [15:0] prg_mem_addr;
    logic [7:0]  prg_mem_data;

    jr100_loader prg_loader
    (
        .clk      (clk),
        .rst      (rst),
        .download (prg_download),
        .wr       (prg_wr),
        .data     (prg_data),
        .wait_req (prg_wait),
        .busy     (prg_busy),
        .mem_we   (prg_mem_we),
        .mem_addr (prg_mem_addr),
        .mem_data (prg_mem_data)
    );

    jr100_mem mem
    (
        .clk         (clk),
        .rst         (core_rst),
        .cpu_addr    (prg_busy ? prg_mem_addr : ext_addr),
        .cpu_wdata   (prg_busy ? prg_mem_data : ext_wdata),
        .cpu_we      (prg_busy ? prg_mem_we : ext_we),
        .cpu_rdata   (ext_rdata),
        .vid_addr    (vid_addr),
        .vid_rdata   (vid_rdata),
        .loader_we   (loader_we),
        .loader_addr (loader_addr),
        .loader_data (loader_data),
        .joy_status  (joy_status)
    );

endmodule
