from sklearnex import patch_sklearn
patch_sklearn()

import argparse
import joblib
import json
import pandas as pd
import numpy as np
import io
import datetime
import sqlite3

from db_connector import DBConnector
from stock_utils import (
    load_all_data, create_features
)
from train_model import PREDICTION_HORIZON, RETURN_THRESHOLD


def load_model_from_db(db_connector, ticker, model_name, version=None):
    """Loads a model and its metadata from the database."""
    try:
        with db_connector.connect() as conn:
                                    cur = conn.cursor()
                                    if version:
                                        query = "SELECT model_object, scaler_object, feature_list, model_version FROM trained_models WHERE ticker_symbol = ? AND model_name = ? AND model_version = ?"
                                        cur.execute(query, (ticker, model_name, version))
                                    else:
                                        query = "SELECT model_object, scaler_object, feature_list, model_version FROM trained_models WHERE ticker_symbol = ? AND model_name = ? ORDER BY model_version DESC LIMIT 1"
                                        cur.execute(query, (ticker, model_name))
                                    result = cur.fetchone()
                                    if not result:
                                        print(f"エラー: データベースに銘柄 {ticker} のモデル {model_name} が見つかりません。")
                                        return None, None, None, None
                        
                                    model_bytes, scaler_bytes, feature_list_json, model_version = result
                                    model = joblib.load(io.BytesIO(model_bytes))
                                    scaler = joblib.load(io.BytesIO(scaler_bytes))
                                    feature_list = json.loads(feature_list_json)
                        
                                    print(f"データベースからモデル {ticker} (name: {model_name}, version: {model_version}) を正常に読み込みました。")
                                    return model, scaler, feature_list, model_version
    except Exception as e:
        print(f"データベースからのモデル読み込み中にエラーが発生しました: {e}")
        return None, None, None, None


def predict_ticker(db_connector, ticker, direction, version=None):
    """Predicts the trend for a single ticker and returns the result as a dictionary."""
    model_name = f"LGBM_{PREDICTION_HORIZON}d_{direction}_{int(RETURN_THRESHOLD*100)}pct"
    model, scaler, feature_list, model_version = load_model_from_db(db_connector, ticker, model_name, version)
    if model is None:
        return None

    try:
        with db_connector.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT features FROM target_tickers WHERE ticker = ?", (ticker,))
            result = cursor.fetchone()
            if result and result[0]:
                feature_tickers = result[0].split(',')
                print(f"\n銘柄 {ticker} の特徴量として {feature_tickers} をデータベースから取得しました。")
            else:
                print(f"\n警告: {ticker} の特徴量リストがデータベースに見つかりません。外部指標なしで続行します。")
                feature_tickers = []
    except Exception as e:
        print(f"\nデータベースからの特徴量取得エラー: {e}。外部指標なしで続行します。")
        feature_tickers = []

    main_data, external_data, macro_data = load_all_data(db_connector, ticker, feature_tickers)
    if main_data.empty:
        print("データ取得に失敗しました。処理を終了します。")
        return None

    all_features_df = create_features(main_data, external_data, macro_data)
    latest_features = all_features_df.iloc[[-1]]

    # モデルが期待する特徴量リストと、現在の特徴量DataFrameのカラム名の不一致を修正
    # 主にpandas_taのバージョンアップによるボリンジャーバンドの命名規則変更に対応
    renamed_latest_features = latest_features.copy()
    for expected_feature in feature_list:
        # 古いボリンジャーバンドの命名規則をチェック (例: BBL_20_2.0)
        if expected_feature.startswith(('BBL_', 'BBM_', 'BBU_', 'BBB_', 'BBP_')) and expected_feature.endswith('_2.0'):
            # 新しいボリンジャーバンドの命名規則 (例: BBL_20_2.0_2.0)
            new_bb_name = expected_feature + '_2.0'
            if new_bb_name in renamed_latest_features.columns and expected_feature not in renamed_latest_features.columns:
                renamed_latest_features.rename(columns={new_bb_name: expected_feature}, inplace=True)
    latest_features = renamed_latest_features # 更新されたDataFrameを使用

    try:
        prediction_data = latest_features[feature_list]
    except KeyError as e:
        print(f"エラー: 予測に必要な特徴量が不足しています。{e}")
        return None

    numeric_features = prediction_data.select_dtypes(include=np.number).columns.tolist()
    prediction_data_scaled = prediction_data.copy()
    prediction_data_scaled[numeric_features] = scaler.transform(prediction_data[numeric_features])

    probability = model.predict_proba(prediction_data_scaled)[:, 1][0]

    target_date = pd.to_datetime(latest_features.index[0]) + pd.tseries.offsets.BusinessDay(n=PREDICTION_HORIZON)

    return {
        "ticker": ticker,
        "direction": direction,
        "probability": probability,
        "model_name": model_name,
        "model_version": model_version,
        "target_date": target_date.strftime('%Y-%m-%d'),
    }


def main():
    parser = argparse.ArgumentParser(description="データベースから学習済みモデルを読み込み、最新の株価トレンドを予測します。")
    parser.add_argument('--ticker', type=str, required=True, help="予測対象のティッカーシンボル (例: 7203.T)")
    parser.add_argument('--direction', type=str, default='up', choices=['up', 'down'], help="予測するトレンドの方向 ('up' または 'down')")
    parser.add_argument('--version', type=int, help="使用するモデルのバージョンを任意で指定。未指定の場合は最新バージョンが使われます。")
    args = parser.parse_args()

    db_connector = DBConnector()
    result = predict_ticker(db_connector, args.ticker, args.direction, args.version)

    if result:
        direction_jp = "上昇" if result['direction'] == 'up' else "下落"
        threshold_pct = int(RETURN_THRESHOLD * 100)
        print("\n--- 予測結果 ---")
        print(f"対象銘柄: {result['ticker']}")
        print(f"モデル: {result['model_name']} (version: {result['model_version']})")
        print(f"予測対象: {PREDICTION_HORIZON}日後 ({result['target_date']}) の株価が {threshold_pct}% 以上{direction_jp}するか")
        print("-------------------------------------")
        print(f"{direction_jp}する確率: {result['probability']:.2%}")
        print("-------------------------------------")


if __name__ == "__main__":
    main()