//============================================================================
//
//  Verilator lockstep harness for the MB8861 CPU core (JR100_MiSTer).
//
//  Loads a 64 KiB memory image (produced by pyjr100emu debug_runner
//  --save-initial-memory), runs the CPU with injected initial registers,
//  and writes an instruction-boundary trace (docs/TRACE_FORMAT.md v1)
//  plus a final memory dump in the same hex format as debug_runner.
//  VIA fields are emitted as zeros; compare with trace_diff --cpu-only
//  until the VIA exists (Phase D).
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

#include "Vmb8861.h"
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

void emit_sample(FILE* fp, long n, uint64_t clk, const Vmb8861* top) {
    fprintf(fp,
            "S n=%ld clk=%llu pc=%04X a=%02X b=%02X ix=%04X sp=%04X cc=%02X"
            " ora=00 orb=00 ddra=00 ddrb=00 acr=00 pcr=00 ifr=00 ier=00 sr=00"
            " t1=0000 t1l=0000 t2=0000 t2l=0000\n",
            n, static_cast<unsigned long long>(clk),
            top->dbg_pc, top->dbg_a, top->dbg_b, top->dbg_ix, top->dbg_sp,
            top->dbg_cc);
}

}  // namespace

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    const char* image_path = nullptr;
    const char* trace_path = nullptr;
    const char* dump_path = nullptr;
    const char* program_name = "unknown";
    uint32_t start_pc = 0x0300;
    uint32_t start_sp = 0x0244;
    uint32_t init_a = 0, init_b = 0, init_ix = 0, init_cc = 0xC0;
    uint64_t max_cycles = 1000000;
    std::vector<DumpRange> ranges;
    std::vector<std::pair<uint64_t, int>> irq_events;   // cycle -> level
    std::vector<uint64_t> nmi_events;                   // cycle (pulse)

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
        else if (arg == "--pc") start_pc = parse_hex(next());
        else if (arg == "--sp") start_sp = parse_hex(next());
        else if (arg == "--a") init_a = parse_hex(next());
        else if (arg == "--b") init_b = parse_hex(next());
        else if (arg == "--ix") init_ix = parse_hex(next());
        else if (arg == "--cc") init_cc = parse_hex(next());
        else if (arg == "--cycles") max_cycles = strtoull(next(), nullptr, 10);
        else if (arg == "--trace") trace_path = next();
        else if (arg == "--dump") dump_path = next();
        else if (arg == "--program-name") program_name = next();
        else if (arg == "--irq-at") {
            std::string spec = next();
            auto colon = spec.find(':');
            if (colon == std::string::npos) {
                fprintf(stderr, "error: --irq-at CYCLE:LEVEL\n");
                return 2;
            }
            irq_events.emplace_back(strtoull(spec.c_str(), nullptr, 10),
                                    atoi(spec.c_str() + colon + 1));
        }
        else if (arg == "--nmi-at") nmi_events.push_back(strtoull(next(), nullptr, 10));
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
        fprintf(stderr, "usage: Vmb8861 --image mem.bin --pc 0300 [--sp 0244]"
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

    FILE* trace = nullptr;
    if (trace_path) {
        trace = (strcmp(trace_path, "-") == 0) ? stdout : fopen(trace_path, "w");
        if (!trace) {
            fprintf(stderr, "error: cannot open trace %s\n", trace_path);
            return 2;
        }
        fputs("# jr100-trace v1\n", trace);
        fputs("# generator: JR100_MiSTer verilator harness\n", trace);
        fprintf(trace, "# program: %s\n", program_name);
    }

    auto* top = new Vmb8861;
    top->rst = 1;
    top->cen = 1;
    top->vector_reset = 0;
    top->nmi_set = 0;
    top->irq_level = 0;
    top->init_pc = start_pc & 0xFFFF;
    top->init_sp = start_sp & 0xFFFF;
    top->init_ix = init_ix & 0xFFFF;
    top->init_a = init_a & 0xFF;
    top->init_b = init_b & 0xFF;
    top->init_cc = init_cc & 0xFF;
    top->bus_rdata = 0;

    top->clk = 0; top->eval();
    top->clk = 1; top->eval();
    top->rst = 0;
    top->clk = 0; top->eval();

    uint64_t cycles = 0;
    long samples = 0;
    size_t irq_next = 0;
    size_t nmi_next = 0;
    while (true) {
        if (top->boundary && cycles > 0) {
            ++samples;
            if (trace) emit_sample(trace, samples, cycles, top);
            if (cycles >= max_cycles) break;
        }
        // interrupt events become visible at the first boundary >= cycle
        while (irq_next < irq_events.size() && cycles >= irq_events[irq_next].first) {
            top->irq_level = irq_events[irq_next].second ? 1 : 0;
            ++irq_next;
        }
        top->nmi_set = 0;
        if (nmi_next < nmi_events.size() && cycles >= nmi_events[nmi_next]) {
            top->nmi_set = 1;
            ++nmi_next;
        }
        top->bus_rdata = g_mem[top->bus_addr];
        top->eval();
        const bool we = top->bus_we;
        const uint16_t wa = top->bus_addr;
        const uint8_t wd = top->bus_wdata;
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
