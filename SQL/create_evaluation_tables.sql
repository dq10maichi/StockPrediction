-- 評価対象の銘柄リストを格納するテーブル
CREATE TABLE IF NOT EXISTS market_list (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    market_segment TEXT,
    industry_code_33 TEXT,
    industry_name_33 TEXT,
    industry_code_17 TEXT,
    industry_name_17 TEXT,
    scale_code TEXT,
    scale_segment TEXT,
    load_date TEXT
);

-- モデルのパフォーマンス結果を記録するテーブル
CREATE TABLE IF NOT EXISTS performance_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    direction TEXT,
    model_version INTEGER,
    evaluation_datetime DATETIME,
    accuracy REAL,
    precision_score REAL,
    recall_score REAL,
    f1_score REAL,
    roc_auc REAL,
    features TEXT,
    training_period_start TEXT,
    training_period_end TEXT,
    status TEXT,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);