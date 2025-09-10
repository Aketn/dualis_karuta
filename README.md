# DUALIS かるた製作プロジェクト

名刺サイズ (91mm x 55mm) の札を A4 に 2 列 5 行で面付けし、両面印刷 (長辺綴じ) に対応した PDF を生成します。

## セットアップ

1. 仮想環境を作成
2. 依存関係をインストール
3. VS Code のビルドタスクで PDF 生成

## 使い方

- CSV: `JDC_karuta.csv` を編集して番号や名称、色、フォント等を記入します。
- タスク: `Ctrl+Shift+B` で `pdf-generator` を実行。`DUALIS_karuta_print.pdf` が出力されます。

より詳しい説明は `Docs/WORKSPACE_GUIDE.md` を参照してください。

### 日本語フォントについて

- 既定のHelveticaは日本語グリフを含まないため、日本語を含むテキストには以下の優先順位でフォールバックします。
  1. `fonts/` ディレクトリに配置した TTF/OTF（推奨: 原ノ味フォント）
  - 例: `fonts/HaranoAjiMincho-Regular.ttf` など
  1. ReportLab の内蔵CIDフォント（`HeiseiMin-W3` など）
- 推奨: 原ノ味フォントを下記のように配置してください。

```bash
mkdir -p fonts
# 例: HaranoAji の TTF/OTF を配置
# fonts/HaranoAjiMincho-Regular.ttf
# fonts/HaranoAjiGothic-Medium.ttf
```

## CSV フォーマット

```csv
number,name,color_code,font,point_size,is_bonus_game,bonus_game_name
000,総記,#8E8E93,Helvetica,28,false,
001,知識・学問・学術,#007AFF,Helvetica,28,false,
002,団体,#34C759,Helvetica,28,false,
003,辞典,#FF9500,Helvetica,28,false,
004,論文集,#FF2D55,Helvetica,28,false,
005,逐次刊行物,#AF52DE,Helvetica,28,false,
006,年鑑・貴重書,#5AC8FA,Helvetica,28,false,
007,ジャーナリズム・新聞,#FF3B30,Helvetica,28,false,
008,叢書・全集・選集,#FFD60A,Helvetica,28,false,
009,書誌学,#FF9F0A,Helvetica,28,true,図書館の自由に関する宣言を読み上げる
```

- color_code は `#RRGGBB`。未指定時は 3 桁目の数字に応じて自動着色。
- font はシステムに存在しない場合、Helvetica にフォールバックします。
- point_size は数値 (推奨: 20〜36)。

## 出力

- `output/DUALIS_karuta_print_<範囲>_<YYYYMMDD>.pdf`
  - 例: `output/DUALIS_karuta_print_000-009_20250910.pdf`
  - 範囲はCSV内のnumberを正規表現で抽出して最小-最大を付与（数字が無い場合はALL）
  - 複数ページ: 絵札A/絵札B/読み札A/読み札B の順

## ライセンス

MIT
