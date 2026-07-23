# JR-100 for MiSTer

FPGA re-implementation of the National (Matsushita) JR-100 personal computer (1981) for the [MiSTer FPGA](https://mister-devel.github.io/MkDocs_MiSTer/) platform.

松下電器 JR-100 の MiSTer 用 FPGA コアです。

**Status: early development — not yet usable.**
現在は開発初期段階です。要件は [AGENTS.md](AGENTS.md)、開発計画は [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) を参照してください。

## ROM

This repository contains **no ROM images**. To use the core, place a JR-100 BASIC ROM image you legally own as `boot.rom` under `/media/fat/games/JR100/` on your MiSTer. Never commit ROM images to this repository (a pre-commit guard is provided — run `./scripts/setup-hooks.sh` once after cloning).

本リポジトリに ROM は含まれません。お手持ちの JR-100 BASIC ROM を `boot.rom` として `/media/fat/games/JR100/` に配置してください。

## Reference implementation

Behavioral reference is the `pyjr100emu` emulator (MIT), expected as a sibling checkout at `../jr100emu` by the verification tooling.

## Build

Quartus Prime 17.0.x, project file `JR100.qpf`. Based on [Template_MiSTer](https://github.com/MiSTer-devel/Template_MiSTer) (commit `69b8a2a`); the `sys/` framework directory is unmodified.

## License

GPL-2.0 (see [LICENSE](LICENSE)), following the MiSTer framework. New HDL written for this core is GPL-2.0-or-later. Portions derived from the MIT-licensed pyjr100emu / [jr100-emulator-v2](https://github.com/kemusiro/jr100-emulator-v2) keep their attribution in file headers.
