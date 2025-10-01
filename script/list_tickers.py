import pandas as pd
from db_connector import get_db_connection

def list_available_tickers():
    """データベースに登録されている銘柄コードのサンプルを一覧表示する"""
    print("--- データベースに接続して銘柄コードを取得します ---")
    conn = None
    try:
        conn, _ = get_db_connection()
        if conn is None:
            print("データベース接続の取得に失敗しました。")
            return

        # 登録されている銘柄コードを100件取得
        query = "SELECT DISTINCT ticker_symbol FROM daily_stock_prices LIMIT 100;"
        df = pd.read_sql(query, conn)
        
        if df.empty:
            print("データベースに銘柄データが見つかりません。")
        else:
            print("\n--- 利用可能な銘柄コード (サンプル) ---")
            for ticker in df['ticker_symbol']:
                print(ticker)
            print("-" * 35)

    except Exception as e:
        print(f"処理中にエラーが発生しました: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    list_available_tickers()