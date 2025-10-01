
import pandas as pd
import datetime
import csv
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from script.db_connector import DBConnector
from script.predict import predict_ticker # We will create this function in predict.py

PREDICTIONS_DIR = project_root / "predictions"

def save_results_to_db(db_connector, results):
    """Saves a list of prediction results to the database."""
    if not results:
        return

    print("--- 予測結果をデータベースに保存中 ---")
    try:
        with db_connector.connect() as conn:
            with conn.cursor() as cur:
                for result in results:
                    cur.execute(
                        """
                        INSERT INTO prediction_results (target_date, ticker, direction, probability, model_name, model_version)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            result['target_date'],
                            result['ticker'],
                            result['direction'],
                            float(result['probability']),
                            result['model_name'],
                            result['model_version']
                        )
                    )
                conn.commit()
        print(f"{len(results)}件の予測結果をデータベースに保存しました。")
    except Exception as e:
        print(f"データベースへの結果保存中にエラーが発生しました: {e}")

def save_results_to_csv(results):
    """Saves a list of prediction results to a CSV file."""
    if not results:
        return

    PREDICTIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filepath = PREDICTIONS_DIR / f"predictions_{timestamp}.csv"

    print(f"--- 予測結果をCSVファイルに保存中: {filepath} ---")
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print("CSVファイルへの保存が完了しました。")
    except Exception as e:
        print(f"CSVファイルへの保存中にエラーが発生しました: {e}")

def main():
    """Fetches all target tickers and runs prediction for each."""
    print("--- 全監視銘柄の予測を開始します ---")
    db_connector = DBConnector()
    all_results = []

    try:
        with db_connector.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT ticker FROM target_tickers ORDER BY ticker")
                tickers = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"データベースからの監視銘柄リストの取得に失敗しました: {e}")
        sys.exit(1)

    if not tickers:
        print("監視対象の銘柄が登録されていません。処理を終了します。")
        return

    print(f"予測対象の銘柄 ({len(tickers)}件): {tickers}")

    for ticker in tickers:
        for direction in ['up', 'down']:
            print(f"\n--- 銘柄: {ticker}, 方向: {direction} の予測を実行 ---")
            result = predict_ticker(db_connector, ticker, direction)
            if result:
                all_results.append(result)
    
    if all_results:
        save_results_to_db(db_connector, all_results)
        save_results_to_csv(all_results)

    print("\n--- 全ての予測処理が完了しました。 ---")

if __name__ == "__main__":
    main()
