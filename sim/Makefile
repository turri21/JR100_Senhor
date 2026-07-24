# Verilator lockstep simulations for the JR-100 core.
#   Vmb8861     - CPU only (Phase C)
#   Vjr100_core - CPU + VIA + address decode (Phase D)

VERILATOR ?= verilator

CPU_RTL := ../rtl/cpu/mb8861.sv
SYS_RTL := ../rtl/cpu/mb8861.sv ../rtl/jr100/jr100_via.sv \
           ../rtl/jr100/jr100_video.sv ../rtl/jr100/jr100_core.sv

all: obj_dir/Vmb8861 obj_dir/Vjr100_core

obj_dir/Vmb8861: $(CPU_RTL) sim_main.cpp Makefile
	$(VERILATOR) --cc --exe --build -O2 --top-module mb8861 \
		-CFLAGS "-O2 -std=c++17" \
		$(CPU_RTL) sim_main.cpp -o Vmb8861

# -Wno-MULTIDRIVEN: jr100_via.sv intentionally updates VIA state from
# module-scope tasks with blocking assignments so the within-cycle
# ordering matches the pyjr100emu reference statement-for-statement.
obj_dir/Vjr100_core: $(SYS_RTL) sim_system.cpp Makefile
	$(VERILATOR) --cc --exe --build -O2 --top-module jr100_core \
		-Wno-MULTIDRIVEN \
		-CFLAGS "-O2 -std=c++17" \
		$(SYS_RTL) sim_system.cpp -o Vjr100_core

clean:
	rm -rf obj_dir

.PHONY: all clean

obj_dir/Vjr100_via: ../rtl/jr100/jr100_via.sv sim_via.cpp Makefile
	$(VERILATOR) --cc --exe --build -O2 --top-module jr100_via \
		-Wno-MULTIDRIVEN \
		-CFLAGS "-O2 -std=c++17" \
		../rtl/jr100/jr100_via.sv sim_via.cpp -o Vjr100_via

TOP_RTL := ../rtl/cpu/mb8861.sv ../rtl/jr100/jr100_via.sv \
           ../rtl/jr100/jr100_video.sv ../rtl/jr100/jr100_core.sv \
           ../rtl/jr100/jr100_mem.sv ../rtl/jr100/jr100_loader.sv \
           ../rtl/jr100/jr100_bas_loader.sv \
           ../rtl/jr100/jr100_saver.sv \
           ../rtl/jr100/jr100_top.sv

obj_dir/Vjr100_top: $(TOP_RTL) sim_top.cpp Makefile
	$(VERILATOR) --cc --exe --build -O2 --top-module jr100_top \
		-Wno-MULTIDRIVEN \
		-CFLAGS "-O2 -std=c++17" \
		$(TOP_RTL) sim_top.cpp -o Vjr100_top
