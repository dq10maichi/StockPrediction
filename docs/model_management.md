# モデル関連スクリプト仕様書

このドキュメントでは、株価予測プロジェクトにおけるモデルの学習、評価、管理に使用される主要なスクリプトについて説明します。

---

## 1. `script/train_model.py`

### 概要
指定された銘柄の予測モデル（up/down）を学習し、結果をデータベースに保存します。

### 主な機能
- **特徴量生成:** `stock_utils.py` を使用して、価格データや外部指標から学習用の特徴量を生成します。
- **ハイパーパラメータチューニング:** 最適なモデルのパラメータを探索します。以下の3つの手法から選択可能です。
    1.  `grid`: 予め定義された組み合わせを総当たりで試す、網羅的な探索。
    2.  `random`: 定義された範囲からランダムに組み合わせをサンプリングする、効率的な探索。
    3.  `optuna`: 過去の試行結果を基に、より有望な領域を重点的に探索するベイズ最適化。最も高度で、良い結果が期待できます。
- **モデルの保存:** 学習済みのモデル、特徴量リスト、学習時のパフォーマンス指標などをデータベースの `trained_models` テーブルに保存します。

### 使用方法 (`Makefile`経由)

`make train` コマンドを使用するのが最も簡単です。

```bash
# Optunaで学習 (推奨)
make train TICKER=7203.T

# ランダム探索を指定して学習
make train TICKER=7203.T SEARCH_METHOD=random

# グリッド探索を指定して学習
make train TICKER=7203.T SEARCH_METHOD=grid
```

### 主要な引数
*   `TICKER`: (必須) 学習対象のティッカーシンボル。
*   `SEARCH_METHOD`: (任意) `optuna` (デフォルト), `random`, `grid` から選択。
*   `YEARS`: (任意) 学習に使用する過去データの年数（デフォルト: 5）。
*   `TEST`: (任意) `true` に設定すると、探索範囲を狭めたテストモードで実行します。

---

## 2. `script/diagnose_model.py`

### 概要
学習済みモデルと対話するための多機能スクリプトです。以下の3つのモードで動作します。

1.  **一覧表示モード:** モデルの概要を確認します。
2.  **評価モード:** モデルの性能を、学習完了後の単一の未来期間で評価します。
3.  **バックテストモード:** モデルの性能を、学習完了後の複数期間にわたって評価し、安定性を測定します。

### 使用方法 (`Makefile`経由)

#### モデルの一覧表示 (`list-models`)
```bash
make list-models TICKER=7203.T
```

#### モデルの性能評価 (`evaluate-model`)
**注意:** 信頼性の高い評価のためには、モデルの学習時から**10営業日以上**経過し、評価に十分な新しいデータが蓄積されている必要があります。
```bash
make evaluate-model TICKER=7203.T DIRECTION=up
```

### 直接的なスクリプトの使用法

`--backtest` のように、`Makefile`で対応していない引数を使う場合は、スクリプトを直接実行します。

```bash
# バックテストモードの実行例
docker run --rm stock-app python script/diagnose_model.py --ticker 7203.T --direction up --backtest
```

### 主要な引数
*   `--ticker`: (必須) 対象のティッカーシンボル。
*   `--direction`: (必須) `up` または `down`。
*   `--version`: (任意) 評価したいモデルのバージョン。デフォルトは最新版。
*   `--backtest`: (任意) このフラグを付けるとバックテストモードで実行されます。

---

## 3. `script/generate_report.py`

### 概要
全ティッカーの最新モデルのパフォーマンスを一度に評価し、結果をMarkdown形式のレポートとして出力します。

### 使用方法
```bash
# レポートをコンソールに出力
docker run --rm stock-app python script/generate_report.py

# ファイルに保存
docker run --rm stock-app python script/generate_report.py > model_performance_report.md
```