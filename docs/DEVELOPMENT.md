# 開発計画と環境方針

要件は [AGENTS.md](../AGENTS.md)（要件定義書 v1.4）を正とする。本書は開発プロセス側の計画を記す。

## 確定事項

| 項目 | 決定 |
|---|---|
| ライセンス | リポジトリ全体 GPL-2.0（Template_MiSTer に従う）。新規HDLは GPL-2.0-or-later。MIT由来の移植部はヘッダで帰属表記 |
| CPU | MB8861H を SystemVerilog で新規実装（既存 cpu68 は VHDL のため Verilator 非対応、かつ GPL-3.0 で不採用） |
| 合成環境 | Mac 上 devcontainer（[MiSTer公式ドキュメント](https://mister-devel.github.io/MkDocs_MiSTer/developer/mistercompile/)記載。Quartus 17.0.2、RAM 8GB推奨）。M2着手前に動作検証し、不成立なら GitHub Actions（raetro/quartus Docker）へ切替 |
| ベース | [Template_MiSTer](https://github.com/MiSTer-devel/Template_MiSTer) commit `69b8a2a`。`sys/` は無改変維持 |
| 参照実装 | pyjr100emu。既定で同階層 `../jr100emu` にチェックアウト（検証ツール側で環境変数により上書き可能にする予定） |

## 開発機（macOS）でできる／できない作業

- **Macで完結**: HDL記述、Verilator + C++/SV テストベンチ、Python参照実装の実行・改修、命令境界トレース差分比較、ドキュメント、`.rbf` の実機転送（SSH/SCP）、実機動作確認
- **Macネイティブ不可**: Quartus合成 → devcontainer（x86エミュレーション）で代替。所要時間は未計測のため M2 前に検証する
- 要件定義書 §6 のとおり **M0/M1 合格まで Quartus には着手しない**

## フェーズ計画

| Phase | マイルストーン | 内容 |
|---|---|---|
| A | — | リポジトリ立ち上げ（Template展開、ROM混入ガード、ドキュメント整備）✅ |
| B | M0 | ロックステップ比較基盤: pyjr100emu 側に命令境界トレース出力を新設（§8.1 の修正を含む）、本リポジトリ `sim/` に Verilator ハーネス、`tools/` に差分比較ツール |
| C | M0→M1 | MB8861 CPU コアを `rtl/cpu/` に新規実装。6800全命令 + 拡張5命令、割込み、未定義op=1クロックNOP、サイクル数は技術資料準拠 |
| D | M1 | システム統合シミュレーション: メモリマップ（BRAM）、R6522 VIA、キーボード9×5行列、表示（32×24・256×192・モノクロ・VRAM共有CGRAM）、`0xCC02` ジョイスティック、音声（Timer 1 + 出力帯域制御）。受入: リセット→READY まで参照実装と一致 |
| E | M2 | devcontainer 検証 → `emu`/`CONF_STR`/`hps_io`/`ioctl_*` 接続 → 初回合成 → 実機で BASIC 画面表示 |
| F | M3/M4 | PS/2入力で BASIC の入力・LIST・RUN、`joystick_0`→`0xCC02` 変換、入力・音声受入試験、OSD からの PRG/BAS ロード |
| G | M5 | README整備、公開前スクラブ（個人情報・ROM・git履歴）、public化、`.rbf` リリース |

## テスト実行

- 本リポジトリ（tools等のPythonユーティリティ）: `python3 -m unittest discover -s tests`
- 参照実装側: `cd ../jr100emu && .venv/bin/python -m pytest tests/unit`
- トレース生成例: `PYTHONPATH=src python -m jr100emu.debug_runner --program datas/maze_init_test.prg --start 0x0300 --cycles 20000 --trace ref.trace`（形式は [TRACE_FORMAT.md](TRACE_FORMAT.md)）
- トレース比較: `python3 tools/trace_diff.py ref.trace dut.trace [--mem ref.dump dut.dump]`

## 検証方針

- 各フェーズで Verilator テストとロックステップ差分ゼロを確認してから次へ進む
- M2 以降で見つかった実機差異は、まず M0 の回帰テストへ追加してから修正する（要件定義書 §6）
- 最初のロックステップ入力: pyjr100emu `datas/` の `maze_*.prg`、`sound_scale.prg`、`doremi_scale.bas`、`twinkle_star.bas` + ジョイスティック最小テスト

## リポジトリ運用

- ROM・個人環境情報はコミットしない。clone 後に `./scripts/setup-hooks.sh` を一度実行し、pre-commit ガードを有効化する
- `rtl/` のテンプレートデモコア（`mycore.v` ほか）は、初回合成のスモークテストが済むまで残す
