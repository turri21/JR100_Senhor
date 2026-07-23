//============================================================================
//
//  Verilator harness for jr100_top: the real-core structure (BRAMs,
//  divided clock enables, ROM loader, MC6800 vector reset).
//
//  Boot verification only: streams the 8 KiB ROM image through the
//  loader, runs the boot, and emits an epoch-adjusted trace (the two
//  vector-fetch cycles are removed so the output compares 1:1 with
//  the pyjr100emu --boot reference), a memory dump reconstructed from
//  the BRAMs, and an optional frame capture.
//
//  Copyright (C) 2026 Zabaglione
//  SPDX-License-Identifier: GPL-2.0-or-later
//
//============================================================================

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "Vjr100_top.h"
#include "Vjr100_top___024root.h"
#include "verilated.h"

namespace {

struct DumpRange {
    uint32_t start;
    uint32_t end;
};

uint32_t parse_hex(const char* text) {
    return static_cast<uint32_t>(strtoul(text, nullptr, 16));
}

bool parse_range(const std::string& spec, DumpRange& out) {
    auto colon = spec.find(':');
    if (colon == std::string::npos) return false;
    out.start = parse_hex(spec.substr(0, colon).c_str()) & 0xFFFF;
    out.end   = parse_hex(spec.substr(colon + 1).c_str()) & 0xFFFF;
    return out.end >= out.start;
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    const char* image_path = nullptr;
    const char* trace_path = nullptr;
    const char* dump_path = nullptr;
    const char* frame_path = nullptr;
    const char* prg_path = nullptr;
    const char* audio_path = nullptr;
    const char* program_name = "jr100-boot";
    uint64_t max_cycles = 600000;
    bool ext_ram = false;
    uint32_t joy = 0, joy2 = 0;
    uint64_t joy2_at = 0;   // CPU cycle to switch joy -> joy2 (0 = never)
    std::vector<DumpRange> ranges;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto next = [&]() -> const char* {
            if (i + 1 >= argc) { fprintf(stderr, "error: %s needs a value\n", arg.c_str()); exit(2); }
            return argv[++i];
        };
        if (arg == "--image") image_path = next();
        else if (arg == "--cycles") max_cycles = strtoull(next(), nullptr, 10);
        else if (arg == "--trace") trace_path = next();
        else if (arg == "--dump") dump_path = next();
        else if (arg == "--frame") frame_path = next();
        else if (arg == "--prg") prg_path = next();
        else if (arg == "--ext-ram") ext_ram = true;
        else if (arg == "--audio") audio_path = next();
        else if (arg == "--joy") joy = parse_hex(next());
        else if (arg == "--joy2") joy2 = parse_hex(next());
        else if (arg == "--joy2-at") joy2_at = strtoull(next(), nullptr, 10);
        else if (arg == "--program-name") program_name = next();
        else if (arg == "--dump-range") {
            DumpRange r;
            if (!parse_range(next(), r)) { fprintf(stderr, "error: bad --dump-range\n"); return 2; }
            ranges.push_back(r);
        } else {
            fprintf(stderr, "error: unknown argument %s\n", arg.c_str());
            return 2;
        }
    }

    if (!image_path) {
        fprintf(stderr, "usage: Vjr100_top --image mem.bin [--cycles N]"
                        " [--trace out] [--dump out --dump-range S:E] [--frame out.pgm]\n");
        return 2;
    }

    static uint8_t image[0x10000];
    {
        FILE* fp = fopen(image_path, "rb");
        if (!fp) { fprintf(stderr, "error: cannot open %s\n", image_path); return 2; }
        size_t got = fread(image, 1, sizeof(image), fp);
        fclose(fp);
        if (got != sizeof(image)) { fprintf(stderr, "error: image must be 65536 bytes\n"); return 2; }
    }

    FILE* trace = nullptr;
    if (trace_path) {
        trace = fopen(trace_path, "w");
        if (!trace) { fprintf(stderr, "error: cannot open %s\n", trace_path); return 2; }
        fputs("# jr100-trace v1\n", trace);
        fputs("# generator: JR100_MiSTer verilator jr100_top harness\n", trace);
        fprintf(trace, "# program: %s\n", program_name);
    }

    auto* top = new Vjr100_top;
    auto tick = [&]() {
        top->clk = 1; top->eval();
        top->clk = 0; top->eval();
    };

    top->rst = 1;
    top->downloading = 0;
    top->cpu_hold = 0;
    top->loader_we = 0;
    top->loader_addr = 0;
    top->loader_data = 0;
    top->key_matrix = 0;
    top->joy_status = joy & 0xFF;
    top->prg_download = 0;
    top->prg_wr = 0;
    top->prg_data = 0;
    top->ext_ram_en = ext_ram ? 1 : 0;
    top->clk = 0; top->eval();
    tick();
    top->rst = 0;

    // Stream the 8 KiB ROM image (E000-FFFF) through the loader.
    top->downloading = 1;
    for (uint32_t i = 0; i < 0x2000; ++i) {
        top->loader_we = 1;
        top->loader_addr = i;
        top->loader_data = image[0xE000 + i];
        top->eval();
        tick();
    }
    top->loader_we = 0;
    top->downloading = 0;
    top->eval();

    // Boot run. Epoch adjustment: the first boundary sample (after the
    // two vector-fetch cycles) is the comparison epoch; drop it and
    // report clk relative to it.
    uint64_t cpu_cycles = 0;
    long samples = 0;
    bool epoch_seen = false;
    FILE* audio_fp = nullptr;
    int audio_last = -1;
    if (audio_path) {
        audio_fp = fopen(audio_path, "w");
        if (!audio_fp) { fprintf(stderr, "error: cannot open %s\n", audio_path); return 2; }
    }
    const uint64_t hard_limit = (max_cycles + 100) * 64ULL * 4ULL;
    uint64_t fast = 0;
    while (fast++ < hard_limit) {
        top->eval();
        if (top->cen_cpu_out && top->boundary && cpu_cycles > 0) {
            if (!epoch_seen) {
                epoch_seen = true;   // epoch sample (clk==2): dropped
            } else {
                ++samples;
                const uint64_t clk = cpu_cycles - 2;
                if (trace) {
                    fprintf(trace,
                            "S n=%ld clk=%llu pc=%04X a=%02X b=%02X ix=%04X sp=%04X cc=%02X"
                            " ora=%02X orb=%02X ddra=%02X ddrb=%02X acr=%02X pcr=%02X"
                            " ifr=%02X ier=%02X sr=%02X t1=%04X t1l=%04X t2=%04X t2l=%04X\n",
                            samples, static_cast<unsigned long long>(clk),
                            top->dbg_pc, top->dbg_a, top->dbg_b, top->dbg_ix,
                            top->dbg_sp, top->dbg_cc,
                            top->dbg_ora, top->dbg_orb, top->dbg_ddra, top->dbg_ddrb,
                            top->dbg_acr, top->dbg_pcr, top->dbg_ifr, top->dbg_ier,
                            top->dbg_sr, top->dbg_t1, top->dbg_t1l, top->dbg_t2,
                            top->dbg_t2l);
                }
                if (clk >= max_cycles) break;
            }
        }
        const bool cen = top->cen_cpu_out;
        if (audio_fp && cen && top->audio != audio_last) {
            fprintf(audio_fp, "%llu %d\n",
                    static_cast<unsigned long long>(cpu_cycles), top->audio ? 1 : 0);
            audio_last = top->audio;
        }
        tick();
        if (cen) ++cpu_cycles;
        if (joy2_at && cpu_cycles >= joy2_at) top->joy_status = joy2 & 0xFF;
    }
    if (audio_fp) fclose(audio_fp);
    if (trace) fclose(trace);

    if (prg_path) {
        // Stream a PROG container through the PRG loader (CPU frozen by
        // prg busy), then let the finaliser drain.
        FILE* fp = fopen(prg_path, "rb");
        if (!fp) { fprintf(stderr, "error: cannot open %s\n", prg_path); return 2; }
        int c;
        top->prg_download = 1;
        tick();   // download leads the first wr, as with real hps_io
        while ((c = fgetc(fp)) != EOF) {
            while (top->prg_wait) tick();
            top->prg_wr = 1;
            top->prg_data = static_cast<uint8_t>(c);
            top->eval();
            tick();
            top->prg_wr = 0;
            tick();
        }
        fclose(fp);
        top->prg_download = 0;
        for (int i = 0; i < 64; ++i) tick();   // drain the finaliser
    }

    if (frame_path) {
        static uint8_t fb[192][256];
        memset(fb, 0, sizeof(fb));
        top->cpu_hold = 1;
        const uint64_t frame_fast = 455ULL * 262ULL * 8ULL * 2ULL;
        for (uint64_t i = 0; i < frame_fast; ++i) {
            top->eval();
            if (top->vid_de) {
                const uint32_t x = top->vid_hcnt - 64;
                const uint32_t y = top->vid_vcnt - 35;
                if (x < 256 && y < 192) fb[y][x] = top->vid_pixel ? 255 : 0;
            }
            tick();
        }
        FILE* fp = fopen(frame_path, "wb");
        if (!fp) { fprintf(stderr, "error: cannot open %s\n", frame_path); return 2; }
        fputs("P5\n256 192\n255\n", fp);
        fwrite(fb, 1, sizeof(fb), fp);
        fclose(fp);
    }

    if (dump_path) {
        // Reconstruct the address space view from the BRAMs.
        static uint8_t mem[0x10000];
        memset(mem, 0, sizeof(mem));
        auto* r = top->rootp;
        for (int i = 0; i < 16384; ++i) mem[i] = r->jr100_top__DOT__mem__DOT__main_ram[i];
        for (int i = 0; i < 256; ++i)   mem[0xC000 + i] = r->jr100_top__DOT__mem__DOT__cgram[i];
        for (int i = 0; i < 768; ++i)   mem[0xC100 + i] = r->jr100_top__DOT__mem__DOT__vram[i];
        for (int i = 0; i < 1024; ++i)  mem[0xE000 + i] = r->jr100_top__DOT__mem__DOT__char_rom[i];
        for (int i = 0; i < 7168; ++i)  mem[0xE400 + i] = r->jr100_top__DOT__mem__DOT__basic_rom[i];
        mem[0xD000] = 0xAA;

        FILE* fp = fopen(dump_path, "w");
        if (!fp) { fprintf(stderr, "error: cannot open %s\n", dump_path); return 2; }
        if (ranges.empty()) ranges.push_back({0x0000, 0xFFFF});
        for (size_t i = 0; i < ranges.size(); ++i) {
            if (i) fputc('\n', fp);
            fputs("ADDR", fp);
            for (int off = 0; off < 16; ++off) fprintf(fp, " +%X", off);
            fputc('\n', fp);
            uint32_t start_line = ranges[i].start & ~0x0Fu;
            uint32_t end_line   = ranges[i].end | 0x0Fu;
            for (uint32_t base = start_line; base <= end_line; base += 16) {
                fprintf(fp, "%04X", base & 0xFFFF);
                for (uint32_t off = 0; off < 16; ++off)
                    fprintf(fp, " %02X", mem[(base + off) & 0xFFFF]);
                fputc('\n', fp);
            }
        }
        fclose(fp);
    }

    top->final();
    delete top;
    return 0;
}
