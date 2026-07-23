# [National JR-100](https://en.wikipedia.org/wiki/Matsushita_JR_series) for [MiSTer Platform](https://github.com/MiSTer-devel/Main_MiSTer/wiki)

FPGA re-implementation of the National (Matsushita) JR-100 personal computer (1981).

*日本語版は [README.ja.md](README.ja.md) をご覧ください。*

## Features

- MB8861H CPU (MC6800 compatible + NIM/OIM/XIM/TMM/ADX extensions), cycle counts verified by instruction-boundary lockstep against the [pyjr100emu](https://github.com/zabaglione/pyjr100emu) reference emulator
- R6522 VIA (timers, shift register, PB7 sound, keyboard matrix scan) verified per-cycle against the reference
- 32x24 character display (256x192 mono), user-defined characters including the real-hardware shared-VRAM glyphs
- PS/2 keyboard (full 9x5 matrix), joystick on `$CC02` (active high)
- BEEP audio with output band limiting (VIA internals never stop)
- OSD loading of PROG containers (`.prg` v1/v2); convert BASIC text with `tools/bas2prg.py`
- Optional 16 KiB extended RAM at `4000-7FFF` (OSD, applied at reset)

Tested on SuperStation One (keyboard: ELECOM TK-FCM077PBK, controller: Xbox One).

## ROM

This repository contains **no ROM images**. Place a JR-100 BASIC ROM you legally own as an 8 KiB raw image (character ROM first 1 KiB, BASIC from offset `0400`) at:

```
/media/fat/games/JR100/boot.rom
```

If your ROM is a PROG container (`jr100rom.prg`), convert it once with:

```bash
python3 tools/prog2rom.py jr100rom.prg boot.rom
```

The core auto-loads `boot.rom` at start; the OSD "Load BASIC ROM" entry does the same manually. Never commit ROM images to this repository (`./scripts/setup-hooks.sh` installs a pre-commit guard).

## Loading programs

- `.prg` (PROG v1/v2 containers): OSD → "Load PRG". Binary sections load to their addresses; BASIC sections load at `0246` with workspace pointers set, ready for `LIST`/`RUN`.
- `.bas` (BASIC text): convert first with `python3 tools/bas2prg.py program.bas program.prg`.

## Build

The official build runs on GitHub Actions (`.github/workflows/build-core.yml`, Quartus 17.0 in a container). The identical local path is:

```bash
CONTAINER_RUNTIME=docker tools/compile_rbf.sh JR100
```

(Any OCI runtime works; on Apple Silicon the toolchain runs but is impractically slow under Rosetta — use CI.)

## Development & verification

Based on [Template_MiSTer](https://github.com/MiSTer-devel/Template_MiSTer); the `sys/` framework directory is unmodified. The behavioural reference is pyjr100emu, expected as a sibling checkout at `../jr100emu`. Development documents are written in Japanese:

- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — plan, environment, verification suites
- [docs/TRACE_FORMAT.md](docs/TRACE_FORMAT.md) — lockstep trace format
- [docs/BOOT_LOCKSTEP.md](docs/BOOT_LOCKSTEP.md) — boot comparison convention and M1 result
- [AGENTS.md](AGENTS.md) — requirements

Simulation (Verilator) covers CPU lockstep, VIA per-cycle vectors, boot-to-READY, frame rendering, joystick/PRG/audio acceptance: see the `tools/run_*` scripts.

## License

GPL-2.0 (see [LICENSE](LICENSE)), following the MiSTer framework. New HDL written for this core is GPL-2.0-or-later. Portions derived from the MIT-licensed pyjr100emu / [jr100-emulator-v2](https://github.com/kemusiro/jr100-emulator-v2) keep their attribution in file headers.
