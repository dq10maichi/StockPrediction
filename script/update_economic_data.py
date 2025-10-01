import pandas_datareader.data as web
import datetime
import pandas as pd
import argparse
import sqlite3
from db_connector import get_db_connection

# デフォルトの経済指標
DEFAULT_FRED_SERIES = {
    'CPIAUCSL': 'cpi',
    'UNRATE': 'unemployment_rate',
    'FEDFUNDS': 'fed_funds_rate',
    'DGS10': '10y_treasury_yield'
}


def update_economic_data(fred_series_ids, start_date='2010-01-01'):
    """FREDから経済指標データを取得し、データベースを更新する"""
    print(f"--- 経済指標データ更新スクリプト開始: {datetime.datetime.now()} ---")

    conn = None
    try:
        end_date = datetime.date.today()
        print(f"FREDからデータを取得中... (期間: {start_date} - {end_date})")
        # 引数で渡されたIDリストを使ってデータを取得
        df_fred = web.DataReader(list(fred_series_ids.keys()), 'fred', start_date, end_date)

        df_fred.rename(columns=fred_series_ids, inplace=True)
        df_fred.index.name = 'indicator_date'

        df_daily = df_fred.resample('D').ffill()

        conn, _ = get_db_connection()
        if conn is None:
            print("データベース接続の取得に失敗したため、処理を中止します。")
            return

        with conn:
            cursor = conn.cursor()

            print("データベースに経済指標を挿入/更新しています...")
            insert_count = 0
            for series_id, series in df_daily.items():
                for date, value in series.dropna().items():
                    cursor.execute(
                        """
                        INSERT INTO macro_economic_indicators (series_id, indicator_date, value)
                        VALUES (?, ?, ?)
                        ON CONFLICT (series_id, indicator_date) DO UPDATE SET
                            value = EXCLUDED.value,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (series_id, date.strftime('%Y-%m-%d'), float(value))
                    )
                    insert_count += 1

            conn.commit()
            print(f"{insert_count}件の経済指標データをデータベースに挿入/更新しました。")

    except Exception as e:
        print(f"経済指標データの更新中にエラーが発生しました: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("--- データベース接続を閉じました ---")

    print(f"--- 経済指標データ更新スクリプト終了: {datetime.datetime.now()} ---")


def main():
    parser = argparse.ArgumentParser(description="FREDから経済指標を取得し、データベースに保存します。")
    parser.add_argument(
        '--indicators', 
        nargs='+', 
        default=None,
        help="取得するFREDシリーズIDと名前のペアを 'ID:name' の形式で指定します (例: GDP:gdp ICSA:initial_claims)。指定がない場合はデフォルトの指標リストを使用します。"
    )
    args = parser.parse_args()

    if args.indicators:
        try:
            # 'ID:name' の形式の引数を辞書に変換
            fred_series = {item.split(':')[0]: item.split(':')[1] for item in args.indicators}
        except IndexError:
            print("エラー: --indicators引数の形式が正しくありません。'ID:name' の形式で指定してください。")
            return
    else:
        # 引数が指定されなかった場合はデフォルト値を使用
        print("指標の指定がないため、デフォルトのリストを使用します。")
        fred_series = DEFAULT_FRED_SERIES

    print(f"取得対象の指標: {fred_series}")
    update_economic_data(fred_series)


if __name__ == '__main__':
    main()