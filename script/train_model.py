from sklearnex import patch_sklearn
patch_sklearn()

import pandas as pd
import numpy as np
import datetime
import lightgbm as lgb
import argparse
import json
import os
import joblib
import io
import optuna
import sqlite3
from sklearn.model_selection import train_test_split, GridSearchCV, RandomizedSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    roc_curve, precision_recall_curve, confusion_matrix
)
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import uniform, randint

from db_connector import DBConnector
from stock_utils import (
    PLOTS_OUTPUT_DIR,
    load_all_data, create_features
)
from config_loader import config_loader

# --- Classification Task Settings ---
PREDICTION_HORIZON, RETURN_THRESHOLD = config_loader.get_target_settings()


def create_classification_target(df, horizon, threshold, direction='up'):
    """Creates a binary classification target based on the specified direction."""
    df_copy = df.copy()
    future_price = df_copy['adj_close_price'].shift(-horizon)
    df_copy[f'target_return_{horizon}d'] = (future_price - df_copy['adj_close_price']) / df_copy['adj_close_price']

    target_col_name = f'target_{horizon}d_{direction}_{int(threshold*100)}pct'

    if direction == 'up':
        df_copy[target_col_name] = (df_copy[f'target_return_{horizon}d'] >= threshold).astype(int)
    elif direction == 'down':
        df_copy[target_col_name] = (df_copy[f'target_return_{horizon}d'] <= -threshold).astype(int)
    else:
        raise ValueError("direction must be either 'up' or 'down'")

    return df_copy, target_col_name


def save_model_to_db(db_connector, ticker, model_name, model, scaler, feature_list, hyperparameters, performance_metrics, notes=""):
    """Saves a trained model and its metadata to the database."""
    new_version = -1
    try:
        with db_connector.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MAX(model_version) FROM trained_models WHERE ticker_symbol = ? AND model_name = ?", (ticker, model_name))
            max_version = cur.fetchone()[0]
            new_version = (max_version or 0) + 1

            model_buffer = io.BytesIO()
            joblib.dump(model, model_buffer)
            model_bytes = model_buffer.getvalue()

            scaler_buffer = io.BytesIO()
            joblib.dump(scaler, scaler_buffer)
            scaler_bytes = scaler_buffer.getvalue()

            insert_data = (
                model_name,
                new_version,
                ticker,
                json.dumps(feature_list),
                model_bytes,
                scaler_bytes,
                json.dumps(hyperparameters),
                json.dumps(performance_metrics),
                notes
            )

            cur.execute(
                """INSERT INTO trained_models (model_name, model_version, ticker_symbol, feature_list, model_object, scaler_object, hyperparameters, performance_metrics, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                insert_data
            )
            conn.commit()
            print(f"モデル '{model_name}' version {new_version} をデータベースに保存しました。")
            return new_version

    except Exception as e:
        print(f"データベースへのモデル保存中にエラーが発生しました: {e}")
        return -1


def plot_roc_curve(y_true, y_pred_proba, ticker, direction):
    # (Implementation unchanged)
    pass


def plot_precision_recall_curve(y_true, y_pred_proba, ticker, direction):
    # (Implementation unchanged)
    pass


def plot_feature_importance(importances, feature_names, ticker, direction):
    # (Implementation unchanged)
    pass


def train_and_evaluate_classification(db_connector, X_train, y_train, X_test, y_test, target_col, ticker, direction, test_mode=False, search_method='random', save_model=True):
    scaler = StandardScaler()
    numeric_features = X_train.select_dtypes(include=np.number).columns.tolist()

    X_train_scaled = X_train.copy()
    X_test_scaled = X_test.copy()
    X_train_scaled[numeric_features] = scaler.fit_transform(X_train[numeric_features])
    X_test_scaled[numeric_features] = scaler.transform(X_test[numeric_features])

    neg_count = y_train.value_counts().get(0, 0)
    pos_count = y_train.value_counts().get(1, 0)
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1
    print(f"クラスの不均衡を調整します。Positive class weight: {scale_pos_weight:.2f}")

    tscv = TimeSeriesSplit(n_splits=3)
    best_params = {}
    hp_settings = config_loader.get_hp_search_settings(test_mode)

    if search_method == 'grid':
        print("\n--- ハイパーパラメータチューニングを開始 (Grid Search) ---")
        param_grid = hp_settings['grid_params']

        base_model = lgb.LGBMClassifier(objective='binary', random_state=42, verbose=-1, scale_pos_weight=scale_pos_weight)
        searcher = GridSearchCV(estimator=base_model, param_grid=param_grid, scoring='roc_auc', n_jobs=-1, cv=tscv)
        searcher.fit(X_train_scaled, y_train)
        best_params = searcher.best_params_

    elif search_method == 'random':
        print("\n--- ハイパーパラメータチューニングを開始 (Random Search) ---")
        param_distributions = {
            'n_estimators': randint(100, 1000),
            'learning_rate': uniform(0.01, 0.2),
            'num_leaves': randint(20, 100),
            'reg_alpha': uniform(0.0, 1.0),
            'reg_lambda': uniform(0.0, 1.0),
        }
        n_iter = hp_settings['random_n_iter']
        base_model = lgb.LGBMClassifier(objective='binary', random_state=42, verbose=-1, scale_pos_weight=scale_pos_weight)
        searcher = RandomizedSearchCV(estimator=base_model, param_distributions=param_distributions, n_iter=n_iter, scoring='roc_auc', n_jobs=-1, cv=tscv, random_state=42)
        searcher.fit(X_train_scaled, y_train)
        best_params = searcher.best_params_

    elif search_method == 'optuna':
        print("\n--- ハイパーパラメータチューニングを開始 (Optuna) ---")
        def objective(trial):
            params = {
                'objective': 'binary',
                'metric': 'roc_auc',
                'random_state': 42,
                'verbose': -1,
                'scale_pos_weight': scale_pos_weight,
                'n_estimators': trial.suggest_int('n_estimators', 100, 2000),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'num_leaves': trial.suggest_int('num_leaves', 20, 300),
                'max_depth': trial.suggest_int('max_depth', 3, 12),
                'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
            }

            scores = []
            for train_idx, val_idx in tscv.split(X_train_scaled):
                X_train_split, X_val_split = X_train_scaled.iloc[train_idx], X_train_scaled.iloc[val_idx]
                y_train_split, y_val_split = y_train.iloc[train_idx], y_train.iloc[val_idx]

                model = lgb.LGBMClassifier(**params)
                model.fit(X_train_split, y_train_split)
                score = roc_auc_score(y_val_split, model.predict_proba(X_val_split)[:, 1])
                scores.append(score)

            return np.mean(scores)

        n_trials = hp_settings['optuna_n_trials']
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials)
        best_params = study.best_params


    print(f"最適なパラメータが見つかりました: {best_params}")
    final_model = lgb.LGBMClassifier(objective='binary', random_state=42, verbose=-1, scale_pos_weight=scale_pos_weight, **best_params)

    print(f"\n--- 最適なパラメータでモデルを学習中 ---")
    final_model.fit(X_train_scaled, y_train)

    y_pred_proba = final_model.predict_proba(X_test_scaled)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)

    performance_metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1_score": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_pred_proba)
    }

    print(f"\n--- 分類モデルの評価 ---")
    for key, value in performance_metrics.items():
        print(f"  {key}: {value:.4f}")
    print("\n  Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # (Plotting functions remain unchanged)

    model_version = -1
    if save_model:
        model_name = f"LGBM_{PREDICTION_HORIZON}d_{direction}_{int(RETURN_THRESHOLD*100)}pct"
        feature_list = X_train.columns.tolist()
        print("\n--- モデルをデータベースに保存中 ---")
        model_version = save_model_to_db(
            db_connector=db_connector,
            ticker=ticker,
            model_name=model_name,
            model=final_model,
            scaler=scaler,
            feature_list=feature_list,
            hyperparameters=best_params,
            performance_metrics=performance_metrics,
            notes=f"Trained on {datetime.date.today().isoformat()} with {search_method} search."
        )

    return final_model, scaler, best_params, performance_metrics, model_version

def main():
    parser = argparse.ArgumentParser(description="指定された銘柄の株価がN日後にX%以上変動するかを予測する分類モデルを学習します。")
    parser.add_argument('--ticker', type=str, required=True, help="予測対象のティッカーシンボル (例: AAPL, 7203.T)")
    parser.add_argument('--direction', type=str, default='up', choices=['up', 'down'], help="予測するトレンドの方向 ('up' または 'down')")
    parser.add_argument('--search-method', type=str, default='random', choices=['grid', 'random', 'optuna'], help="ハイパーパラメータの探索方法 ('grid', 'random', 'optuna')")
    parser.add_argument('--test-mode', action='store_true', help="テストモードを有効にし、ハイパーパラメータの探索範囲を狭めます。")
    parser.add_argument('--training-years', type=int, default=5, help="学習に使うデータ期間を年数で指定します。")
    parser.add_argument('--test-size', type=float, default=0.2, help="学習期間内のデータのうち、テスト用として確保する割合。")
    args = parser.parse_args()
    ticker = args.ticker
    direction = args.direction

    db_connector = DBConnector()
    try:
        with db_connector.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT features FROM target_tickers WHERE ticker = ?", (ticker,))
            result = cursor.fetchone()
            feature_tickers = result[0].split(',') if result and result[0] else []
    except Exception as e:
        print(f"データベースからの特徴量取得エラー: {e}。外部指標なしで続行します。")
        feature_tickers = []

    direction_jp = "上昇" if direction == 'up' else "下落"
    print(f"--- 株価{direction_jp}分類モデル学習スクリプト ---")
    print(f"対象銘柄: {ticker}, 予測期間: {PREDICTION_HORIZON}日, 変動閾値: {RETURN_THRESHOLD*100}%, 方向: {direction}")
    if args.test_mode:
        print("*** テストモードで実行中 ***")

    main_data, external_data, macro_data = load_all_data(db_connector, ticker, feature_tickers)
    if main_data.empty:
        print("データ読み込みに失敗しました。処理を終了します。")
        return

    features_df = create_features(main_data, external_data, macro_data)
    targets_df, target_col = create_classification_target(features_df, PREDICTION_HORIZON, RETURN_THRESHOLD, direction)

    final_df = targets_df.dropna()

    latest_date = final_df.index.max()
    start_date = latest_date - pd.DateOffset(years=args.training_years)
    window_df = final_df.loc[start_date:]
    print(f"\n学習ウィンドウ: {start_date.date()} から {latest_date.date()} まで ({len(window_df)}件)")

    features_columns = features_df.columns.intersection(window_df.columns)
    X = window_df[features_columns]
    y = window_df[target_col]

    train_size = int(len(X) * (1 - args.test_size))
    X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
    y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]

    print(f"訓練データ: {len(X_train)}件, テストデータ: {len(X_test)}件")

    train_and_evaluate_classification(db_connector, X_train, y_train, X_test, y_test, target_col, ticker, direction, args.test_mode, args.search_method)

    print("\n--- モデル学習スクリプトが完了しました。 ---")


if __name__ == "__main__":
    main()
