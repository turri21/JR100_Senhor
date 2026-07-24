//============================================================================
//
//  Verilator per-cycle unit harness for jr100_via.
//
//  Runs the same scenario files as tools/gen_via_vectors.py and emits
//  the identical observable-state lines for exact diffing.
//
//  Copyright (C) 2026 Zabaglione
//  SPDX-License-Identifier: GPL-2.0-or-later
//
//============================================================================

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "Vjr100_via.h"
#include "verilated.h"

struct Op {
    bool write;
    uint8_t reg;
    uint8_t value;
};

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    const char* scenario_path = nullptr;
    const char* out_path = nullptr;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--scenario" && i + 1 < argc) scenario_path = argv[++i];
        else if (arg == "--out" && i + 1 < argc) out_path = argv[++i];
    }
    if (!scenario_path || !out_path) {
        fprintf(stderr, "usage: Vjr100_via --scenario file --out file\n");
        return 2;
    }

    uint64_t total = 0;
    std::map<uint64_t, std::vector<Op>> ops;
    std::map<uint64_t, std::vector<std::pair<bool,bool>>> edges;  // (is_ca1, level)
    {
        std::ifstream in(scenario_path);
        if (!in) {
            fprintf(stderr, "error: cannot open %s\n", scenario_path);
            return 2;
        }
        std::string raw;
        while (std::getline(in, raw)) {
            auto hash = raw.find('#');
            if (hash != std::string::npos) raw.erase(hash);
            std::istringstream ss(raw);
            std::string kind;
            if (!(ss >> kind)) continue;
            if (kind == "N") {
                ss >> total;
            } else if (kind == "E") {
                uint64_t cycle;
                std::string line_s;
                int state;
                ss >> cycle >> line_s >> state;
                edges[cycle].push_back({line_s == "A" || line_s == "a", state != 0});
            } else if (kind == "W" || kind == "R") {
                uint64_t cycle;
                std::string reg_s, val_s;
                ss >> cycle >> reg_s;
                Op op{kind == "W", static_cast<uint8_t>(strtoul(reg_s.c_str(), nullptr, 16)), 0};
                if (op.write) {
                    ss >> val_s;
                    op.value = static_cast<uint8_t>(strtoul(val_s.c_str(), nullptr, 16));
                }
                ops[cycle].push_back(op);
            }
        }
    }

    FILE* out = fopen(out_path, "w");
    if (!out) {
        fprintf(stderr, "error: cannot open %s\n", out_path);
        return 2;
    }

    auto* top = new Vjr100_via;
    top->rst = 1;
    top->cen = 1;
    top->sel = 0;
    top->we = 0;
    top->reg_addr = 0;
    top->wdata = 0;
    top->key_matrix = 0;
    top->ca1_in = 0;
    top->cb1_in = 0;
    top->clk = 0; top->eval();
    top->clk = 1; top->eval();
    top->rst = 0;
    top->clk = 0; top->eval();

    for (uint64_t k = 0; k < total; ++k) {
        // one access per cycle (scenarios schedule at most one)
        top->sel = 0;
        top->we = 0;
        auto eit = edges.find(k);
        if (eit != edges.end())
            for (auto& e : eit->second)
                (e.first ? top->ca1_in : top->cb1_in) = e.second ? 1 : 0;
        auto it = ops.find(k);
        if (it != ops.end() && !it->second.empty()) {
            const Op& op = it->second.front();
            top->sel = 1;
            top->we = op.write ? 1 : 0;
            top->reg_addr = op.reg & 0x0F;
            top->wdata = op.value;
            if (it->second.size() > 1)
                fprintf(stderr, "warning: multiple ops at cycle %llu; only first applied\n",
                        static_cast<unsigned long long>(k));
        }
        top->eval();
        top->clk = 1; top->eval();
        top->clk = 0; top->eval();

        const int irq = top->irq ? 1 : 0;
        const int pb7 = top->pb7_out ? 1 : 0;
        fprintf(out,
                "C %llu t1=%04X t2=%04X ifr=%02X ier=%02X pb7=%d pb6=%d irq=%d cb2=%d\n",
                static_cast<unsigned long long>(k),
                top->dbg_t1, top->dbg_t2, top->dbg_ifr, top->dbg_ier & 0x7F,
                pb7, top->dbg_pb6 ? 1 : 0, irq, top->cb2 ? 1 : 0);
    }

    fclose(out);
    top->final();
    delete top;
    return 0;
}
