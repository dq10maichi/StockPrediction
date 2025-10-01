-- 既存のテーブルが存在する場合、削除
DROP TABLE IF EXISTS daily_stock_prices;
DROP TABLE IF EXISTS macro_economic_indicators;
DROP TABLE IF EXISTS company_fundamentals;
DROP TABLE IF EXISTS stock_info;
DROP TABLE IF EXISTS trained_models;
DROP TABLE IF EXISTS target_tickers;
DROP TABLE IF EXISTS prediction_results;

-- テーブル名: daily_stock_prices
-- 日々の株価データ（始値、高値、安値、終値、出来高など）を格納
CREATE TABLE daily_stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL, -- YYYY-MM-DD 形式
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    adj_close_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, trade_date) -- 同じ銘柄の同じ日付のデータは重複しない
);

-- daily_stock_prices テーブルのインデックス
CREATE INDEX IF NOT EXISTS idx_stock_ticker_date ON daily_stock_prices (ticker_symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_trade_date ON daily_stock_prices (trade_date);


-- テーブル名: macro_economic_indicators
-- FREDなどから取得するマクロ経済指標を格納
CREATE TABLE macro_economic_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id TEXT NOT NULL, -- FREDなどのSeries ID
    indicator_date TEXT NOT NULL, -- YYYY-MM-DD 形式
    value REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, indicator_date) -- 同じ指標の同じ日付のデータは重複しない
);

-- macro_economic_indicators テーブルのインデックス
CREATE INDEX IF NOT EXISTS idx_macro_series_date ON macro_economic_indicators (series_id, indicator_date);
CREATE INDEX IF NOT EXISTS idx_macro_indicator_date ON macro_economic_indicators (indicator_date);


-- テーブル名: company_fundamentals
-- 年次や四半期ごとの財務諸表データや主要指標を格納
CREATE TABLE company_fundamentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_symbol TEXT NOT NULL,
    report_date TEXT NOT NULL, -- YYYY-MM-DD 形式 (報告期間の終了日や発表日)
    period_type TEXT NOT NULL, -- 'ANNUAL', 'QUARTERLY' など
    metric_name TEXT NOT NULL, -- ファンダメンタルズ指標の名前 (例: 'Total Revenue', 'Net Income', 'EPS')
    metric_value REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, report_date, period_type, metric_name) -- 同じ銘柄の同じ報告期間・期間種別で同じ指標は重複しない
);

-- company_fundamentals テーブルのインデックス
CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker_date_metric ON company_fundamentals (ticker_symbol, report_date, metric_name);
CREATE INDEX IF NOT EXISTS idx_fundamentals_report_date ON company_fundamentals (report_date);


-- テーブル名: stock_info
-- 各銘柄の基本情報（会社名、業界、上場市場など）を格納 (任意だが推奨)
CREATE TABLE stock_info (
    ticker_symbol TEXT PRIMARY KEY NOT NULL, -- ティッカーシンボルを主キーにする
    company_name TEXT NOT NULL,
    exchange TEXT NULL,
    sector TEXT NULL,
    industry TEXT NULL,
    country TEXT NULL,
    currency TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- テーブル名: trained_models
-- 学習済みモデル、そのメタデータ、評価指標を格納
CREATE TABLE trained_models (
    -- 1. 基本情報
    model_id INTEGER PRIMARY KEY AUTOINCREMENT, -- モデルの一意なID
    model_name TEXT NOT NULL, -- モデルの識別名 (例: 'LGBM_10d_3pct_up')
    model_version INTEGER NOT NULL, -- モデルのバージョン番号
    creation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, -- このレコードが作成された日時

    -- 2. 関連情報と再現性
    ticker_symbol TEXT NOT NULL, -- 予測対象の銘柄
    training_code_version TEXT NULL, -- 学習に使用したコードのGitコミットハッシュなど
    feature_list TEXT NOT NULL, -- 学習時の特徴量リスト（JSON文字列）

    -- 3. モデル本体と関連オブジェクト
    model_object BLOB NOT NULL, -- シリアライズされたモデル本体
    scaler_object BLOB NOT NULL, -- 同時に学習された特徴量スケーラー

    -- 4. パラメータと評価指標
    hyperparameters TEXT NULL, -- 最適化されたハイパーパラメータ（JSON文字列）
    performance_metrics TEXT NULL, -- 適合率、再現率、ROC AUCなどの評価指標（JSON文字列）

    -- 5. その他
    notes TEXT NULL, -- 自由記述欄
    notification_sent INTEGER DEFAULT 0, -- 通知フラグ (0 or 1)

    -- 6. 制約
    UNIQUE (ticker_symbol, model_name, model_version),
    FOREIGN KEY (ticker_symbol) REFERENCES stock_info(ticker_symbol)
);

-- trained_models テーブルのインデックス
CREATE INDEX IF NOT EXISTS idx_trained_models_ticker_name_version ON trained_models (ticker_symbol, model_name, model_version);

-- テーブル名: target_tickers
-- 予測対象とする銘柄と、その際に使用する特徴量のリストを管理
CREATE TABLE target_tickers (
    ticker TEXT PRIMARY KEY,
    features TEXT, -- カンマ区切りの文字列として特徴量リストを保存
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- テーブル名: prediction_results
-- 日々の予測結果の履歴を保存
CREATE TABLE prediction_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, -- 予測実行日時
    target_date TEXT NOT NULL,          -- 予測対象日 (例: 10営業日後)
    ticker TEXT NOT NULL,        -- 銘柄コード
    direction TEXT NOT NULL,      -- 予測トレンド ('up' or 'down')
    probability REAL NOT NULL,         -- 予測された確率 (例: 0.5410)
    model_name TEXT NOT NULL,   -- 使用したモデル名
    model_version INTEGER NOT NULL,         -- 使用したモデルのバージョン
    notification_sent INTEGER DEFAULT 0, -- 通知フラグ (0 or 1)
    -- 外部キー制約 (任意だが推奨)
    FOREIGN KEY (ticker) REFERENCES stock_info(ticker_symbol) ON DELETE CASCADE
);

-- prediction_results テーブルのインデックス
CREATE INDEX IF NOT EXISTS idx_prediction_results_ticker_date ON prediction_results (ticker, target_date);
CREATE INDEX IF NOT EXISTS idx_prediction_results_model ON prediction_results (model_name, model_version);