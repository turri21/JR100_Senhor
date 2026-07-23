//============================================================================
//
//  JR100_MiSTer: MiSTer framework wrapper (emu) for the JR-100 core.
//
//  Thin adapter around rtl/jr100/jr100_top.sv, which is verified on Mac
//  by instruction-boundary lockstep against pyjr100emu (docs/).
//
//  Copyright (C) 2026 Zabaglione
//
//  This program is free software; you can redistribute it and/or modify it
//  under the terms of the GNU General Public License as published by the Free
//  Software Foundation; either version 2 of the License, or (at your option)
//  any later version.
//
//  This program is distributed in the hope that it will be useful, but WITHOUT
//  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
//  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
//  more details.
//
//  You should have received a copy of the GNU General Public License along
//  with this program; if not, write to the Free Software Foundation, Inc.,
//  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
//
//============================================================================

module emu
(
	`include "sys/emu_ports.vh"
);

///////// Default values for ports not used in this core /////////

assign ADC_BUS  = 'Z;
assign USER_OUT = '1;
assign {UART_RTS, UART_TXD, UART_DTR} = 0;
assign {SD_SCK, SD_MOSI, SD_CS} = 'Z;
assign {SDRAM_DQ, SDRAM_A, SDRAM_BA, SDRAM_CLK, SDRAM_CKE, SDRAM_DQML, SDRAM_DQMH, SDRAM_nWE, SDRAM_nCAS, SDRAM_nRAS, SDRAM_nCS} = 'Z;
assign {DDRAM_CLK, DDRAM_BURSTCNT, DDRAM_ADDR, DDRAM_DIN, DDRAM_BE, DDRAM_RD, DDRAM_WE} = '0;

assign VGA_SL = 0;
assign VGA_F1 = 0;
assign VGA_SCALER  = 0;
assign VGA_DISABLE = 0;
assign HDMI_FREEZE = 0;
assign HDMI_BLACKOUT = 0;
assign HDMI_BOB_DEINT = 0;

assign AUDIO_S = 0;
assign AUDIO_MIX = 0;

assign LED_DISK = 0;
assign LED_POWER = 0;
assign BUTTONS = 0;

//////////////////////////////////////////////////////////////////

wire [1:0] ar = status[122:121];

assign VIDEO_ARX = (!ar) ? 12'd4 : (ar - 1'd1);
assign VIDEO_ARY = (!ar) ? 12'd3 : 12'd0;

`include "build_id.v"
localparam CONF_STR = {
	"JR100;;",
	"-;",
	"F0,rom,Load BASIC ROM;",
	"F1,prg,Load PRG;",
	"-;",
	"O[122:121],Aspect ratio,Original,Full Screen,[ARC1],[ARC2];",
	"-;",
	"R[0],Reset;",
	"J,Fire;",
	"V,v",`BUILD_DATE
};

wire forced_scandoubler;
wire   [1:0] buttons;
wire [127:0] status;
wire  [10:0] ps2_key;
wire  [31:0] joystick_0;

wire        ioctl_download;
wire  [7:0] ioctl_index;
wire        ioctl_wr;
wire [26:0] ioctl_addr;
wire  [7:0] ioctl_dout;

hps_io #(.CONF_STR(CONF_STR)) hps_io
(
	.clk_sys(clk_sys),
	.HPS_BUS(HPS_BUS),
	.EXT_BUS(),
	.gamma_bus(),

	.forced_scandoubler(forced_scandoubler),

	.buttons(buttons),
	.status(status),
	.status_menumask(0),

	.ps2_key(ps2_key),
	.joystick_0(joystick_0),

	.ioctl_download(ioctl_download),
	.ioctl_index(ioctl_index),
	.ioctl_wr(ioctl_wr),
	.ioctl_addr(ioctl_addr),
	.ioctl_dout(ioctl_dout),
	.ioctl_wait(prg_wait)
);

///////////////////////   CLOCKS   ///////////////////////////////

// 57.272727 MHz = 4x NTSC colorburst: /8 = 7.159 MHz pixel,
// /64 = 894.886 kHz CPU (AGENTS.md §3.1)
wire clk_sys;
pll pll
(
	.refclk(CLK_50M),
	.rst(0),
	.outclk_0(clk_sys)
);

wire reset = RESET | status[0] | buttons[1];

///////////////////////   CORE   /////////////////////////////////

// boot.rom (games/JR100/) and the OSD "F0" slot both arrive as
// ioctl index 0: an 8 KiB image, char ROM first (AGENTS.md §7).
wire rom_download = ioctl_download && (ioctl_index[5:0] == 0);
wire loader_we = ioctl_wr && rom_download && (ioctl_addr[26:13] == 0);

wire prg_download = ioctl_download && (ioctl_index[5:0] == 1);
wire prg_wait;

// MiSTer joystick -> JR-100 CC02 (AGENTS.md §4): bit0=right, bit1=left,
// bit2=up, bit3=down, bit4=fire, all active high, idle = 00.
wire [7:0] joy_status = {3'b000,
                         joystick_0[4],   // fire
                         joystick_0[2],   // down
                         joystick_0[3],   // up
                         joystick_0[1],   // left
                         joystick_0[0]};  // right

wire [44:0] key_matrix;
jr100_keyboard keyboard
(
	.clk(clk_sys),
	.rst(reset),
	.ps2_key(ps2_key),
	.key_matrix(key_matrix)
);

wire pb7;
wire vid_pixel, vid_de, vid_hs, vid_vs;
wire cen_pix;

jr100_top core
(
	.clk         (clk_sys),
	.rst         (reset),
	.downloading (rom_download),
	.cpu_hold    (1'b0),

	.loader_we   (loader_we),
	.loader_addr (ioctl_addr[12:0]),
	.loader_data (ioctl_dout),

	.prg_download (prg_download),
	.prg_wr       (ioctl_wr && prg_download),
	.prg_data     (ioctl_dout),
	.prg_wait     (prg_wait),

	.key_matrix  (key_matrix),
	.joy_status  (joy_status),

	.pb7         (pb7),

	.vid_pixel   (vid_pixel),
	.vid_de      (vid_de),
	.vid_hs      (vid_hs),
	.vid_vs      (vid_vs),
	.vid_hcnt    (),
	.vid_vcnt    (),

	.cen_pix_out (cen_pix),
	.cen_cpu_out (),
	.boundary    (),
	.dbg_pc      (),
	.dbg_sp      (),
	.dbg_ix      (),
	.dbg_a       (),
	.dbg_b       (),
	.dbg_cc      (),
	.dbg_ora     (),
	.dbg_orb     (),
	.dbg_ddra    (),
	.dbg_ddrb    (),
	.dbg_acr     (),
	.dbg_pcr     (),
	.dbg_ifr     (),
	.dbg_ier     (),
	.dbg_sr      (),
	.dbg_t1      (),
	.dbg_t1l     (),
	.dbg_t2      (),
	.dbg_t2l     ()
);

///////////////////////   VIDEO / AUDIO   ////////////////////////

assign CLK_VIDEO = clk_sys;
assign CE_PIXEL  = cen_pix;

assign VGA_DE = vid_de;
assign VGA_HS = vid_hs;
assign VGA_VS = vid_vs;
assign VGA_R  = {8{vid_pixel}};
assign VGA_G  = {8{vid_pixel}};
assign VGA_B  = {8{vid_pixel}};

// Raw Timer 1 square wave for now; the band-limiting stage arrives
// with M4 (AGENTS.md §3.4).
assign AUDIO_L = {1'b0, pb7, 14'd0};
assign AUDIO_R = {1'b0, pb7, 14'd0};

assign LED_USER = ioctl_download;

endmodule
