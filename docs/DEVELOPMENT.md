# 開発計画と環境方針

要件は [AGENTS.md](../AGENTS.md)（要件定義書 v1.4）を正とする。本書は開発プロセス側の計画を記す。

## 確定事項

| 項目 | 決定 |
|---|---|
| ライセンス | リポジトリ全体 GPL-2.0（Template_MiSTer に従う）。新規HDLは GPL-2.0-or-later。MIT由来の移植部はヘッダで帰属表記 |
| CPU | MB8861H を SystemVerilog で新規実装（既存 cpu68 は VHDL のため Verilator 非対応、かつ GPL-3.0 で不採用） |
| 合成環境 | **正式ビルド経路は GitHub Actions**（`.github/workflows/build-core.yml`、当面 `workflow_dispatch` 手動起動）。ローカル（Apple Container + Rosetta 2）は2026-07-23/24に検証済み: Quartus 17.0.2 の起動・全体のエラボレーション・論理合成はエラー0で進行するが、**スループットが実効0.1コア以下に劣化し完走は非実用**（19時間でも第1ステージ未完）。よってローカルはツールチェーン検証・緊急用にとどめ、合成はCIで行う。スクリプトはランタイム中立（`tools/compile_rbf.sh`、`CONTAINER_RUNTIME`）でCI/ローカル同一手順。**初回CIビルド実績（2026-07-24）: 全工程11分で成功**（イメージ取得込み、Cyclone V 5CSEBA6U23I7、`JR100.rbf` 2.4MB を artifact 保存） |
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
| B | M0 | ロックステップ比較基盤: `--trace`（命令境界トレース）、`tools/trace_diff.py`、意図的差分の検出確認 ✅ |
| C | M0→M1 | MB8861 CPU コアを `rtl/cpu/mb8861.sv` に新規実装 ✅（6800全命令 + 拡張5命令 + 割込み実装済み。maze系テスト6本・計約10.3万サンプルでCPU単体ロックステップ一致。割込み・WAI経路のロックステップ検証は未実施） |
| D | M1 | R6522 VIA（`rtl/jr100/jr100_via.sv`）とシステム統合（`rtl/jr100/jr100_core.sv`: アドレスデコード・ROM書き込み保護・拡張I/O）を実装 ✅。maze系6本を**VIA状態込み全フィールド**で一致確認。sound_scale.prg はCPU状態・メモリが13,900サンプル一致（タイマ位相のみ下記の既知モデル差）。**M1達成（2026-07-23）**: BASIC ROMブート照合で600,000サイクル・132,758サンプルが全フィールド一致、READY表示を確認（[BOOT_LOCKSTEP.md](BOOT_LOCKSTEP.md)）。表示パイプライン・キーボード実入力の検証は未着手 |
| E | M2 | 表示パイプライン `rtl/jr100/jr100_video.sv` 実装 ✅（文字ジェネレータ4種のグリフ源、VRAM共有CGRAM=実機仕様対応。ブート後READY画面がPython表示モデルと**画素完全一致**。フレームタイミングは暫定でM2のHDMI出力時に実機仕様へ調整）。CPU実リセットシーケンス実装 ✅（`vector_reset`: FFFE/FFFF ベクタフェッチ+I=1）。**実コア構造 `jr100_top` 検証済み ✅**: BRAM同期読み出しメモリ（`jr100_mem`）、実機比率クロックイネーブル（システムクロック÷64=CPU、÷8=ピクセル）、ローダ経由の8KiB ROM分割ロード（文字ROM/BASIC ROM）、ベクタリセット起動——この構造のままM1ブート照合（132,758サンプル）・メモリ・READYフレームが全一致（`Vjr100_top`、エポック調整付き）。`emu` ラッパ実装 ✅（`JR100.sv`: CONF_STR/`hps_io`/`ioctl`→ローダ/映像/音声スタブ、PLL 57.272727MHz、PS/2→行列変換 `jr100_keyboard.sv`）。**JR-100コア本体のCI合成成功（2026-07-24）**: `JR100.rbf` 2.57MB、ALM 21%・BRAM 11%・タイミング違反0。Quartus 17.0固有の非対応構文（関数呼出し結果へのビット選択）は修正済み。**M2達成（2026-07-24、SuperStation One実機）**: `boot.rom` 自動ロード→HDMIにREADY表示を確認。あわせてキーボード動作（CTRL+キーのショートカット表示、SHIFT文字、CTRL+VでGRAPHモード移行・セミグラフィック表示）とBEEP音（生PB7スタブ）も実機確認済み — M3の主要部とM4音声の素通し動作を先行確認 |
| F | M3/M4 | **完了（2026-07-24）**: キーボード実機確認、`joystick_0`→`0xCC02`（受入12パターン）、OSD PRGロード（RTLストリーミングパーサ、受入7ファイル）、`.bas`はOSD直接ロード（`jr100_bas_loader.sv`＝`load_basic_text`準拠のストリーミングパーサ、受入6ファイルで参照実装とバイト一致。不正行はスキップする best-effort 動作のみ参照実装＝ファイル全体拒否と相違、正当なファイルは同一）、音声出力帯域制御（帯域内周期一致/帯域外無音+VIA継続）、CPU割込み/WAI経路のゴールデンベクタ検証（5シナリオ、Iフラグ退避順の実バグを検出修正）、拡張RAM 4000-7FFF（OSD・リセット時ラッチ）。カセットFSKはOSDロード置換方針どおり非実装。**M4実機受入確認（2026-07-24）**: OSDからSTARFIRE.prgをロードし `A=USR($D00)` で起動・キーボードプレイ成功（SuperStation One + ELECOM TK-FCM077PBK + Xbox Oneコントローラ） |
| G | M5 | 公開準備: README最終化・スクラブ（ツリー内個人情報/ROM混入なし確認済み）。**public化はユーザー承認待ち**。コミット履歴のメールアドレス（gmail、24件）の扱いが唯一の残決定事項 |

## 参照実装の実機仕様との差異（追跡リスト）

HDLは互換性基準である pyjr100emu の挙動を忠実に写している（AGENTS.md §1）。以下は精読で判明した、6800/MB8861 の一次資料と食い違う可能性がある参照実装の挙動である。AGENTS.md §7 のとおり黙って吸収せず、ここで追跡する。修正する場合は ①一次資料で実機仕様を確認 → ②Python修正+回帰テスト → ③HDL追随 の順で両側を同時に変える。

| # | 項目 | pyjr100emu（=現HDL）の挙動 | 一次資料上の期待 | 状態 |
|---|---|---|---|---|
| 1 | ORAB ext (0xFA) | OR を実行 | ORAB は OR | **解決**（pyjr100emu `9b11a18` で修正、HDL追随） |
| 2 | NEG の C フラグ | C = (オペランド ≠ 0) | 同左 | **解決**（同上） |
| 3 | NMI/IRQ エントリ | I フラグをセットする。IRQ はレベルセンシティブ入力 | 同左 | **解決**（同上。あわせて WAI は命令実行時にレジスタ退避し、WAI 経由の割込みエントリは退避なし4サイクルに変更） |
| 4 | SWI の戻りアドレス | opcode+2 を push | opcode+1（次命令） | **一次資料確認済・要修正** |
| 5 | ADC の H フラグ | キャリー入力を半桁計算に含めない | 含める | **一次資料確認済・要修正** |
| 6 | STS のフラグ | N/Z を **IX** から設定 | SP から設定 | **一次資料確認済・要修正** |
| 7 | NIM/OIM/XIM の N | N = (結果 ≠ 0)（bit7ではない） | 同左（MB8861 固有仕様） | **解決（実装が正しい）** |
| 8 | XIM の V | V を更新しない（NIM/OIM は V=0) | 同左（MB8861 固有仕様） | **解決（実装が正しい）** |
| 9 | TMM のフラグ条件 | Bp=0 または **M=0** → Z、**M=$FF** → V、他は N | Bp=0 または **(M∧Bp)=0** → Z、**(M∧Bp)=Bp** → V、他は N（マスクビットで判定） | 未解決（要一次資料） |

### 一次資料調査の結果（2026-07-24）

**#4/#5/#6 — Motorola "M6800 Programming Reference Manual" M68PRM(D), Nov 1976（bitsavers/archive.org）で確認:**

- **#4 SWI**: §3.3.3「The value saved for the program counter is the address of the SWI instruction, plus one.」付録の動作記述も `PC ← (PC)+0001` → push（PC は opcode 位置基準）。実装は fetch 後にさらに +1 しており opcode+2 を積む。1バイトずれのため SWI を使うソフトの RTI 復帰が壊れる（JR-100 BASIC ROM 起動列では未使用のため実害未観測）。
- **#5 ADC**: 付録 ADC 頁「H: Set if there was a carry from bit 3」、演算は `ACCX + M + C`。ブール式 `H = X3·M3 + M3·R̄3 + R̄3·X3` は結果ビット R3（キャリー入力込み）を含む。実装は `(X&$0F)+(M&$0F)>$0F` のみで、`(X&$0F)+(M&$0F)=$0F` かつ C=1 のとき実機 H=1 / 実装 H=0 に発散。DAA を併用する BCD 演算に影響。
- **#6 STS**: 付録 STS 頁「N: Set if the most significant bit of **the stack pointer** is set」「Z: Set if all bits of **the stack pointer** are cleared」、ブール式 `N = SPH7`。実装は IX から N/Z を設定しており誤り（V=0 は正しい）。
- 修正手順は本節冒頭のとおり ①Python 修正+回帰テスト → ②HDL 追随 → ③ロックステップ再照合。Python 側は参照実装（pyjr100emu / Java 原典 jr100-emulator-v2 とも同一挙動）の修正判断が必要。

**#7/#8 — MB8861 追加命令の資料（Fujitsu MB8861 解説, nkomatsu 氏 IC Collection）で確認:**

- NIM/OIM/XIM は Z/N のみ影響し「演算結果が 0 になれば Z セット・N リセット、0 以外なら Z リセット・N セット」（通常の N=bit7 と異なる旨も明記）。NIM/OIM は V リセット、**XIM は V 不変**。H/C は全て不変。→ **参照実装（=現HDL）の挙動どおり**。#7/#8 は「一次資料との食い違い」ではなく MB8861 固有仕様と確認。
- 原典一次資料: 星川竜輔他「MB8861 8ビットマイクロプロセッサ」FUJITSU Vol.27 No.5 pp.67-87 (1976)。MB8871 データシート転載が国会図書館デジタルコレクション「マイコン手づくり塾」に収録との情報あり（未閲覧）。

**#9（新規）— TMM のフラグ条件:** 上記資料は「Bp のマスクビットに対応するオペランドビットが全て 0 → Z セット」「全て 1 → V セット」とマスク後の判定を記述する。実装（Java→Python→HDL 共通）はメモリバイト全体で `M=0` / `M=$FF` を判定しており、部分マスク時に相違（例: Bp=$01, M=$01 → 資料 V=1 / 実装 N=1）。nkomatsu 氏の解説は二次資料のため、修正前に上記一次資料（FUJITSU 誌または MB8871 データシート）での確認を要する。

割込み・WAI の新挙動（I フラグ、レベル IRQ、WAI 退避、4サイクル退出）は Python 側テストで検証済みだが、HDL 側のロックステップはまだ迷路系（割込み非使用）のみ。

VIA 単体のサイクル単位検証（計画書 §5.2）は `tools/run_via_tests.sh` で実施済み: `tests/via/*.scn` の共通シナリオを pyjr100emu 由来のゴールデンベクタ（`tools/gen_via_vectors.py`）と Verilator 単体シミュレーション（`Vjr100_via`)で実行し、**サイクル毎の t1/t2/IFR/IER/PB7/PB6/IRQ が4シナリオ全て厳密一致**（T1ワンショット、BEEPチェーン=T1モード3+PB7→PB6ジャンパ+T2パルスカウント、IER/IFRゲーティング、SRシフト）。CPU割込み・WAI経路は `tools/run_cpu_irq_tests.py`（境界サイクルIRQ/NMI注入、Python直駆動ゴールデン）で5シナリオ検証済み（Iフラグ退避順の実バグを検出・修正）。

### VIA アクセスのタイミングモデル差（既知の制約）

Python 版は命令一括実行の設計上、CPU からの VIA アクセスを**命令開始時点**で適用する。HDL は実際のバスサイクル時点で適用するため、タイマの書き込み・カウンタ読出しには命令内オフセットが生じる。

- 実測（sound_scale.prg）: `STAA ext` による T1CH 書き込みで ref `t1=00A8` / dut `t1=00AC`（4サイクル差）。**CPU 状態とメモリは 13,900 サンプル完全一致**で、差はタイマ位相に封じ込められている
- 方針: 計画書 §5.2 のとおり、VIA タイマ・IRQ の検証は専用のサイクル単位試験で行う。バス位置補正（VIA `delay` フック）は実際の発散を確認し承認を得てから着手する
- M1 実測: BASIC ブート（リセット→READY、600,000サイクル）は本制約に該当する発散なしで全フィールド一致（[BOOT_LOCKSTEP.md](BOOT_LOCKSTEP.md)）

## テスト実行

- 本リポジトリ（tools等のPythonユーティリティ）: `python3 -m unittest discover -s tests`
- 参照実装側: `cd ../jr100emu && .venv/bin/python -m pytest tests/unit`
- トレース生成例: `PYTHONPATH=src python -m jr100emu.debug_runner --program datas/maze_init_test.prg --start 0x0300 --cycles 20000 --trace ref.trace`（形式は [TRACE_FORMAT.md](TRACE_FORMAT.md)）
- トレース比較: `python3 tools/trace_diff.py ref.trace dut.trace [--cpu-only] [--mem ref.dump dut.dump]`
- CPU単体ロックステップ一括実行: `tools/run_lockstep.sh datas/maze_init_test.prg 20000`（Verilatorビルド込み。プログラムは pyjr100emu チェックアウト相対）
- フレーム検証: DUTに `--frame out.pgm` を付けて実行し、`python3 tools/render_reference.py --image <img> --dump <dump> --out ref.pgm` と `cmp` で画素比較
- 合成（要Quartusコンテナ）: `tools/compile_rbf.sh JR100`（`CONTAINER_RUNTIME` で container/podman/docker 切替。ソースをVMローカルへコピーして実行）
- CPUサイクル表の再抽出: `python3 tools/dump_opcode_table.py > docs/generated/opcode_cycles.txt`

## 検証方針

- 各フェーズで Verilator テストとロックステップ差分ゼロを確認してから次へ進む
- M2 以降で見つかった実機差異は、まず M0 の回帰テストへ追加してから修正する（要件定義書 §6）
- 最初のロックステップ入力: pyjr100emu `datas/` の `maze_*.prg`、`sound_scale.prg`、`doremi_scale.bas`、`twinkle_star.bas` + ジョイスティック最小テスト

## リポジトリ運用

- ROM・個人環境情報はコミットしない。clone 後に `./scripts/setup-hooks.sh` を一度実行し、pre-commit ガードを有効化する
- 受入スイート: `tools/run_lockstep.sh` / `run_via_tests.sh` / `run_joy_tests.py` / `run_prg_load_test.py` / `run_audio_tests.py` / `run_cpu_irq_tests.py`
