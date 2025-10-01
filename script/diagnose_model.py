import argparse
import json
import pandas as pd
import numpy as np
import os
import joblib
import io
import datetime

from db_connector import get_db_connection, DBConnector
from stock_utils import (
    PLOTS_OUTPUT_DIR,
    load_all_data, create_features
)
from train_model import (
    PREDICTION_HORIZON, RETURN_THRESHOLD,
    create_classification_target,
    plot_roc_curve, plot_precision_recall_curve, plot_feature_importance
)

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix
)
from sklearn.model_selection import TimeSeriesSplit

def list_models(ticker=None):
    """学習済みモデルを一覧表示する。銘柄が指定されていれば、その銘柄のみ表示する。"""
    conn = None
    try:
        conn, _ = get_db_connection()
        with conn.cursor() as cur:
            sql = """
                SELECT
                    ticker_symbol, model_name, model_version, notes,
                    performance_metrics, hyperparameters, creation_timestamp
                FROM trained_models
            """
            params = ()
            if ticker:
                sql += " WHERE ticker_symbol = ?"
                params = (ticker,)
            sql += " ORDER BY ticker_symbol, model_name, model_version DESC"

            cur.execute(sql, params)
            models = cur.fetchall()

            if not models:
                msg = f"銘柄 {ticker} の" if ticker else ""
                print(f"{msg}学習済みモデルは見つかりません。")
                return

            header = f"--- 銘柄: {ticker} の学習済みモデル一覧 ---" if ticker else "--- 全ての学習済みモデル一覧 ---"
            print(header)
            current_ticker = None
            current_model_name = None

            for model in models:
                ticker_symbol, model_name, model_version, notes, perf_json, hyper_json, ts_str = model
                perf = json.loads(perf_json) if perf_json else None
                hyper = json.loads(hyper_json) if hyper_json else None
                ts = datetime.datetime.fromisoformat(ts_str) if ts_str else None


                if ticker_symbol != current_ticker:
                    print(f"\n銘柄: {ticker_symbol}")
                    current_ticker = ticker_symbol
                    current_model_name = None

                if model_name != current_model_name:
                    print(f"  モデル名: {model_name}")
                    current_model_name = model_name

                direction = "up" if "up" in model_name else "down" if "down" in model_name else "不明"

                print(f"    バージョン: {model_version} (作成日: {ts.strftime('%Y-%m-%d %H:%M:%S') if ts else 'N/A'})")
                print(f"      方向: {direction}")
                if notes: print(f"      備考: {notes}")

                if perf:
                    print("      学習時パフォーマンス:")
                    for metric, value in perf.items():
                        print(f"        {metric}: {value:.4f}")
                print("-" * 40)

    except Exception as e:
        print(f"モデル一覧の取得中にエラーが発生しました: {e}")
    finally:
        if conn: conn.close()

def load_model_for_evaluation(ticker, model_name, version=None):
    """評価用に、モデルと関連する全てのメタデータをデータベースから読み込む。"""
    conn = None
    try:
        conn, _ = get_db_connection()
        with conn.cursor() as cur:
            base_query = """
                SELECT model_object, scaler_object, feature_list, performance_metrics, hyperparameters, creation_timestamp
                FROM trained_models
                WHERE ticker_symbol = ? AND model_name = ?
            """
            if version:
                query = base_query + " AND model_version = ?"
                params = (ticker, model_name, version)
            else:
                query = base_query + " ORDER BY model_version DESC LIMIT 1"
                params = (ticker, model_name)

            cur.execute(query, params)
            result = cur.fetchone()

            if not result:
                print(f"エラー: データベースに銘柄 {ticker} のモデル {model_name} (バージョン: {version or '最新'}) が見つかりません。")
                return None, None, None, None, None, None

            model_bytes, scaler_bytes, feature_list_json, perf_json, hyper_json, ts_str = result
            model = joblib.load(io.BytesIO(model_bytes))
            scaler = joblib.load(io.BytesIO(scaler_bytes))
            feature_list = json.loads(feature_list_json) if feature_list_json else None
            perf = json.loads(perf_json) if perf_json else None
            hyper = json.loads(hyper_json) if hyper_json else None
            ts = datetime.datetime.fromisoformat(ts_str) if ts_str else None


            if version is None:
                cur.execute("SELECT model_version FROM trained_models WHERE ticker_symbol = ? AND model_name = ? ORDER BY model_version DESC LIMIT 1", (ticker, model_name))
                version = cur.fetchone()[0]

            print(f"データベースからモデル {ticker} (name: {model_name}, version: {version}) を正常に読み込みました。")
            return model, scaler, feature_list, perf, hyper, ts

    except Exception as e:
        print(f"データベースからのモデル読み込み中にエラーが発生しました: {e}")
        return None, None, None, None, None, None
    finally:
        if conn: conn.close()

def evaluate_model_performance(ticker, direction, version=None):
    """指定されたモデルのパフォーマンスを評価し、結果の辞書を返す。"""
    model_name = f"LGBM_{PREDICTION_HORIZON}d_{direction}_{int(RETURN_THRESHOLD*100)}pct"
    model, scaler, feature_list, perf_db, hyper_db, creation_ts = load_model_for_evaluation(ticker, model_name, version)
    if model is None: return None

    print("\n--- モデル情報 ---")
    print(f"  銘柄: {ticker}, モデル名: {model_name}, バージョン: {version or '最新'}")
    print(f"  学習完了日時: {creation_ts}")
    if perf_db: print("  学習時のパフォーマンス指標:", perf_db)
    print("------------------")

    db_connector_for_features = DBConnector()
    try:
        with db_connector_for_features.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT features FROM target_tickers WHERE ticker = ?", (ticker,))
                result = cursor.fetchone()
                feature_tickers = result[0].split(',') if result and result[0] else []
    except Exception as e:
        print(f"データベースからの特徴量取得エラー: {e}。外部指標なしで続行します。")
        feature_tickers = []

    print(f"\n--- 特徴量と目的変数を生成中 ---")
    db_connector = DBConnector()
    main_data, external_data, macro_data = load_all_data(db_connector, ticker, feature_tickers)
    if main_data.empty:
        print("データ取得に失敗しました。"); return None

    all_features_df = create_features(main_data, external_data, macro_data)
    targets_df, target_col = create_classification_target(all_features_df, PREDICTION_HORIZON, RETURN_THRESHOLD, direction)

    # タイムゾーン情報を揃える（DBからはaware, DFはnaiveなため）
    if creation_ts and hasattr(creation_ts, 'tzinfo') and creation_ts.tzinfo is not None:
        creation_ts = creation_ts.replace(tzinfo=None)

    # モデル学習時以降のデータのみを評価対象とする
    evaluation_df = targets_df[targets_df.index > creation_ts].dropna()
    
    if evaluation_df.empty:
        print("評価対象となる新しいデータがありません。"); return None
    
    print(f"評価対象期間: {evaluation_df.index.min().date()} から {evaluation_df.index.max().date()} まで ({len(evaluation_df)}件)")

    y_test = evaluation_df[[target_col]]
    X_test = evaluation_df[all_features_df.columns.intersection(evaluation_df.columns)]

    print("\n--- 評価データの準備とスケーリング ---")
    try:
        X_test_aligned = X_test[feature_list]
    except KeyError as e:
        print(f"エラー: 必要な特徴量が不足。{e}"); return None

    numeric_features = X_test_aligned.select_dtypes(include=np.number).columns.tolist()
    X_test_scaled = X_test_aligned.copy()
    X_test_scaled[numeric_features] = scaler.transform(X_test_aligned[numeric_features])

    print("\n--- モデルのパフォーマンスを評価中 ---")
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)

    # Calculate metrics
    metrics = {
        "Accuracy": accuracy_score(y_test, y_pred),
        "Precision": precision_score(y_test, y_pred, zero_division=0),
        "Recall": recall_score(y_test, y_pred, zero_division=0),
        "F1 Score": f1_score(y_test, y_pred, zero_division=0),
        "ROC AUC": roc_auc_score(y_test, y_pred_proba)
    }

    print(f"\n--- 評価結果 (学習後のデータ) ---")
    for key, value in metrics.items():
        print(f"  {key}:  {value:.4f}")
    print("\n  Confusion Matrix:\n", confusion_matrix(y_test, y_pred))

    plot_roc_curve(y_test, y_pred_proba, ticker, direction)
    plot_precision_recall_curve(y_test, y_pred_proba, ticker, direction)
    if hasattr(model, 'feature_importances_'):
        imp = pd.DataFrame({'feature': feature_list, 'importance': model.feature_importances_})
        plot_feature_importance(imp, feature_list, ticker, direction)
    print(f"\n評価プロットが '{PLOTS_OUTPUT_DIR}' に保存されました。")

    return metrics

def backtest_model_performance(ticker, direction, version=None, n_splits=4):
    """指定されたモデルのバックテストを行い、パフォーマンスを評価する。"""
    model_name = f"LGBM_{PREDICTION_HORIZON}d_{direction}_{int(RETURN_THRESHOLD*100)}pct"
    model, scaler, feature_list, _, _, creation_ts = load_model_for_evaluation(ticker, model_name, version)
    if model is None: return

    print(f"\n--- バックテスト開始: {ticker} ({direction}) ---")
    print(f"  モデルバージョン: {version or '最新'}, 学習完了日時: {creation_ts}")

    # (略) データ取得と特徴量生成 (evaluate_model_performanceと同様)
    db_connector = DBConnector()
    main_data, external_data, macro_data = load_all_data(db_connector, ticker, [])
    if main_data.empty: print("データ取得失敗"); return
    all_features_df = create_features(main_data, external_data, macro_data)
    targets_df, target_col = create_classification_target(all_features_df, PREDICTION_HORIZON, RETURN_THRESHOLD, direction)

    if hasattr(creation_ts, 'tzinfo') and creation_ts.tzinfo is not None:
        creation_ts = creation_ts.replace(tzinfo=None)

    evaluation_df = targets_df[targets_df.index > creation_ts].dropna()
    if len(evaluation_df) < n_splits * 2: # Ensure enough data for splitting
        print(f"バックテストに十分なデータがありません ({len(evaluation_df)}件)。")
        return

    tscv = TimeSeriesSplit(n_splits=n_splits)
    X = evaluation_df[feature_list]
    y = evaluation_df[target_col]

    all_metrics = []
    for i, (train_index, test_index) in enumerate(tscv.split(X)):
        print(f"\n--- バックテスト スプリット {i+1}/{n_splits} ---")
        X_test, y_test = X.iloc[test_index], y.iloc[test_index]
        
        if len(y_test) == 0:
            print("このスプリットにはテストデータがありません。")
            continue

        start_date = X_test.index.min().date()
        end_date = X_test.index.max().date()
        print(f"  評価期間: {start_date} から {end_date} まで ({len(X_test)}件)")

        X_test_scaled = X_test.copy()
        numeric_features = X_test.select_dtypes(include=np.number).columns.tolist()
        X_test_scaled[numeric_features] = scaler.transform(X_test[numeric_features])

        y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
        y_pred = (y_pred_proba > 0.5).astype(int)

        metrics = {
            "ROC AUC": roc_auc_score(y_test, y_pred_proba),
            "F1 Score": f1_score(y_test, y_pred, zero_division=0),
            "Precision": precision_score(y_test, y_pred, zero_division=0),
            "Recall": recall_score(y_test, y_pred, zero_division=0)
        }
        all_metrics.append(metrics)
        for key, value in metrics.items():
            print(f"    {key}: {value:.4f}")

    print("\n--- バックテストサマリー ---")
    summary_df = pd.DataFrame(all_metrics)
    print(summary_df.describe())

def main():
    parser = argparse.ArgumentParser(
        description="学習済みモデルの一覧表示または性能評価を行います。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--ticker', type=str, help="対象のティッカーシンボル (例: 7203.T)。")
    parser.add_argument('--direction', type=str, choices=['up', 'down'], help="評価するトレンドの方向。")
    parser.add_argument('--version', type=int, help="評価するモデルのバージョン番号。")
    parser.add_argument('--backtest', action='store_true', help="バックテストモードで評価を実行します。")

    args = parser.parse_args()

    if args.backtest:
        if not args.ticker or not args.direction:
            parser.error("--backtestには --ticker と --direction の両方が必須です。")
        print("--- バックテストモード ---")
        backtest_model_performance(args.ticker, args.direction, args.version)
    elif args.direction:
        if not args.ticker:
            parser.error("--direction を指定する場合は --ticker も必須です。")
        print(f"--- モデル評価モード ---")
        evaluate_model_performance(args.ticker, args.direction, args.version)
    else:
        print(f"--- モデル一覧表示モード ---")
        list_models(args.ticker)

    print("\n--- スクリプトが完了しました。 ---")

if __name__ == "__main__":
    main()
