import pandas as pd
import numpy as np
import datetime
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_auc_score
)
import os
import argparse
import warnings
import json
from sklearn.model_selection import RandomizedSearchCV

# 共通モジュールから設定と関数をインポート
from stock_utils import (
    load_all_data, create_features
)

warnings.filterwarnings('ignore', category=UserWarning)

def create_target(df, prediction_days, threshold, direction='up'):
    """目的変数を作成する"""
    df_copy = df.copy()
    future_price = df_copy['adj_close_price'].shift(-prediction_days)
    df_copy[f'target_return_{prediction_days}d'] = (future_price - df_copy['adj_close_price']) / df_copy['adj_close_price']
    
    target_col_name = f'target_{prediction_days}d_{direction}_{int(threshold*100)}pct'
    
    if direction == 'up':
        df_copy[target_col_name] = (df_copy[f'target_return_{prediction_days}d'] >= threshold).astype(int)
    elif direction == 'down':
        df_copy[target_col_name] = (df_copy[f'target_return_{prediction_days}d'] <= -threshold).astype(int)
    else:
        raise ValueError("direction must be either 'up' or 'down'")
        
    df_copy.dropna(subset=[target_col_name], inplace=True)
    return df_copy, target_col_name

def run_backtest(ticker, feature_tickers, train_end_date, test_start_date, tune_hyperparameters=False, direction='up', threshold=0.03, prediction_days=10):
    """指定された銘柄と特徴量、期間でバックテストを実行する"""
    print("-" * 80)
    print(f"バックテスト開始: {datetime.datetime.now()}")
    print(f"対象銘柄: {ticker}")
    print(f"予測方向: {direction}, 閾値: {threshold:.2%}, 予測期間: {prediction_days}日")
    print(f"特徴量: {feature_tickers if feature_tickers else 'なし'}")
    print(f"学習期間終了日: {train_end_date}")
    print(f"評価期間開始日: {test_start_date}")
    print(f"ハイパーパラメータチューニング: {tune_hyperparameters}")
    print("-" * 80)

    # 1. データ取得
    main_df, feature_dfs, macro_df = load_all_data(ticker, feature_tickers if feature_tickers else [])
    if main_df.empty:
        print(f"エラー: {ticker} のデータが見つかりません。")
        return

    # 2. 特徴量と目的変数の作成
    df_with_features = create_features(main_df, feature_dfs, macro_df)
    df_final, target_col = create_target(df_with_features, prediction_days, threshold, direction)

    if df_final.empty:
        print("エラー: データが空になりました。期間が不十分か、データがありません。")
        return

    # 3. 学習データと評価データに分割
    train_df = df_final.loc[:train_end_date]
    test_df = df_final.loc[test_start_date:]

    if train_df.empty or test_df.empty:
        print("エラー: 学習または評価データが空です。期間設定を確認してください。")
        return

    print(f"学習データ件数: {len(train_df)}")
    print(f"評価データ件数: {len(test_df)}")

    features = [col for col in train_df.columns if col not in 
                ['open_price', 'high_price', 'low_price', 'close_price', 'adj_close_price', 
                 'future_adj_close', 'volume', target_col] and not col.endswith('_volume') and not col.endswith('_price') and not col.startswith('target')] 
    
    X_train = train_df[features]
    y_train = train_df[target_col]
    X_test = test_df[features]
    y_test = test_df[target_col]

    # 4. スケーリング
    numeric_features = [f for f in features if X_train[f].dtype in ['int64', 'float64']]
    scaler = StandardScaler()
    X_train_scaled = X_train.copy()
    X_test_scaled = X_test.copy()
    X_train_scaled[numeric_features] = scaler.fit_transform(X_train[numeric_features])
    X_test_scaled[numeric_features] = scaler.transform(X_test[numeric_features])

    # 5. モデル学習またはハイパーパラメータチューニング
    if tune_hyperparameters:
        print("\nハイパーパラメータチューニングを開始します...")
        param_dist = {
            'n_estimators': [100, 200, 300, 500, 800],
            'learning_rate': [0.01, 0.05, 0.1, 0.2],
            'num_leaves': [20, 31, 40, 60],
            'max_depth': [-1, 5, 8, 10],
            'min_child_samples': [20, 30, 50, 100],
            'subsample': [0.7, 0.8, 0.9, 1.0],
            'colsample_bytree': [0.7, 0.8, 0.9, 1.0],
            'reg_alpha': [0, 0.1, 0.5, 1.0],
            'reg_lambda': [0, 0.1, 0.5, 1.0],
        }
        # RandomizedSearchCVは、指定されたパラメータ分布からランダムにサンプリングして探索
        # n_iterは試行回数、cvは交差検定の分割数
        random_search = RandomizedSearchCV(
            lgb.LGBMClassifier(objective='binary', metric='binary_logloss', random_state=42, is_unbalance=True),
            param_distributions=param_dist,
            n_iter=50, # 試行回数
            scoring='roc_auc', # 評価指標
            cv=3, # 交差検定の分割数
            verbose=0, # ログ出力レベル
            random_state=42,
            n_jobs=-1 # 全てのCPUコアを使用
        )
        random_search.fit(X_train_scaled, y_train)
        lgb_clf = random_search.best_estimator_
        print("\n最適なハイパーパラメータ:")
        print(random_search.best_params_)
    else:
        print("\nモデルを学習中...")
        lgb_clf = lgb.LGBMClassifier(objective='binary', metric='binary_logloss', random_state=42, is_unbalance=True)
        lgb_clf.fit(X_train_scaled, y_train)

    # 6. 評価
    y_pred = lgb_clf.predict(X_test_scaled)
    y_pred_proba = lgb_clf.predict_proba(X_test_scaled)[:, 1]

    print("\n--- モデル評価結果 ---")
    print(f"期間: {test_start_date} から {test_df.index[-1].strftime('%Y-%m-%d')} まで")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred):.4f}")
    print(f"Recall: {recall_score(y_test, y_pred):.4f}")
    print(f"F1 Score: {f1_score(y_test, y_pred):.4f}")
    print(f"ROC AUC Score: {roc_auc_score(y_test, y_pred_proba):.4f}")
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description='株価予測モデルのバックテストを実行します。')
    parser.add_argument('--ticker', type=str, required=True, help='予測対象の銘柄コード (例: 6902.JP)')
    # feature-tickersはtickers.jsonから読み込むため、引数としては不要にするが、後方互換性のため残す
    parser.add_argument('--feature-tickers', type=str, nargs='*', default=None, help='[非推奨] 特徴量として使用する外部指標の銘柄コード')
    parser.add_argument('--train-end-date', type=str, default='2023-12-31', help='学習期間の終了日')
    parser.add_argument('--test-start-date', type=str, default='2024-01-01', help='評価期間の開始日')
    parser.add_argument('--tune', action='store_true', help='ハイパーパラメータチューニングを実行します。')
    parser.add_argument('--direction', type=str, default='up', choices=['up', 'down'], help="予測するトレンドの方向 ('up' または 'down')")
    parser.add_argument('--threshold', type=float, default=0.03, help='変動率の閾値 (例: 0.03は3%%)')
    parser.add_argument('--prediction-days', type=int, default=10, help='予測期間（日数）')
    args = parser.parse_args()

    # 引数でfeature_tickersが指定されなかった場合、tickers.jsonから読み込む
    if args.feature_tickers is None:
        try:
            with open('tickers.json', 'r', encoding='utf-8') as f:
                tickers_data = json.load(f)
            target_ticker_info = next((item for item in tickers_data if item["ticker_symbol"] == args.ticker), None)
            if target_ticker_info and 'feature_tickers' in target_ticker_info:
                feature_tickers = target_ticker_info['feature_tickers']
            else:
                feature_tickers = []
        except (FileNotFoundError, json.JSONDecodeError):
            feature_tickers = []
    else:
        print("警告: --feature-tickers引数は非推奨です。tickers.jsonの設定が優先されます。")
        feature_tickers = args.feature_tickers

    run_backtest(args.ticker, feature_tickers, args.train_end_date, args.test_start_date, args.tune, args.direction, args.threshold, args.prediction_days)

if __name__ == "__main__":
    main()
