import argparse
import json
from db_connector import get_db_connection
import datetime

def list_models():
    conn = None
    try:
        conn, _ = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    ticker_symbol, 
                    model_name, 
                    model_version, 
                    notes, 
                    performance_metrics,
                    hyperparameters,
                    creation_timestamp
                FROM trained_models
                ORDER BY ticker_symbol, model_name, model_version DESC
            """)
            models = cur.fetchall()

            if not models:
                print("データベースに学習済みモデルが見つかりません。")
                return

            print("--- 学習済みモデル一覧 ---")
            current_ticker = None
            current_model_name = None

            for model in models:
                ticker_symbol, model_name, model_version, notes, performance_metrics_json, hyperparameters_json, creation_timestamp_str = model

                if ticker_symbol != current_ticker:
                    print(f"\n銘柄: {ticker_symbol}")
                    current_ticker = ticker_symbol
                    current_model_name = None # Reset model name for new ticker

                if model_name != current_model_name:
                    print(f"  モデル名: {model_name}")
                    current_model_name = model_name
                
                # Extract direction from model_name
                direction = "不明"
                if "up" in model_name:
                    direction = "up"
                elif "down" in model_name:
                    direction = "down"

                creation_timestamp = datetime.datetime.fromisoformat(creation_timestamp_str)
                print(f"    バージョン: {model_version} (作成日: {creation_timestamp.strftime('%Y-%m-%d %H:%M:%S')})")
                print(f"      方向: {direction}")
                if notes:
                    print(f"      備考: {notes}")
                
                if performance_metrics_json:
                    performance_metrics = json.loads(performance_metrics_json)
                    print("      パフォーマンス:")
                    for metric, value in performance_metrics.items():
                        print(f"        {metric}: {value:.4f}")
                
                if hyperparameters_json:
                    hyperparameters = json.loads(hyperparameters_json)
                    print("      ハイパーパラメータ:")
                    for param, value in hyperparameters.items():
                        print(f"        {param}: {value}")
                print("-" * 40)

    except Exception as e:
        print(f"モデル一覧の取得中にエラーが発生しました: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    list_models()