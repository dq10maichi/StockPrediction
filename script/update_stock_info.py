import argparse
import sys
from pathlib import Path
import yfinance as yf
import sqlite3

# プロジェクトのルートディレクトリをsys.pathに追加
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from script.db_connector import DBConnector


def update_stock_info(db_connector, ticker):
    """
    yfinanceから銘柄情報を取得し、stock_infoテーブルを更新（UPSERT）する
    """
    print(f"--- 銘柄 {ticker} の情報を yfinance から取得しています... ---")
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info

        # yfinanceから必須情報が取得できない場合は処理を中断
        company_name = info.get('longName') or info.get('shortName')
        if not company_name:
            print(f"警告: {ticker} の会社名が取得できませんでした。stock_infoテーブルの更新をスキップします。")
            return False

        # 取得した情報を辞書にまとめる
        stock_data = {
            'ticker_symbol': ticker,
            'company_name': company_name,
            'exchange': info.get('exchange'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'country': info.get('country'),
            'currency': info.get('currency')
        }

        # Noneの値を削除
        stock_data = {k: v for k, v in stock_data.items() if v is not None}

        print(f"取得した情報: {stock_data}")

    except Exception as e:
        print(f"エラー: yfinanceでの情報取得中にエラーが発生しました - {e}")
        return False

    print(f"--- データベースの stock_info テーブルを更新しています... ---")
    try:
        with db_connector.connect() as conn:
            cursor = conn.cursor()
            # 登録済みのカラムを取得
            cursor.execute(f"PRAGMA table_info(stock_info);")
            existing_columns = [row[1] for row in cursor.fetchall()]

            # 登録データのうち、テーブルに存在するカラムのみを対象とする
            update_data = {k: v for k, v in stock_data.items() if k in existing_columns}

            if not update_data:
                print("警告: データベースに登録するデータがありません。")
                return False

            columns = ", ".join(update_data.keys())
            placeholders = ", ".join(["?"] * len(update_data))

            # ON CONFLICT (UPSERT) クエリの動的生成
            update_assignments = ", ".join([f"{key} = excluded.{key}" for key in update_data.keys() if key != 'ticker_symbol'])

            query = f"""
                INSERT INTO stock_info ({columns})
                VALUES ({placeholders})
                ON CONFLICT (ticker_symbol) DO UPDATE SET
                    {update_assignments};
            """

            cursor.execute(query, list(update_data.values()))
            conn.commit()
        print(f"銘柄 {ticker} の情報を stock_info テーブルに正常に登録/更新しました。")
        return True
    except Exception as e:
        print(f"エラー: データベースの更新に失敗しました - {e}")
        return False


def main():
    """
    コマンドライン引数からティッカーを受け取り、情報を更新する
    """
    parser = argparse.ArgumentParser(description="指定された銘柄の会社情報を yfinance から取得し、データベースを更新します。")
    parser.add_argument("--ticker", required=True, help="更新対象の銘柄コード (例: 7203.T)")
    args = parser.parse_args()

    db_connector = DBConnector()
    update_stock_info(db_connector, args.ticker)


if __name__ == "__main__":
    main()