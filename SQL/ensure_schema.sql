-- テーブルが存在しない場合のみ作成するスキーマ定義

-- テーブル名: daily_stock_prices
CREATE TABLE IF NOT EXISTS daily_stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    adj_close_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_stock_ticker_date ON daily_stock_prices (ticker_symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_stock_trade_date ON daily_stock_prices (trade_date);

-- テーブル名: macro_economic_indicators
CREATE TABLE IF NOT EXISTS macro_economic_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id TEXT NOT NULL,
    indicator_date TEXT NOT NULL,
    value REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, indicator_date)
);
CREATE INDEX IF NOT EXISTS idx_macro_series_date ON macro_economic_indicators (series_id, indicator_date);
CREATE INDEX IF NOT EXISTS idx_macro_indicator_date ON macro_economic_indicators (indicator_date);

-- テーブル名: company_fundamentals
CREATE TABLE IF NOT EXISTS company_fundamentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_symbol TEXT NOT NULL,
    report_date TEXT NOT NULL,
    period_type TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker_symbol, report_date, period_type, metric_name)
);
CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker_date_metric ON company_fundamentals (ticker_symbol, report_date, metric_name);
CREATE INDEX IF NOT EXISTS idx_fundamentals_report_date ON company_fundamentals (report_date);

-- テーブル名: stock_info
CREATE TABLE IF NOT EXISTS stock_info (
    ticker_symbol TEXT PRIMARY KEY NOT NULL,
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
CREATE TABLE IF NOT EXISTS trained_models (
    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    creation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    ticker_symbol TEXT NOT NULL,
    training_code_version TEXT NULL,
    feature_list TEXT NOT NULL,
    model_object BLOB NOT NULL,
    scaler_object BLOB NOT NULL,
    hyperparameters TEXT NULL,
    performance_metrics TEXT NULL,
    notes TEXT NULL,
    notification_sent INTEGER DEFAULT 0,
    UNIQUE (ticker_symbol, model_name, model_version),
    FOREIGN KEY (ticker_symbol) REFERENCES stock_info(ticker_symbol)
);
CREATE INDEX IF NOT EXISTS idx_trained_models_ticker_name_version ON trained_models (ticker_symbol, model_name, model_version);

-- テーブル名: target_tickers
CREATE TABLE IF NOT EXISTS target_tickers (
    ticker TEXT PRIMARY KEY,
    features TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- テーブル名: prediction_results
CREATE TABLE IF NOT EXISTS prediction_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    target_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL,
    probability REAL NOT NULL,
    model_name TEXT NOT NULL,
    model_version INTEGER NOT NULL,
    notification_sent INTEGER DEFAULT 0,
    FOREIGN KEY (ticker) REFERENCES stock_info(ticker_symbol) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_prediction_results_ticker_date ON prediction_results (ticker, target_date);
CREATE INDEX IF NOT EXISTS idx_prediction_results_model ON prediction_results (model_name, model_version);