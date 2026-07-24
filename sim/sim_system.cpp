//============================================================================
//
//  Verilator lockstep harness for the JR-100 system (CPU + VIA + decode).
//
//  Same contract as sim_main.cpp, but instantiates jr100_core and emits
//  real VIA state in the trace (full-field comparison with trace_diff).
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

#include "Vjr100_core.h"
#include "verilated.h"

namespace {

struct DumpRange {
    uint32_t start;
    uint32_t end;
};

uint8_t g_mem[0x10000];

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

void write_dump(FILE* fp, const std::vector<DumpRange>& ranges) {
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
                fprintf(fp, " %02X", g_mem[(base + off) & 0xFFFF]);
            fputc('\n', fp);
        }
    }
}

void emit_sample(FILE* fp, long n, uint64_t clk, const Vjr100_core* top) {
    fprintf(fp,
            "S n=%ld clk=%llu pc=%04X a=%02X b=%02X ix=%04X sp=%04X cc=%02X"
            " ora=%02X orb=%02X ddra=%02X ddrb=%02X acr=%02X pcr=%02X"
            " ifr=%02X ier=%02X sr=%02X t1=%04X t1l=%04X t2=%04X t2l=%04X\n",
            n, static_cast<unsigned long long>(clk),
            top->dbg_pc, top->dbg_a, top->dbg_b, top->dbg_ix, top->dbg_sp,
            top->dbg_cc,
            top->dbg_ora, top->dbg_orb, top->dbg_ddra, top->dbg_ddrb,
            top->dbg_acr, top->dbg_pcr, top->dbg_ifr, top->dbg_ier,
            top->dbg_sr, top->dbg_t1, top->dbg_t1l, top->dbg_t2,
            top->dbg_t2l);
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    const char* image_path = nullptr;
    const char* trace_path = nullptr;
    const char* dump_path = nullptr;
    const char* frame_path = nullptr;
    const char* program_name = "unknown";
    bool boot = false;
    bool vector_reset = false;
    bool pc_given = false, sp_given = false, cc_given = false;
    uint32_t start_pc = 0x0300;
    uint32_t start_sp = 0x0244;
    uint32_t init_a = 0, init_b = 0, init_ix = 0, init_cc = 0xC0;
    uint64_t max_cycles = 1000000;
    std::vector<DumpRange> ranges;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto next = [&]() -> const char* {
            if (i + 1 >= argc) {
                fprintf(stderr, "error: %s needs a value\n", arg.c_str());
                exit(2);
            }
            return argv[++i];
        };
        if (arg == "--image") image_path = next();
        else if (arg == "--boot") boot = true;
        else if (arg == "--vector-reset") vector_reset = true;
        else if (arg == "--pc") { start_pc = parse_hex(next()); pc_given = true; }
        else if (arg == "--sp") { start_sp = parse_hex(next()); sp_given = true; }
        else if (arg == "--a") init_a = parse_hex(next());
        else if (arg == "--b") init_b = parse_hex(next());
        else if (arg == "--ix") init_ix = parse_hex(next());
        else if (arg == "--cc") { init_cc = parse_hex(next()); cc_given = true; }
        else if (arg == "--cycles") max_cycles = strtoull(next(), nullptr, 10);
        else if (arg == "--trace") trace_path = next();
        else if (arg == "--dump") dump_path = next();
        else if (arg == "--frame") frame_path = next();
        else if (arg == "--program-name") program_name = next();
        else if (arg == "--dump-range") {
            DumpRange r;
            if (!parse_range(next(), r)) {
                fprintf(stderr, "error: bad --dump-range\n");
                return 2;
            }
            ranges.push_back(r);
        } else {
            fprintf(stderr, "error: unknown argument %s\n", arg.c_str());
            return 2;
        }
    }

    if (!image_path) {
        fprintf(stderr, "usage: Vjr100_core --image mem.bin --pc 0300 [--sp 0244]"
                        " [--cycles N] [--trace out] [--dump out --dump-range S:E]\n");
        return 2;
    }

    FILE* img = fopen(image_path, "rb");
    if (!img) {
        fprintf(stderr, "error: cannot open image %s\n", image_path);
        return 2;
    }
    size_t got = fread(g_mem, 1, sizeof(g_mem), img);
    fclose(img);
    if (got != sizeof(g_mem)) {
        fprintf(stderr, "error: image must be 65536 bytes (got %zu)\n", got);
        return 2;
    }

    if (boot) {
        // Boot comparison convention (docs/BOOT_LOCKSTEP.md): PC from the
        // reset vector, I=1 (RESET spec), everything else normalised to 0.
        if (pc_given || sp_given || cc_given) {
            fprintf(stderr, "error: --boot cannot be combined with --pc/--sp/--cc\n");
            return 2;
        }
        start_pc = (static_cast<uint32_t>(g_mem[0xFFFE]) << 8) | g_mem[0xFFFF];
        start_sp = 0x0000;
        init_cc = 0xD0;
    }

    FILE* trace = nullptr;
    if (trace_path) {
        trace = (strcmp(trace_path, "-") == 0) ? stdout : fopen(trace_path, "w");
        if (!trace) {
            fprintf(stderr, "error: cannot open trace %s\n", trace_path);
            return 2;
        }
        fputs("# jr100-trace v1\n", trace);
        fputs("# generator: JR100_MiSTer verilator system harness\n", trace);
        fprintf(trace, "# program: %s\n", program_name);
    }

    auto* top = new Vjr100_core;
    top->rst = 1;
    top->cen = 1;
    top->cen_vid = 0;
    top->vid_rdata = 0;
    top->key_matrix = 0;
    top->vector_reset = vector_reset ? 1 : 0;
    if (vector_reset) {
        start_sp = 0x0000;
        init_cc = 0xD0;
    }
    top->init_pc = start_pc & 0xFFFF;
    top->init_sp = start_sp & 0xFFFF;
    top->init_ix = init_ix & 0xFFFF;
    top->init_a = init_a & 0xFF;
    top->init_b = init_b & 0xFF;
    top->init_cc = init_cc & 0xFF;
    top->ext_rdata = 0;

    top->clk = 0; top->eval();
    top->clk = 1; top->eval();
    top->rst = 0;
    top->clk = 0; top->eval();

    uint64_t cycles = 0;
    long samples = 0;
    while (true) {
        if (top->boundary && cycles > 0) {
            ++samples;
            if (trace) emit_sample(trace, samples, cycles, top);
            if (cycles >= max_cycles) break;
        }
        top->ext_rdata = g_mem[top->ext_addr];
        top->eval();
        const bool we = top->ext_we;
        const uint16_t wa = top->ext_addr;
        const uint8_t wd = top->ext_wdata;
        top->clk = 1; top->eval();
        if (we) g_mem[wa] = wd;
        top->clk = 0; top->eval();
        ++cycles;
        if (cycles > max_cycles + 100000) {
            fprintf(stderr, "error: no instruction boundary reached; aborting\n");
            break;
        }
    }

    if (trace && trace != stdout) fclose(trace);

    if (frame_path) {
        // Freeze CPU/VIA and scan one full video frame from the final
        // memory state (256x192 active pixels, PGM P5 output).
        static uint8_t fb[192][256];
        memset(fb, 0, sizeof(fb));
        top->cen = 0;
        top->cen_vid = 1;
        const uint64_t frame_cycles = 448ULL * 256ULL + 16;
        for (uint64_t i = 0; i < frame_cycles; ++i) {
            top->vid_rdata = g_mem[top->vid_addr];
            top->ext_rdata = g_mem[top->ext_addr];
            top->eval();
            if (top->vid_de) {
                const uint32_t x = top->vid_hcnt - 64;
                const uint32_t y = top->vid_vcnt - 35;
                if (x < 256 && y < 192) fb[y][x] = top->vid_pixel ? 255 : 0;
            }
            top->clk = 1; top->eval();
            top->clk = 0; top->eval();
        }
        FILE* fp = fopen(frame_path, "wb");
        if (!fp) {
            fprintf(stderr, "error: cannot open frame %s\n", frame_path);
            return 2;
        }
        fputs("P5\n256 192\n255\n", fp);
        fwrite(fb, 1, sizeof(fb), fp);
        fclose(fp);
    }

    if (dump_path) {
        FILE* fp = (strcmp(dump_path, "-") == 0) ? stdout : fopen(dump_path, "w");
        if (!fp) {
            fprintf(stderr, "error: cannot open dump %s\n", dump_path);
            return 2;
        }
        if (ranges.empty()) ranges.push_back({0x0000, 0xFFFF});
        write_dump(fp, ranges);
        if (fp != stdout) fclose(fp);
    }

    top->final();
    delete top;
    return 0;
}
