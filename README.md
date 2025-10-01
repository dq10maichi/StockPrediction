# 株価トレンド予測アプリケーション V2

## 1. 概要

このアプリケーションは、機械学習モデル（LightGBM）を用いて、指定された銘柄の将来の株価トレンドを予測するパイプラインです。

具体的には、「10日後に株価が3%以上上昇するか」または「10日後に株価が3%以上下落するか」という2つの分類問題を解き、モデルの学習、評価、保存までの一連のプロセスを自動化します。

## 2. 主な特徴

- **Makefileによる簡単操作**: `make`コマンド一つで、環境構築から日々の運用まで簡単に行えます。
- **データベースによる銘柄管理**: 予測対象の銘柄と特徴量の組み合わせをデータベースで一元管理できます。
- **一括予測機能**: データベースに登録された全銘柄のトレンド予測を `make predict-all` ひとつで実行できます。
- **Docker対応**: すべての処理がDockerコンテナ内で完結するため、環境構築が不要です。
- **豊富な特徴量**: 株価、テクニカル指標、マクロ経済指標など、多様なデータを特徴量として利用します。
- **モデルと結果の永続化**: 学習済みモデル、日々の予測結果はSQLiteデータベースにバージョン管理されて保存されます。

## 3. ディレクトリ構造

```
.
├── Makefile              # 操作を簡略化するMakefile
├── Dockerfile            # Dockerコンテナの定義ファイル
├── requirements.txt      # Pythonの依存ライブラリ
├── script/               # アプリケーションのコアロジック
│   ├── train_model.py      # モデル学習
│   ├── predict.py        # 個別銘柄の予測
│   ├── predict_all.py    # 全登録銘柄の予測と結果保存
│   ├── manage_tickers.py # DBへの監視銘柄の登録・削除・一覧表示
│   └── ...
├── SQL/                  # データベースのテーブル定義
├── predictions/          # 日々の予測結果（CSV）の出力先
├── plots/                # モデル評価のプロット出力先
└── logs/                 # 実行ログの出力先
```

## 4. 要件

-   [Docker](https://www.docker.com/)
-   [make](https://www.gnu.org/software/make/)
-   [Git](https://git-scm.com/)

## 5. インストールとセットアップ

1.  **リポジトリをクローン**

    ```bash
    git clone git@github.com:dq10maichi/StockPrediction.git
    cd stockPrediction
    ```

2.  **Dockerイメージのビルド**

    アプリケーションの実行に必要な環境を含むDockerイメージをビルドします。
    `requirements.txt` に記載されているPythonライブラリがインストールされます。

    ```bash
    make build
    ```

3.  **データベースの初期化**

    SQLiteデータベースファイルを作成し、テーブルスキーマをセットアップします。
    このコマンドは、過去のデータをすべて削除してデータベースを再作成します。

    ```bash
    make init-db
    ```

4.  **（任意）自動実行ジョブの設定**

    毎日のデータ更新と予測を自動化したい場合は、cronジョブを設定します。

    ```bash
    bash script/setup_cron.sh
    ```
    このスクリプトは、現在のユーザーのcrontabに以下のジョブを登録します。
    - 毎日午前7時 (JST): `make update-data` と `make predict-all` を実行
    - 毎週日曜午前8時 (JST): `make send-notifications` を実行

    ジョブの実行ログは `logs/cron.log` に保存されます。

## 6. 主な利用方法 (Makefile)

### 監視銘柄の管理

まず、予測したい銘柄をデータベースに登録します。
`make add-ticker` を実行すると、`target_tickers` テーブルに銘柄が登録されると同時に、`yfinance` ライブラリを通じて銘柄の基本情報（会社名、セクター、国など）が自動的に取得され、`stock_info` テーブルに格納されます。

- **監視銘柄の追加**
  予測対象の銘柄をデータベースに登録します。`FEATURES`には、その銘柄のモデル学習時に使用する特徴量（カンマ区切り）を指定します。
  ```bash
  # 例: トヨタ自動車 (7203.T) を日経平均、TOPIX、S&P500、ドル円を特徴量として追加
  make add-ticker TICKER=7203.T FEATURES='^N225,^TPX,^GSPC,JPY=X'
  ```

- **監視銘柄の一覧表示**
  ```bash
  make list-tickers
  ```

- **監視銘柄の削除**
  ```bash
  make remove-ticker TICKER=7203.T
  ```

- **銘柄情報の個別の手動更新**
  何らかの理由で銘柄情報の更新に失敗した場合など、個別に情報を更新したい場合は以下のコマンドを実行します。
  ```bash
  make update-info TICKER=7203.T
  ```

### 日々の運用

- **1. データ更新（毎日）**
  ```bash
  make update-data
  ```

- **2. モデル学習（銘柄追加時や定期的に実行）**
  ```bash
  make train TICKER=7203.T
  ```
  学習年数は`YEARS`変数で変更可能です (`make train TICKER=7203.T YEARS=3`)。

- **3. 全銘柄の予測（毎日）**
  このコマンドで、DBに登録されている全銘柄の予測を実行し、結果をDBとCSVファイルに保存します。
  ```bash
  make predict-all
  ```

### モデルの管理と評価

学習済みモデルの一覧表示や性能評価については、以下のドキュメントを参照してください。
詳細: [docs/model_management.md](docs/model_management.md)

- **学習済みモデルの一覧表示**
  ```bash
  make list-models [TICKER=7203.T]
  ```

- **特定のモデルの性能評価**
  ```bash
  make evaluate-model TICKER=7203.T DIRECTION=up [VERSION=1]
  ```

### その他

- **利用可能なコマンド一覧の表示**
  ```bash
  make help
  ```

## 7. 運用ガイド

### モデルの改善とテスト

1.  `script/train_model.py`や`script/stock_utils.py`などのPythonコードを編集し、特徴量やモデルのロジックを改善します。
2.  変更を反映させるために、Dockerイメージを再ビルドします。
    ```bash
    make build
    ```
3.  テスト用の銘柄でモデルを学習させ、性能が改善したかを確認します。`TEST=true`を付けると、ハイパーパラメータの探索範囲を狭め、テストを高速に実行できます。
    ```bash
    make train TICKER=7203.T TEST=true
    ```

### バックテストによる詳細な性能検証

`train_model.py`が日々の学習に使われるのに対し、`backtest.py`はより詳細な条件でモデルの性能を検証するために使用します。特定の期間でのテストや、パラメータチューニング、予測ターゲットの探索などに役立ちます。

**注意:** `backtest.py` は現在、データベースからの特徴量読み込みに対応していません。必要に応じて改修が必要です。

## 8. 成果物

- **モデル**: 学習済みのモデルは、SQLiteデータベースの`trained_models`テーブルに直接保存されます。
- **予測結果 (DB)**: `predict-all`による日々の予測結果は`prediction_results`テーブルに蓄積されます。
- **予測結果 (CSV)**: `predict-all`を実行すると、その日の予測結果サマリーが`predictions/`ディレクトリにCSVファイルとして出力されます。
- **評価プロット**: モデルのROC曲線や特徴量の重要度などのグラフが`plots/`ディレクトリに出力されます。
- **ログ**: アプリケーションの詳細な実行ログが`logs/`ディレクトリに出力されます。

## 9. 通知システムの設定

このアプリケーションは、モデル学習や予測結果の通知をGoogle SheetsとEメールで行うことができます。これらの機能を有効にするには、以下の環境変数を設定し、サービスアカウントの認証情報を準備する必要があります。

### 9.1. Google Sheets連携

Google Sheetsに通知を送信するには、以下の設定が必要です。

-   **`GSPREAD_SHEET_NAME` 環境変数**:
    通知を書き込むGoogleスプレッドシートの正確な名前を設定します。
    例: `export GSPREAD_SHEET_NAME="株価予測"`

-   **`secrets/service_account.json` ファイル**:
    Google Sheets APIへの認証に使用するサービスアカウントのJSONキーファイルを、プロジェクトルートの `secrets/` ディレクトリに配置する必要があります。

    **取得方法**:
    1.  Google Cloud Console にアクセスし、新しいプロジェクトを作成するか、既存のプロジェクトを選択します。
    2.  「APIとサービス」->「ライブラリ」に移動し、「Google Sheets API」を検索して有効にします。
    3.  「APIとサービス」->「認証情報」に移動し、「認証情報を作成」->「サービスアカウント」を選択します。
    4.  サービスアカウント名を入力し、作成します。
    5.  作成したサービスアカウントのメールアドレスを控えます。
    6.  サービスアカウントのキーを作成し、JSON形式でダウンロードします。ダウンロードしたファイルを `secrets/service_account.json` として保存します。
    7.  通知を書き込むGoogleスプレッドシート（例: 「株価予測」）を作成し、**サービスアカウントのメールアドレスを「編集者」として共有**します。

### 9.2. Eメール通知

Eメールで通知を送信するには、SMTPサーバーの設定が必要です。

-   **SMTP関連の環境変数**:
    以下の環境変数を設定します。これらは `make send-notifications` コマンド実行時にDockerコンテナ内に渡されます。
    -   `SMTP_HOST`: SMTPサーバーのホスト名 (例: `smtp.gmail.com`)
    -   `SMTP_PORT`: SMTPサーバーのポート番号 (例: `587` for TLS)
    -   `SMTP_USER`: SMTP認証に使用するユーザー名 (メールアドレスであることが多い)
    -   `SMTP_PASSWORD`: SMTP認証に使用するパスワード
    -   `SMTP_SENDER`: 送信元として表示されるメールアドレス
    -   `SMTP_RECIPIENT`: 通知メールの受信者メールアドレス

    例:
    ```bash
    export SMTP_HOST="smtp.gmail.com"
    export SMTP_PORT="587"
    export SMTP_USER="your_email@gmail.com"
    export SMTP_PASSWORD="your_app_password" # アプリパスワードの使用を推奨
    export SMTP_SENDER="your_email@gmail.com"
    export SMTP_RECIPIENT="recipient_email@example.com"
    ```

    **注意**: 上記の環境変数例 (`your_email@gmail.com`, `your_app_password` など) はプレースホルダーです。実際の機密情報（メールアドレス、パスワードなど）を直接 `README.md` やGitリポジトリにコミットしないでください。これらの値は、`.env` ファイルや環境変数として安全に管理する必要があります。

## 10. データベーススキーマ

`SQL/createtable.sql` には、基本的なテーブル定義が含まれています。
`make add-ticker` コマンドを実行することで、`target_tickers` テーブルと `stock_info` テーブルにデータが自動的に登録されます。
`company_fundamentals` テーブルにデータを投入するスクリプトは現在提供されていませんが、将来的な拡張のために用意されています。

各テーブルの詳細な定義、および便利なビュー（`prediction_summary`など）については、以下のドキュメントを参照してください。

詳細: [docs/database_schema.md](docs/database_schema.md)
