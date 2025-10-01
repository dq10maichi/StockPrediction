import pandas as pd
import numpy as np
import datetime
import os
import joblib

# 共通モジュールから設定と関数をインポート
from stock_utils import (
    TARGET_TICKER, PREDICTION_DAYS, MODELS_DIR, PREDICTION_OUTPUT_DIR,
    MODEL_FILENAME, SCALER_FILENAME, DEFAULT_PROB_THRESHOLD,
    fetch_data, create_features
)

def predict_future_trend():
    """学習済みモデルをロードし、最新データに基づいて未来のトレンドを予測する"""
    model_path = os.path.join(MODELS_DIR, MODEL_FILENAME)
    scaler_path = os.path.join(MODELS_DIR, SCALER_FILENAME)

    # モデルとスケーラーが存在するか確認
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        print(f"エラー: モデル({model_path})またはスケーラー({scaler_path})が見つかりません。")
        print("先に train_model.py を実行して、モデルを学習・保存してください。")
        return

    # モデルとスケーラーをロード
    try:
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        print("モデルとスケーラーを正常にロードしました。")
    except Exception as e:
        print(f"モデルまたはスケーラーのロード中にエラーが発生しました: {e}")
        return

    # 予測のための最新データを取得
    print(f"\n予測のため {TARGET_TICKER} の最新データを取得しています...")
    df_raw = fetch_data(TARGET_TICKER)
    if df_raw.empty:
        print(f"エラー: {TARGET_TICKER} の株価データが見つかりません。")
        return
    
    # 特徴量を生成
    df_features = create_features(df_raw)
    if df_features.empty:
        print("エラー: 特徴量を作成できませんでした。データが不足している可能性があります。")
        return

    # 予測に使用する最新のデータポイント（最終行）を取得
    latest_data = df_features.iloc[[-1]]
    latest_date = latest_data.index[0].strftime('%Y-%m-%d')
    print(f"予測基準日: {latest_date}")

    # スケーリング対象の特徴量リストを特定
    numeric_features = [f for f in latest_data.columns if latest_data[f].dtype in ['int64', 'float64'] and f not in 
                        ['open_price', 'high_price', 'low_price', 'close_price', 'adj_close_price', 'volume']]
    
    features_for_prediction = [col for col in df_features.columns if col not in 
                               ['open_price', 'high_price', 'low_price', 'close_price', 'adj_close_price', 'volume', 'target']]

    # 最新データから予測用の特徴量を選択
    X_latest = latest_data[features_for_prediction]
    
    # スケーリングを適用
    X_latest_scaled = X_latest.copy()
    X_latest_scaled[numeric_features] = scaler.transform(X_latest[numeric_features])

    # 予測を実行
    pred_proba = model.predict_proba(X_latest_scaled)[:, 1]
    prediction = (pred_proba > DEFAULT_PROB_THRESHOLD).astype(int)[0]

    print("\n--- 予測結果 ---")
    print(f"  {PREDICTION_DAYS}営業日後の株価トレンド予測")
    print(f"  上昇する確率: {pred_proba[0]:.2%}")
    print(f"  予測: {'上昇' if prediction == 1 else '下落'}")

    # 予測結果を保存
    os.makedirs(PREDICTION_OUTPUT_DIR, exist_ok=True)
    prediction_filename = os.path.join(PREDICTION_OUTPUT_DIR, f"{TARGET_TICKER}_prediction_{datetime.date.today().strftime('%Y%m%d')}.csv")
    
    prediction_data = {
        'prediction_datetime_utc': datetime.datetime.utcnow(),
        'target_ticker': TARGET_TICKER,
        'last_data_date': latest_date,
        'prediction_days': PREDICTION_DAYS,
        'probability_up': pred_proba[0],
        'predicted_trend': prediction
    }
    pd.DataFrame([prediction_data]).to_csv(prediction_filename, index=False)
    print(f"\n予測結果を '{prediction_filename}' に保存しました。")

def main():
    print(f"--- 株価トレンド予測実行スクリプト開始: {datetime.datetime.now()} ---")
    predict_future_trend()
    print(f"\n--- 株価トレンド予測実行スクript終了: {datetime.datetime.now()} ---")

if __name__ == "__main__":
    main()
