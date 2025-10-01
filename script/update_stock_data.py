import yfinance as yf
import pandas as pd
import sqlite3
import datetime
import time
import json
import argparse
from db_connector import get_db_connection

# --- 設定 ---
REQUEST_DELAY_SECONDS = 0.5
LOOKBACK_DAYS = 7


def insert_stock_info(conn):
    """
    データベースに銘柄情報を登録する
    """
    print("--- 銘柄情報設定を開始 ---")

    # tickers.jsonファイルから銘柄リストを読み込む
    try:
        # スクリプトの実行場所からの相対パス
        with open('tickers.json', 'r', encoding='utf-8') as f:
            tickers_data = json.load(f)
    except FileNotFoundError:
        print("エラー: tickers.jsonファイルが見つかりません。ticker情報を登録できませんでした。")
        return
    except json.JSONDecodeError:
        print("エラー: tickers.jsonファイルの形式が正しくありません。")
        return

    # データベースに挿入するために、辞書のリストをタプルのリストに変換
    stocks_to_add = [
        (
            t.get('ticker_symbol'), t.get('company_name'), t.get('exchange'),
            t.get('sector'), t.get('industry'), t.get('country'), t.get('currency')
        )
        for t in tickers_data
    ]

    if not stocks_to_add:
        print("登録する銘柄情報がありません。")
        return

    with conn:
        cursor = conn.cursor()
        # ON CONFLICT (ticker_symbol) DO NOTHING を使い、既に存在するティッカーは無視する
        insert_query = """
            INSERT OR IGNORE INTO stock_info (ticker_symbol, company_name, exchange, sector, industry, country, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        cursor.executemany(insert_query, stocks_to_add)
        conn.commit()
        print(f"{cursor.rowcount}件の新しい銘柄が登録されました。")
    print("--- 銘柄情報設定が完了 ---")


def get_tickers_from_db(conn):
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticker_symbol FROM stock_info")
        tickers = [row[0] for row in cursor.fetchall()]
        return tickers


def get_last_trade_date_from_db(conn, ticker_symbol):
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(trade_date) FROM daily_stock_prices WHERE ticker_symbol = ?",
            (ticker_symbol,)
        )
        result = cursor.fetchone()[0]
        # SQLite returns string, convert to date
        if result:
            return datetime.datetime.strptime(result, '%Y-%m-%d').date()
        return None


def insert_or_update_daily_prices(conn, df_prices):
    if df_prices.empty:
        print("    更新するデータがありません。")
        return

    with conn:
        cursor = conn.cursor()
        # データをタプルのリストに変換
        data_to_insert = [
            (
                row['ticker_symbol'],
                index.date().strftime('%Y-%m-%d'),
                row['Open'],
                row['High'],
                row['Low'],
                row['Close'],
                row['Adj Close'],
                row['Volume']
            )
            for index, row in df_prices.iterrows()
        ]

        # ON CONFLICT を使用したUPSERTクエリ
        upsert_query = """
            INSERT INTO daily_stock_prices (
                ticker_symbol, trade_date, open_price, high_price, low_price,
                close_price, adj_close_price, volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (ticker_symbol, trade_date) DO UPDATE SET
                open_price = excluded.open_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                close_price = excluded.close_price,
                adj_close_price = excluded.adj_close_price,
                volume = excluded.volume,
                updated_at = CURRENT_TIMESTAMP;
        """

        try:
            cursor.executemany(upsert_query, data_to_insert)
            conn.commit()
            print(f"    {len(data_to_insert)}件のデータをデータベースに挿入/更新しました。")
        except sqlite3.Error as e:
            conn.rollback()
            print(f"    データベースへの挿入/更新中にエラーが発生しました: {e}")


def validate_data_quality(df, ticker):
    """取得したデータの品質を検証する"""
    is_valid = True
    # 1. 重要なカラムの欠損値チェック
    if df['Adj Close'].isnull().any():
        print(f"  [警告] 銘柄 {ticker}: 'Adj Close' に欠損値が見つかりました。")
        # 全て欠損している場合は、このデータを無効とする
        if df['Adj Close'].isnull().all():
            print(f"  [エラー] 銘柄 {ticker}: 'Adj Close' が全て欠損値です。このデータはスキップされます。")
            is_valid = False

    # 2. 異常な価格変動のチェック (前日比50%以上の変動)
    adj_close_no_nan = df['Adj Close'].dropna()
    if len(adj_close_no_nan) > 1:
        daily_return = adj_close_no_nan.pct_change().abs()
        # .any() を使って、異常値が一つでも存在するかを単一のbool値として評価する
        if (daily_return > 0.5).any():
            abnormal_changes = daily_return[daily_return > 0.5]
            for date, change in abnormal_changes.items():
                print(f"  [警告] 銘柄 {ticker}: {date.strftime('%Y-%m-%d')}に異常な価格変動 ({change:.2%}) を検出しました。株式分割等の可能性があります。")

    return is_valid


def main():
    parser = argparse.ArgumentParser(description="株価データをyfinanceから取得し、データベースを更新します。")
    parser.add_argument('--tickers', nargs='*', default=None, help="更新対象のティッカーシンボル（複数指定可）。指定しない場合はDB内の全銘柄が対象。）")
    args = parser.parse_args()

    print(f"--- 株価データ取得スクリプト開始: {datetime.datetime.now()} ---")
    conn, tunnel = None, None
    try:
        conn, _ = get_db_connection()
        if conn is None:
            print("データベース接続の取得に失敗したため、処理を中止します。")
            return

        if args.tickers:
            tickers = args.tickers
            print(f"コマンドライン引数から対象銘柄を取得しました: {len(tickers)}件")
        else:
            print("DBから対象銘柄を取得します。")
            insert_stock_info(conn)
            tickers = get_tickers_from_db(conn)

        if not tickers:
            print("取得対象の銘柄が登録されていません。")
            return

        print(f"取得対象銘柄数: {len(tickers)}")

        for ticker in tickers:
            print(f"\n銘柄: {ticker} のデータを取得中...")
            last_date = get_last_trade_date_from_db(conn, ticker)

            if last_date:
                start_date_yf = last_date - datetime.timedelta(days=LOOKBACK_DAYS)
                print(f"  データベース上の最新データ日: {last_date.strftime('%Y-%m-%d')}")
                print(f"  yfinanceからの取得開始日: {start_date_yf.strftime('%Y-%m-%d')}")
            else:
                start_date_yf = datetime.date.today() - datetime.timedelta(days=365 * 10)
                print(f"  過去データがありません。{start_date_yf.strftime('%Y-%m-%d')} から取得します。")

            end_date_yf = datetime.date.today() + datetime.timedelta(days=1)
            df = yf.download(ticker, start=start_date_yf, end=end_date_yf, progress=False, auto_adjust=False, actions=False)

            if df.empty:
                print(f"  '{ticker}' のデータを取得できませんでした。")
                continue

            # yfinanceが返すMultiIndexをフラットなカラム名に修正
            df.columns = df.columns.get_level_values(0)

            # データ品質を検証
            if not validate_data_quality(df, ticker):
                continue

            df['ticker_symbol'] = ticker

            insert_or_update_daily_prices(conn, df)
            time.sleep(REQUEST_DELAY_SECONDS)

    except Exception as e:
        print(f"スクリプト実行中に予期せぬエラーが発生しました: {e}")
    finally:
        if conn:
            conn.close()
            print(f"\n--- データベース接続を閉じました ---")

    print(f"--- 株価データ取得スクリプト終了: {datetime.datetime.now()} ---")


if __name__ == "__main__":
    main()
