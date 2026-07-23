# JR-100 MiSTer コア開発 要件定義書

- 版: 1.4（2026-07-23）
- 状態: 参照実装・同梱資料・JR-100技術資料・MiSTer公式開発資料による確定版。参照実装との差異は実機仕様とPython互換仕様を分けて記録する。
- 対応表: [`docs/referent-table-jr100-mister-core.md`](docs/referent-table-jr100-mister-core.md)
- 対応表SHA-256: `c5adb7e35628cb593cdec9fef37c69c1bbd34c79b62d6becd06ce7f361b3ceff`

## 1. 目的と成果物

松下電器 JR-100 を、MiSTer標準フレームワークで動作する Cyclone V 向け FPGA コアとして新規実装する。第一ターゲットは SuperStation One とし、DE10-Nano で動作する MiSTer 標準インターフェースだけを使用する。機種固有のSS1対応は実装しない。

成果物は以下とする。

- MiSTerが読み込む `.rbf` ファイル
- HDL、シミュレーション用テストベンチ、比較ツール、ビルド定義を含むソース一式
- ROM入手・配置とプログラムロードを説明するREADME

参照実装は別リポジトリの Python 版 `pyjr100emu` とする（既定では本リポジトリと同階層の `../jr100emu` にチェックアウトして参照する）。Python版が実装している挙動は、HDL化時の互換性基準とする。ただし、Python版内で矛盾する値または未実装の部分を実機仕様とみなしてはならない。実機の事実は、[JR-100技術資料](https://asamomiji.jp/contents/documents/retropc/jr100)と国内版資料に基づく。

JR-100U公式操作説明書は海外出荷版の資料であるため、国内版と食い違う項目の決定根拠には使わない。32×24表示、16 KiB RAM、8 KiB ROM、CGRAM、VRAM、VIA、600ボーFSKカセットなど、国内版資料と一致する共通仕様の相互確認にのみ用いる。CPUはJR-100U資料がMN1800・890 kHzと記すが、国内版のCPUはMB8861Hとして確定する。

## 2. 参照実装の現状

CPU、メモリ、VIA、画面、キーボード、ジョイスティック、BASIC/PROGローダ、Pygame音声、ヘッドレス実行器が実装されている。`datas/` にはBASIC、PROG、迷路テスト、音階プログラムなどの検証入力がある。BASIC ROMの候補ファイル `datas/jr100rom.prg` は作業ツリーに存在するが、Git管理対象ではない。

ヘッドレス実行器は、ROMと `.prg`/`.prog`/`.bas` をロードし、開始PC、終了PC、実行サイクル、メモリ範囲を指定してメモリダンプできる。一方で、CPU・VIAレジスタを命令ごとに出力するトレース形式は未実装である。従って、ロックステップ検証の前提となるトレース出力は本コア開発で新設する。

この環境では `python3 -m pytest` を実行したが、`pytest` が未導入のためテスト実行はできなかった。本文書の「実装済み」はソースとテスト記述を読んだ結果であり、今回の実行による合格確認ではない。

## 3. 参照実装準拠のハードウェア定義

### 3.1 CPU

| 項目 | HDLで採用する定義 | 根拠 |
|---|---|---|
| CPU | 富士通MB8861H。MC6800ハードウェア互換、独自5命令を持つ | [JR-100技術資料](https://asamomiji.jp/contents/documents/retropc/jr100)、利用者の確定判断 |
| レジスタ | A、B、IX、SP、PC、CCR（H/I/N/Z/V/C） | 同上 |
| 割込み | reset、NMI、IRQ、WAI、RTI、RTS、SWIを実装する | 同上 |
| 拡張命令 | ADX、NIM、OIM、XIM、TMMを実装する | 同上 |
| 拡張命令のopcode/サイクル | NIM indexed=`71`/8、OIM indexed=`72`/8、XIM indexed=`75`/8、TMM indexed=`7B`/7、ADX extended=`FC`/7 | 技術資料とPython実装が一致 |
| ADX immediate | opcode=`EC`、4サイクル | 実機資料および利用者の確定判断。Python実装も4サイクルへ修正する |
| 未定義opcode | 1クロックのNOPとして扱う | `MB8861.execute()` |

既存の6800 HDLコアを基底に利用してよい。ただし、上表の拡張命令、割込み時のスタック順序、未定義opcode処理、命令サイクルが参照実装と一致することを受入条件とする。CPUクロックは14.31818 MHzを16分周した894,886.25 Hz（資料上の表記は894 kHz）とする。

### 3.2 アドレス空間

| アドレス | 長さ | 参照実装の割当て | HDL要件 |
|---|---:|---|---|
| `0x0000–0x3FFF` | 16 KiB | 標準Main RAM | BRAMに実装する |
| `0x4000–0x7FFF` | 16 KiB | `extended_ram=True` 時だけMain RAM | 初期版では無効でよい。実装する場合はOSDで明示選択可能にする |
| `0xC000–0xC0FF` | 256 B | 32文字分のユーザー定義文字RAM | BRAMに実装する |
| `0xC100–0xC3FF` | 768 B | 32×24文字のVRAM | BRAMに実装する |
| `0xC800–0xC80F` | 16 B | R6522互換VIAレジスタ | VIAを実装する |
| `0xCC02` | 1 B | ジョイスティック・インターフェースの読み出しポート | 初期版で実装する。bit 0=右、bit 1=左、bit 2=上、bit 3=下、bit 4=スイッチ、bit 5–7=0、すべてactive-high。無入力時は`0x00`とする |
| `0xE000–0xE3FF` | 1 KiB | キャラクタビットマップROM | 8 KiB ROMイメージから分離して読み出す |
| `0xE400–0xFFFF` | 7 KiB | JR-BASIC ROM | ユーザー供給ROMをBRAMへロードする |

実機は`0x8000–0xBFFF`に拡張ROM、`0xD000–0xD7FF`にプリンタ制御ROM、`0xD800–0xDFFF`に増設機器用ROMを割り当てる。初期版は拡張BOXのROMを対象外とする。ジョイスティックは実機拡張回路との完全一致を現時点の目標にせず、Java版および修正済みPython版のactive-highな`0xCC02`読出し仕様を互換要件とする。

### 3.3 表示

画面は32×24文字、論理解像度256×192ピクセルである。文字ROMは`0xE000–0xE3FF`の1 KiBで、5×7ドット文字64種と8×8ドットのセミグラフィック文字64種を持つ。表示コード`0x80–0xFF`は、Port B bit 5により反転文字またはユーザー定義文字として表示する。

専用CGRAMは`0xC000–0xC0FF`の256 Bで、8バイト×32文字を定義する。実機はさらにVRAM `0xC100–0xC3FF` と同じ物理データを96文字分のユーザー定義文字として参照できる。この共有は、VRAMを書き換えると該当文字の字形も変わる実機挙動である。HDLではこの共有参照を実装する。Python版の表示クラスは128文字分のCGRAM配列を持つが、メモリマップから更新できるのは先頭32文字だけであり、実機の共有参照は未実装である。

HDLは、VRAMとフォントRAM/ROMから毎ピクセル文字ビットを生成してMiSTerのビデオパイプラインに渡す。Python版は黒背景・白前景のみを生成しているため、初期版の映像はモノクロとする。アスペクト比、スケーリング、出力同期はMiSTer標準フレームワークの設定に従う。

### 3.4 VIA、キーボード、音声

VIAは `0xC800` 起点のR6522レジスタ16本を持ち、Timer 1、Timer 2、シフトレジスタ、CA/CB端子、IFR/IERを実装する。IRQはIFRとIERの有効ビットからCPU IRQへ接続する。

JR-100固有の接続は次のとおりである。

- Port Aの下位4ビットでキーボード行を選択する。
- Port B下位5ビットは選択行のキー状態をactive-lowで返す。Python版の内部行列は押下を1で保持し、VIA読み出し時に反転する。
- キーボードは9行×5ビットである。PCキーマップの完全な対応は pyjr100emu の `src/jr100emu/app.py` にある `KEY_MATRIX_MAP` を正とする。
- Port B bit 5はフォント面切替に用いる。
- Port B bit 7の入力をbit 6へ反映するPB7/PB6ジャンパ接続を再現する。
- Timer 1をPB7矩形波出力モード（BASIC ROMはACR=`0xE0`を使用）で開始した時、周波数は `894886.25 / (timer1 + 2) / 2` Hz となる。PB7出力はPB6入力へ接続され、Timer 2はPB6の立下りを数える。これによりBEEP文の鳴動時間を制御する。Python版はPB7/PB6接続と周波数式を実装するが、Timer 2による実機BEEP時間までの検証は追加対象とする。

ROM BASIC初期化後のVIAデータ方向は、DDRA=`0x1F`、DDRB=`0x20`である。キーボード走査はORAのbit 3–0へ0–8を出力し、IRBのbit 4–0を読む。キー未押下は1、押下は0である。これはPython版の9×5行列と一致する。

HDLの音声は、上記Timer 1の状態から1bitまたはPCMの単音出力を生成し、MiSTer標準の音声出力へ接続する。Timer 1、PB7、PB6、Timer 2はCPUクロック基準の内部信号として常に更新し、音声出力の都合で停止、丸め、置換してはならない。

音声出力帯域制御は、VIA内部信号を生成した後、MiSTer音声出力へ渡す境界にだけ置く。選択したPCMサンプルレートのナイキスト周波数以上となるTimer 1矩形波は無音として出力するか、可聴域へ折り返さないローパス処理を行う。Timer 1の値が0のように出力帯域を大幅に超える場合も、PB7/PB6の遷移とTimer 2のカウントは継続する。Pygame用の44.1 kHz PCM生成、バッファ長、および初回再生遅延は移植対象外である。

### 3.5 ROMとプログラム

BASIC ROMはリポジトリへ含めない。READMEではユーザーが権利を持つROMを `boot.rom` としてコアのゲームディレクトリに配置するよう案内する。MiSTerの標準ディレクトリは `/media/fat/games/<CORE>` である。

ROM、`.prg`、`.prog`、`.bas` はOSDから選択する。MiSTerの `CONF_STR` にファイル選択項目を定義し、`hps_io` が提供する `ioctl_download`、`ioctl_wr`、`ioctl_addr`、`ioctl_dout` を使ってHPSからBRAMへ転送する。`.prg` はPython版と同じPROGコンテナとして解析する。`.bas` はPython版の `BasicLoader` と同じ、ROM BASICが要求するメモリ内容とポインタ更新の手順をHDL側またはロード制御側で再現する。

カセットは600ボー、FSK 1200 Hz（スペース）/2400 Hz（マーク）である。初期版ではその実時間入出力を実装せず、OSDロードで置き換える。これは削除ではなく、ロード手段を置き換える互換性方針である。

## 4. MiSTer統合要件

リポジトリは `Template_MiSTer` の構成を基礎とする。MiSTerが利用するコア側モジュール名は `emu`、OSD構成は `CONF_STR`、HPSとの入出力は `hps_io` とする。SDRAMコントローラは接続しない。上記のRAM、VRAM、CGRAM、ROMをCyclone Vの内蔵BRAMだけで実装する。

PS/2キーボード入力はMiSTerフレームワークから受け、対応する9×5行列の押下/解放状態へ変換する。初期版で使用するOSD項目は、ROM選択、PRG/BAS選択、リセット、必要であれば拡張RAMの有効化に限る。

MiSTerのホスト側ゲームコントローラは`hps_io`の`joystick_0`で受け、次の組み合わせ回路で`0xCC02`へ変換する。SDL/Pygame固有のaxis、hat、button番号や機種別マッピングはHPS側の責務であり、HDLへ移植しない。

| JR-100 `0xCC02` | 意味 | MiSTer入力 |
|---:|---|---|
| bit 0 | 右 | `joystick_0[0]` |
| bit 1 | 左 | `joystick_0[1]` |
| bit 2 | 上 | `joystick_0[3]` |
| bit 3 | 下 | `joystick_0[2]` |
| bit 4 | スイッチ | `joystick_0[4]` |
| bit 5–7 | 未使用 | `3'b000` |

`CONF_STR`では最初のジョイスティックボタンをスイッチとして宣言する。表示名は`Fire`とし、`J,Fire;`を使用する。入力を何も受けていない時の`0xCC02`は`0x00`でなければならない。

HPSファイル転送および `CONF_STR` の仕様は [MiSTer公式 `hps_io` 資料](https://mister-devel.github.io/MkDocs_MiSTer/developer/hps_io/) と [Core Configuration String資料](https://mister-devel.github.io/MkDocs_MiSTer/developer/conf_str/) を正とする。

## 5. 開発と検証

### 5.1 開発環境

| 工程 | 確定した手段 |
|---|---|
| HDLシミュレーション | Mac上のVerilatorとC++またはSystemVerilogテストベンチ |
| 参照側の実行 | `PYTHONPATH=src python3 -m jr100emu.debug_runner` |
| FPGA合成 | Cyclone Vを対象にできるQuartus環境。OSはツールが動作する環境を採用する |
| 実機配置 | `.rbf`をMiSTerのコア配置先へコピーする。転送手段はSSH/SCPまたはSambaでよい |

「Quartus Prime LiteのmacOS版は存在しない」および「GitHub ActionsでQuartus合成できる」は、本調査で一次資料により確認できていない。そのため必須要件には含めない。

### 5.2 ロックステップ検証

HDLの実装より先に、命令境界トレースと差分比較を実装する。比較入力は同一のROM、PRG/BAS、初期レジスタ、初期RAMとし、以下を記録する。

- 実行済み命令数、PC、A、B、IX、SP、CCR、累積クロック
- VIAのORA/ORB、DDRA/DDRB、ACR/PCR、Timer 1/2、IFR/IER、SR
- 指定範囲のメモリ（最低でもVRAM、CGRAM、テストプログラム領域）

通常の比較単位は命令完了直後とする。VIAタイマやIRQのテストだけは、クロック数と各サイクルでの可視状態も比較する。Python版は命令をまとめて実行する設計であり、現時点でバスサイクル波形の参照にはならないため、HDLの各バスサイクルをPython版へ強制的に一致させることは要件にしない。

最初の入力には `datas/maze_init_test.prg`、`datas/maze_*.prg`、`datas/sound_scale.prg`、`datas/doremi_scale.bas`、`datas/twinkle_star.bas` と、ジョイスティック入力を読み出す最小テストプログラムを使う。BASIC ROMを使うテストは、利用者が正規に用意した同一ROMを両方へ与える。

入力・音声受入試験は特定のゲームへ依存させず、次の値をテストベンチから直接与える。

- ジョイスティックは無入力、右、左、上、下、各斜め方向、スイッチ単独、方向とスイッチの同時入力、押下保持、解放を検証する。無入力時は`0x00`、各入力時は対応するbitだけがactive-highになることを確認する。
- 音声は可聴帯域内の代表的なTimer 1値、停止状態、出力帯域外となるTimer 1値を検証する。可聴帯域内では期待周波数を出力し、出力帯域外では可聴域への折り返し音を出さないことを確認する。
- 出力帯域外の音声試験でも、Timer 1、PB7、PB6、Timer 2、IFRが音声出力帯域制御の影響を受けず、期待するクロック数で遷移することを確認する。

## 6. マイルストーンと受入条件

| # | 到達条件 | 受入条件 |
|---|---|---|
| M0 | 比較基盤完成 | Python側とVerilator側が同じ命令境界トレースを出し、意図的な差分を検出できる |
| M1 | BASIC ROM起動 | リセット後からREADY表示までのCPU状態、VIA状態、VRAMが参照実装と一致する |
| M2 | MiSTer統合 | `.rbf`を実機へ配置し、HDMIでM1と同じBASIC画面を表示する |
| M3 | 入力 | PS/2入力でBASICの入力、LIST、RUNが動作する。ジョイスティックの無入力、各方向、同時方向、スイッチ、押下保持、解放が`0xCC02`のactive-high定義に一致する |
| M4 | 音声・ロード | 可聴帯域内のTimer 1音程、帯域外信号の無音化、帯域制御中も継続するVIA内部状態、OSDのPRG/BASロード、既存PRGの実行を確認する |
| M5 | 公開準備 | ROM非同梱、README、ライセンス、再現可能なビルド手順を確認する |

M0とM1が合格するまでQuartus合成と実機デバッグを開始しない。M2以降の実機差異は、まずM0の回帰テストへ追加してから修正する。

## 7. 未解決事項と、着手前に必要な確認

以下は資料と実装で確認できた差異であり、実装時に黙って吸収してはならない。

| 項目 | 確認できた事実 | 要求する判断または資料 |
|---|---|---|
| VRAM共有CGRAM | 実機はVRAMを96文字の字形データとしても参照する。Python版は未実装 | HDLで実装し、Python側のロックステップ比較では専用CGRAMの32文字とVRAMを別項目として比較する |
| BASIC ROMのロード境界 | 実機は文字ROM 1 KiBとBASIC ROM 7 KiBを分ける。Python版は8 KiB全体をBASIC ROMとして読む | OSDで8 KiBイメージを受け、`E000–E3FF`を文字ROM、`E400–FFFF`をBASIC ROMへ割り当てる |
| ライセンス | 現リポジトリはMIT | 新規HDLリポジトリのライセンスと、流用するCPU/VIA HDLのライセンス互換性 |

上記は実装時の差分管理対象である。ライセンス以外に、M0を開始するための未解決ハードウェア仕様は残っていない。

## 8. 初回実装の順序

1. Python参照実装へ、ADX immediateの4サイクル、実機のVRAM共有CGRAM、8 KiB ROMの文字ROM/BASIC ROM分離を反映する。後二者を反映しない間はロックステップ比較から除外し、HDL単体試験で実機仕様を検証する。ジョイスティックはJava版および修正済みPython版のactive-highプロファイルを維持する。
2. Template_MiSTerを基礎にし、`emu`、`hps_io`、BRAM ROMロード、最小ビデオ出力を接続する。
3. 6800互換CPUをVerilatorで単体起動し、MB8861拡張命令・割込み・命令サイクルを追加する。
4. 命令境界トレースと差分ツールを完成させ、CPU単体およびVIA単体の一致を確認する。
5. メモリマップ、画面、VIA、キーボード、単音出力、OSDロードの順に統合してM1からM5へ進む。

## 9. 参照資料

以下は参照実装 pyjr100emu リポジトリ内のパスである。

- `src/jr100emu/jr100/computer.py`
- `src/jr100emu/jr100/memory.py`
- `src/jr100emu/jr100/display.py`
- `src/jr100emu/jr100/r6522.py`
- `src/jr100emu/jr100/sound.py`
- `src/jr100emu/io/joystick.py`
- `src/jr100emu/via/r6522.py`
- `src/jr100emu/cpu/cpu.py`
- `tests/unit/test_extended_io.py`
- `tests/unit/test_joystick_adapter.py`
- `tests/unit/test_sound.py`
- `docs/IMPLEMENTATION.md`、`docs/CPU_PORTING_NOTES.md`、`docs/VIA_PORTING_NOTES.md`、`docs/HEADLESS_DEBUG_RUNNER.md`
- [JR-100 技術資料（計算機室）](https://asamomiji.jp/contents/documents/retropc/jr100)
- `JR-100.pdf`（`cmpslv3.stars.ne.jp/Jr100/EnrJr1.htm` のPDF化資料。ローカル保管、リポジトリ非同梱）
- [JR-100U Operating Instructions（公式海外版）](https://archive.org/details/Panasonic_JR-100U_Operating_Instructions/mode/2up)（国内版との共通仕様の照合専用）
- [MiSTer FPGA Documentation: hps_io](https://mister-devel.github.io/MkDocs_MiSTer/developer/hps_io/)
- [MiSTer FPGA Documentation: Core Configuration String](https://mister-devel.github.io/MkDocs_MiSTer/developer/conf_str/)
- [MiSTer FPGA Documentation: Core Paths](https://mister-devel.github.io/MkDocs_MiSTer/cores/paths/)
