# National JR-100 for MiSTer（日本語）

松下電器（ナショナル）JR-100（1981年）の [MiSTer FPGA](https://github.com/MiSTer-devel/Main_MiSTer/wiki) 用コアです。

*English version: [README.md](README.md)*

## 特徴

- MB8861H CPU（MC6800互換 + NIM/OIM/XIM/TMM/ADX拡張命令）。参照エミュレータ [pyjr100emu](https://github.com/zabaglione/pyjr100emu) との命令境界ロックステップでサイクル数まで検証済み
- R6522 VIA（タイマ、シフトレジスタ、PB7サウンド、キーボード行列走査）をサイクル単位で参照実装と照合
- 32×24文字表示（256×192モノクロ）。ユーザー定義文字は実機のVRAM共有参照（0xA0-0xFF）まで実装
- PS/2キーボード（9×5行列全キー）、ジョイスティック（`$CC02`、active-high）
- BEEP音声（出力帯域制御つき。VIA内部動作は帯域制御の影響を受けません）
- OSDからのPROGコンテナ（`.prg` v1/v2）ロード。BASICテキストは `tools/bas2prg.py` で変換
- 拡張RAM 16KiB（`4000-7FFF`、OSD選択・リセット時反映）

SuperStation One で動作確認済み（キーボード: ELECOM TK-FCM077PBK、コントローラ: Xbox One）。

## ROMについて

本リポジトリに**ROMは含まれません**。お手持ちの正規なJR-100 BASIC ROMを、8KiB生イメージ（先頭1KiBが文字ROM、`0400` 以降がBASIC）として次の場所へ配置してください:

```
/media/fat/games/JR100/boot.rom
```

PROGコンテナ形式（`jr100rom.prg`）の場合は一度だけ変換します:

```bash
python3 tools/prog2rom.py jr100rom.prg boot.rom
```

コア起動時に `boot.rom` が自動ロードされます（OSDの「Load BASIC ROM」から手動選択も可能）。ROMイメージは絶対にコミットしないでください（`./scripts/setup-hooks.sh` で混入ガードを有効化できます）。

## プログラムのロード

- `.prg`（PROG v1/v2コンテナ）: OSD →「Load PRG」。バイナリセクションは指定アドレスへ、BASICセクションは `0246` へロードされワークポインタも設定済み（そのまま `LIST`/`RUN` 可能）
- `.bas`（BASICテキスト）: `python3 tools/bas2prg.py program.bas program.prg` で変換してからロード

## ビルド

正式ビルドは GitHub Actions（`.github/workflows/build-core.yml`、コンテナ内Quartus 17.0）です。同一手順のローカル実行:

```bash
CONTAINER_RUNTIME=docker tools/compile_rbf.sh JR100
```

（OCIランタイムなら何でも動作します。Apple SiliconではRosetta経由でツールは起動しますが実用外の速度のため、CIを推奨）

## 開発・検証

[Template_MiSTer](https://github.com/MiSTer-devel/Template_MiSTer) を基礎とし、`sys/` フレームワークは無改変です。互換性基準は pyjr100emu（同階層 `../jr100emu` にチェックアウト想定）。

- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — 開発計画・環境・検証スイート
- [docs/TRACE_FORMAT.md](docs/TRACE_FORMAT.md) — ロックステップトレース形式
- [docs/BOOT_LOCKSTEP.md](docs/BOOT_LOCKSTEP.md) — ブート比較規約とM1判定結果
- [AGENTS.md](AGENTS.md) — 要件定義書

Verilatorシミュレーションで、CPUロックステップ・VIAサイクル単位ベクタ・READY到達ブート・フレーム描画・ジョイスティック/PRG/音声の受入試験を網羅しています（`tools/run_*` 参照）。

## ライセンス

GPL-2.0（[LICENSE](LICENSE)、MiSTerフレームワークに準拠）。本コア向けの新規HDLは GPL-2.0-or-later。MITライセンスの pyjr100emu / [jr100-emulator-v2](https://github.com/kemusiro/jr100-emulator-v2) 由来の移植部分は各ファイルヘッダに帰属を記載しています。
