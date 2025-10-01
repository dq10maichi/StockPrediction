import argparse
import json
import joblib
import io
import pandas as pd
from db_connector import get_db_connection
import sqlite3

def get_model_info(ticker, model_name):
    """指定されたモデルの情報をデータベースから取得して表示する"""
    conn = None
    try:
        conn, _ = get_db_connection()
        if conn is None:
            print("データベース接続に失敗しました。")
            return

        with conn.cursor() as cur:
            # 最新バージョンのモデルを取得
            query = """
                SELECT model_version, hyperparameters, feature_list, creation_timestamp, model_object
                FROM trained_models
                WHERE ticker_symbol = ? AND model_name = ?
                ORDER BY model_version DESC
                LIMIT 1;
            """
            cur.execute(query, (ticker, model_name))
            result = cur.fetchone()

            if result:
                version, hyperparameters_json, feature_list_json, timestamp, model_bytes = result
                hyperparameters = json.loads(hyperparameters_json)
                feature_list = json.loads(feature_list_json)

                print(f"--- モデル情報: {model_name} (銘柄: {ticker}) ---")
                print(f"  最新バージョン: {version}")
                print(f"  学習日時: {timestamp}")
                
                print("\n--- ハイパーパラメータ ---")
                print(json.dumps(hyperparameters, indent=4, ensure_ascii=False))
                
                # モデルをデシリアライズして特徴量の重要度を取得
                model = joblib.load(io.BytesIO(model_bytes))
                
                print("\n--- 特徴量の重要度 (Top 20) ---")
                feature_importances = pd.DataFrame(
                    {'feature': feature_list, 'importance': model.feature_importances_}
                ).sort_values('importance', ascending=False)
                
                print(feature_importances.head(20).to_string(index=False))

                print("\n--- 全特徴量リスト ---")
                # 見やすいように1行に5つずつ表示
                for i in range(0, len(feature_list), 5):
                    print("  " + ", ".join(feature_list[i:i+5]))
            else:
                print(f"モデル '{model_name}' (銘柄: {ticker}) はデータベースに見つかりません。")

    except Exception as e:
        print(f"情報の取得中にエラーが発生しました: {e}")
    finally:
        if conn:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="データベースから学習済みモデルの情報を取得します。")
    parser.add_argument('--ticker', type=str, required=True, help="対象のティッカーシンボル")
    parser.add_argument('--model-name', type=str, required=True, help="対象のモデル名 (例: LGBM_10d_down_3pct)")
    args = parser.parse_args()

    get_model_info(args.ticker, args.model_name)

if __name__ == "__main__":
    main()