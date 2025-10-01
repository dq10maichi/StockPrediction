import argparse
import sys
from pathlib import Path
import sqlite3

# プロジェクトのルートディレクトリをsys.pathに追加
# これにより、他のモジュール (db_connectorなど) を直接インポートできる
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from script.db_connector import DBConnector
from script.update_stock_info import update_stock_info


def list_tickers(connector):
    """データベースに登録されているすべての監視銘柄を一覧表示する"""
    print("--- 監視銘柄リスト ---")
    try:
        with connector.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, features FROM target_tickers ORDER BY ticker")
            tickers = cursor.fetchall()
            if not tickers:
                print("監視銘柄はまだ登録されていません。")
            else:
                print(f"{'TICKER':<15} FEATURES")
                print("-" * 40)
                for ticker, features in tickers:
                    print(f"{ticker:<15} {features}")
    except Exception as e:
        print(f"エラー: 銘柄リストの取得に失敗しました - {e}")
        sys.exit(1)


def add_ticker(connector, ticker, features):
    """新しい監視銘柄と特徴量をデータベースに追加する"""
    if not ticker or not features:
        print("エラー: 銘柄コードと特徴量の両方を指定してください。")
        sys.exit(1)

    print(f"銘柄 '{ticker}' を特徴量 '{features}' で追加しています...")
    try:
        with connector.connect() as conn:
            cursor = conn.cursor()
            # 存在する場合は更新、しない場合は挿入 (UPSERT)
            cursor.execute(
                """
                INSERT INTO target_tickers (ticker, features)
                VALUES (?, ?)
                ON CONFLICT (ticker) DO UPDATE SET
                    features = excluded.features;
                """,
                (ticker, features)
            )
            conn.commit()
        print(f"銘柄 '{ticker}' の追加/更新が完了しました。")

        # stock_infoテーブルも更新する
        update_stock_info(connector, ticker)

    except Exception as e:
        print(f"エラー: 銘柄の追加に失敗しました - {e}")
        sys.exit(1)


def remove_ticker(connector, ticker):
    """指定された監視銘柄をデータベースから削除する"""
    if not ticker:
        print("エラー: 削除する銘柄コードを指定してください。")
        sys.exit(1)

    print(f"銘柄 '{ticker}' を削除しています...")
    try:
        with connector.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM target_tickers WHERE ticker = ?", (ticker,))
            conn.commit()
            if cursor.rowcount == 0:
                print(f"銘柄 '{ticker}' は見つかりませんでした。")
            else:
                print(f"銘柄 '{ticker}' の削除が完了しました。")
    except Exception as e:
        print(f"エラー: 銘柄の削除に失敗しました - {e}")
        sys.exit(1)


def main():
    """コマンドライン引数を解釈して、対応する関数を呼び出す"""
    parser = argparse.ArgumentParser(description="監視対象の銘柄をデータベースで管理します。")
    subparsers = parser.add_subparsers(dest="command", required=True, help="実行するコマンド")

    # 'list' コマンド
    parser_list = subparsers.add_parser("list", help="登録されているすべての監視銘柄を一覧表示します。")

    # 'add' コマンド
    parser_add = subparsers.add_parser("add", help="新しい監視銘柄を追加または更新します。")
    parser_add.add_argument("--ticker", required=True, help="追加する銘柄コード (例: 7203.T)")
    parser_add.add_argument("--features", required=True, help="使用する特徴量のカンマ区切りリスト (例: '^N225,^TPX')")

    # 'remove' コマンド
    parser_remove = subparsers.add_parser("remove", help="監視銘柄を削除します。")
    parser_remove.add_argument("--ticker", required=True, help="削除する銘柄コード")

    args = parser.parse_args()

    # データベース接続を初期化
    db_connector = DBConnector()

    if args.command == "list":
        list_tickers(db_connector)
    elif args.command == "add":
        add_ticker(db_connector, args.ticker, args.features)
    elif args.command == "remove":
        remove_ticker(db_connector, args.ticker)


if __name__ == "__main__":
    main()