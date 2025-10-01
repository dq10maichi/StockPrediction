DROP VIEW IF EXISTS prediction_summary;

CREATE VIEW prediction_summary AS
WITH latest_predictions AS (
    -- 各銘柄と方向ごとに最新の予測タイムスタンプを取得
    SELECT
        ticker,
        direction,
        MAX(prediction_timestamp) AS max_timestamp
    FROM
        prediction_results
    GROUP BY
        ticker,
        direction
),
latest_stock_updates AS (
    -- 各銘柄の最新の株価更新日を取得
    SELECT
        ticker_symbol,
        MAX(trade_date) AS last_updated
    FROM
        daily_stock_prices
    GROUP BY
        ticker_symbol
)
SELECT
    -- Ticker and Company Name
    tt.ticker,
    si.company_name,

    -- Latest 'up' prediction details
    p_up.probability AS up_probability,
    p_up.model_version AS up_model_version,
    m_up.creation_timestamp AS up_model_creation_date,
    CAST(json_extract(m_up.performance_metrics, '$.recall') AS REAL) AS up_model_recall,
    CAST(json_extract(m_up.performance_metrics, '$.roc_auc') AS REAL) AS up_model_roc_auc,
    CAST(json_extract(m_up.performance_metrics, '$.accuracy') AS REAL) AS up_model_accuracy,
    CAST(json_extract(m_up.performance_metrics, '$.f1_score') AS REAL) AS up_model_f1_score,

    -- Latest 'down' prediction details
    p_down.probability AS down_probability,
    p_down.model_version AS down_model_version,
    m_down.creation_timestamp AS down_model_creation_date,
    CAST(json_extract(m_down.performance_metrics, '$.recall') AS REAL) AS down_model_recall,
    CAST(json_extract(m_down.performance_metrics, '$.roc_auc') AS REAL) AS down_model_roc_auc,
    CAST(json_extract(m_down.performance_metrics, '$.accuracy') AS REAL) AS down_model_accuracy,
    CAST(json_extract(m_down.performance_metrics, '$.f1_score') AS REAL) AS down_model_f1_score,

    -- Last stock data update
    lsu.last_updated AS stock_data_updated_at

FROM
    target_tickers tt
    -- Join with stock info to get company name
    LEFT JOIN stock_info si ON tt.ticker = si.ticker_symbol

    -- Join for 'up' predictions
    LEFT JOIN latest_predictions lp_up ON tt.ticker = lp_up.ticker AND lp_up.direction = 'up'
    LEFT JOIN prediction_results p_up ON lp_up.ticker = p_up.ticker AND lp_up.max_timestamp = p_up.prediction_timestamp AND p_up.direction = 'up'
    LEFT JOIN trained_models m_up ON p_up.ticker = m_up.ticker_symbol AND p_up.model_name = m_up.model_name AND p_up.model_version = m_up.model_version

    -- Join for 'down' predictions
    LEFT JOIN latest_predictions lp_down ON tt.ticker = lp_down.ticker AND lp_down.direction = 'down'
    LEFT JOIN prediction_results p_down ON lp_down.ticker = p_down.ticker AND lp_down.max_timestamp = p_down.prediction_timestamp AND p_down.direction = 'down'
    LEFT JOIN trained_models m_down ON p_down.ticker = m_down.ticker_symbol AND p_down.model_name = m_down.model_name AND p_down.model_version = m_down.model_version

    -- Join for last stock update date
    LEFT JOIN latest_stock_updates lsu ON tt.ticker = lsu.ticker_symbol;