# Verilator lockstep simulation for the MB8861 CPU core.
# Usage: make -C sim && sim/obj_dir/Vmb8861 --image mem.bin --pc 0300 ...

VERILATOR ?= verilator

RTL := ../rtl/cpu/mb8861.sv

all: obj_dir/Vmb8861

obj_dir/Vmb8861: $(RTL) sim_main.cpp Makefile
	$(VERILATOR) --cc --exe --build -O2 --top-module mb8861 \
		-CFLAGS "-O2 -std=c++17" \
		$(RTL) sim_main.cpp -o Vmb8861

clean:
	rm -rf obj_dir

.PHONY: all clean
