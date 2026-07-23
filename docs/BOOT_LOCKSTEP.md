# M1 ブートロックステップ: 比較規約と判定基準

pyjr100emu 側調査（2026-07-23、MC6800一次資料に基づく）で確定した規約。M1「リセット後からREADY表示までのCPU状態、VIA状態、VRAMが参照実装と一致する」の判定に用いる。

## ブート比較開始境界（エポック）

> RESET処理が完了し、I=1、PCが `$FFFE/$FFFF` のベクタ値となり、最初の命令をまだ実行していない命令境界を開始点とする。この時点を `clk=0` とする。

- pyjr100emu の `computer.reset()` は**呼出し内で即時に**クロックとデバイスをリセットする。続く `tick(1)` は保留中のCPU RESETを確定（PC=ベクタ、I=1）し、命令を実行せず、VIAを1内部ティック進める
- この `reset(); tick(1)` は実機RESETシーケンス（RESET保持時間、2バイトのベクタ読出し、opcodeフェッチ）の1クロック再現**ではない**。比較エポックを作る操作である

## レジスタ初期値（ブート比較規約）

| フィールド | 値 | 根拠区分 |
|---|---:|---|
| A / B | `$00` | 比較用正規化（RESETで値が保証されない） |
| IX / SP | `$0000` | 比較用正規化（同上。`SP=$0000` は実機仕様ではない） |
| I | 1 | **RESET仕様**（MC6800はRESETシーケンス中にInterrupt Maskをセット） |
| H/N/Z/V/C | 0 | 比較用正規化 |
| CC | **`$D0`** | `11HINZVC` 形式で上記を合成 |
| PC | `memory[$FFFE]<<8 \| memory[$FFFF]` | RESET仕様（ビッグエンディアン） |

MB8861H固有のRESET差分は富士通一次資料で独立確認できていないため、MC6800互換部分へMC6800仕様を適用するプロジェクト方針に基づく。

## R6522 のRESET挙動

- RESETは内部レジスタをクリアするが、**T1/T2カウンタ・ラッチ・シフトレジスタは保持**する（Rockwell R6522データシート）
- コールドスタート（FPGA構成直後／Python新規構築）ではこれらの初期値が0のため、ブート開始境界では結果的に全て0
- **実行中のウォームリセット**では保持しなければならない。HDLは `rst` で保持し、電源投入初期値（0）はレジスタ初期化子で与える

## プログラムモードの補足規約

プログラムモード（`--program`/`--start`）はウォームアップ実行後にリセットするため、保持仕様のままではT1/T2にウォームアップ残滓が残る。比較規約として `reset()` 直後・確定 `tick(1)` の**前に** T1/T2カウンタ・ラッチ・SRを0へ正規化する（`_normalise_program_via_state`）。これによりコールド起動のDUTと位相が一致する。

## M1 判定基準

- TRACE_FORMAT v1 の**全フィールド**（CPU + VIA）とメモリダンプの一致をもって判定する
- **VIAフィールドの差分はM1達成と認めない**。`--cpu-only` は原因分類のための診断専用
- TRACE_FORMATに含まれない内部同期値のみの差分を許容する場合は、観測可能状態・IRQ・制御フロー・メモリへの無影響を証明し、別途承認を得る
- バス位置補正（VIA `delay` フック）は、実際の発散を確認し原因を特定してから、承認を得て着手する

## 実行手順

```bash
# 参照側（ROMパスは各自の環境。成果物は sim/work 固定 = 非コミット領域）
cd ../jr100emu && PYTHONPATH=src .venv/bin/python -m jr100emu.debug_runner \
  --boot --rom datas/jr100rom.prg --cycles 600000 \
  --trace ../jr100-core/sim/work/boot.ref.trace \
  --save-initial-memory ../jr100-core/sim/work/boot.img \
  --dump ../jr100-core/sim/work/boot.ref.dump \
  --dump-range 0000:03FF --dump-range C000:C3FF

# DUT側（PCはイメージのFFFE/FFFFから自動設定、CC=$D0/SP=0を適用）
sim/obj_dir/Vjr100_core --image sim/work/boot.img --boot --cycles 600000 \
  --trace sim/work/boot.dut.trace \
  --dump sim/work/boot.dut.dump --dump-range 0000:03FF --dump-range C000:C3FF

# 判定
python3 tools/trace_diff.py sim/work/boot.ref.trace sim/work/boot.dut.trace \
  --mem sim/work/boot.ref.dump sim/work/boot.dut.dump
```

READY到達クロックや入力待ちループPCはROM固有情報のため、コード・ドキュメントへ固定値として組み込まない（ローカル測定で運用）。

## M1 判定結果（2026-07-23）

- 600,000サイクル / **132,758サンプルが全フィールド一致**、メモリダンプ（`0000:03FF` + `C000:C3FF`）一致
- VRAMの所定位置に READY の表示コード列を確認
- 最終状態は要件定義書 §3.4 の期待値と一致（DDRA=`$1F`、DDRB=`$20`、キーボード走査動作中）
- **M1 受入条件達成**。READYまでの起動列では VIAアクセスタイミングモデル差（docs/DEVELOPMENT.md）による発散は発生しなかった
