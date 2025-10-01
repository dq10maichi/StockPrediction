import argparse
import json
import pandas as pd
import numpy as np
import datetime
import os

from stock_utils import (
    PLOTS_OUTPUT_DIR,
    load_all_data, create_features
)
from predict import load_model_from_db # Use the enhanced load_model_from_db
from train_model import (
    PREDICTION_HORIZON, RETURN_THRESHOLD, 
    create_classification_target, 
    plot_roc_curve, plot_precision_recall_curve, plot_feature_importance
)

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix
)

def evaluate_model_performance(ticker, direction, version=None):
    # 1. Construct model name and load from DB
    model_name = f"LGBM_{PREDICTION_HORIZON}d_{direction}_{int(RETURN_THRESHOLD*100)}pct"
    model, scaler, feature_list, performance_metrics_db, hyperparameters_db = load_model_from_db(ticker, model_name, version)
    if model is None:
        return

    print("\n--- モデル情報 ---")
    print(f"  学習時の特徴量リスト: {feature_list}")
    if hyperparameters_db:
        print("  学習時のハイパーパラメータ:")
        for param, value in hyperparameters_db.items():
            print(f"    {param}: {value}")
    if performance_metrics_db:
        print("  学習時のパフォーマンス指標:")
        for metric, value in performance_metrics_db.items():
            print(f"    {metric}: {value:.4f}")
    print("------------------")

    # 2. Get all data to generate features and target
    try:
        with open('tickers.json', 'r', encoding='utf-8') as f:
            tickers_data = json.load(f)
        
        target_ticker_info = next((item for item in tickers_data if item["ticker_symbol"] == ticker), None)
        
        if target_ticker_info and 'feature_tickers' in target_ticker_info:
            feature_tickers = target_ticker_info['feature_tickers']
            print(f"\n銘柄 {ticker} の特徴量として {feature_tickers} を使用します。")
        else:
            print(f"\n警告: {ticker} の特徴量リストが tickers.json に見つかりません。外部指標なしで続行します。")
            feature_tickers = []

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"\ntickers.jsonの読み込みエラー: {e}。外部指標なしで続行します。")
        feature_tickers = []

    print("\n--- 全データを取得し、特徴量と目的変数を生成中 ---")
    main_data, external_data, macro_data = load_all_data(ticker, feature_tickers)
    if main_data.empty:
        print("データ取得に失敗しました。処理を終了します。")
        return

    all_features_df = create_features(main_data, external_data, macro_data)
    targets_df, target_col = create_classification_target(all_features_df, PREDICTION_HORIZON, RETURN_THRESHOLD, direction)
    
    final_df = targets_df.dropna()
    y = final_df[[target_col]]
    X = final_df[all_features_df.columns.intersection(final_df.columns)]
    
    aligned_index = X.index.intersection(y.index)
    X = X.loc[aligned_index]
    y = y.loc[aligned_index]

    # 3. Split data into train and test sets (e.g., last 20% for test)
    train_size = int(len(X) * 0.8)
    X_test = X.iloc[train_size:]
    y_test = y.iloc[train_size:]

    if X_test.empty:
        print("評価用のテストデータがありません。データ期間を確認してください。")
        return

    # 4. Ensure feature consistency and scale test data
    print("\n--- 評価データの準備とスケーリング ---")
    try:
        X_test_aligned = X_test[feature_list] # Align columns with training features
    except KeyError as e:
        print(f"エラー: 評価に必要な特徴量が不足しています。{e}")
        print("学習時の特徴量リスト: ", feature_list)
        print("現在の評価データの特徴量リスト: ", X_test.columns.tolist())
        return

    numeric_features = X_test_aligned.select_dtypes(include=np.number).columns.tolist()
    X_test_scaled = X_test_aligned.copy()
    X_test_scaled[numeric_features] = scaler.transform(X_test_aligned[numeric_features])

    # 5. Make predictions and evaluate
    print("\n--- モデルのパフォーマンスを評価中 ---")
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_pred_proba)

    print(f"\n--- 評価結果 (テストデータ) ---")
    print(f"  Accuracy: {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall: {recall:.4f}")
    print(f"  F1 Score: {f1:.4f}")
    print(f"  ROC AUC: {roc_auc:.4f}")
    print("\n  Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # 6. Generate plots
    plot_roc_curve(y_test, y_pred_proba, ticker)
    plot_precision_recall_curve(y_test, y_pred_proba, ticker)
    
    # Feature importance from the loaded model (if available)
    if hasattr(model, 'feature_importances_'):
        feature_importances = pd.DataFrame({'feature': feature_list, 'importance': model.feature_importances_})
        plot_feature_importance(feature_importances, ticker)
    else:
        print("警告: ロードされたモデルには特徴量の重要度情報が含まれていません。")

    print(f"評価プロットが '{PLOTS_OUTPUT_DIR}' に保存されました。")

def main():
    parser = argparse.ArgumentParser(description="指定された学習済みモデルのパフォーマンスを評価します。 અ")
    parser.add_argument('--ticker', type=str, required=True, help="評価対象のティッカーシンボル (例: 7203.T)")
    parser.add_argument('--direction', type=str, default='up', choices=['up', 'down'], help="評価するトレンドの方向 ('up' または 'down')")
    parser.add_argument('--version', type=int, help="使用するモデルのバージョンを任意で指定。未指定の場合は最新バージョンが使われます。")
    args = parser.parse_args()

    evaluate_model_performance(args.ticker, args.direction, args.version)

    print("\n--- モデル評価スクリプトが完了しました。 ---")

if __name__ == "__main__":
    main()
