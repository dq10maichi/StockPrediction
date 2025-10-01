import os
from db_connector import get_db_connection
import sqlite3

# SQLファイルへのパス
SQL_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'SQL', 'createtable.sql')

def initialize_database():
    """
    SQLファイルからDDLを読み込み、データベースのテーブルを初期化する
    """
    print("--- データベースの初期化を開始します ---")
    conn = None
    try:
        conn, _ = get_db_connection()
        if conn is None:
            print("データベース接続の取得に失敗したため、初期化を中止します。")
            return

        cursor = conn.cursor()

        print(f"SQLファイル '{SQL_FILE_PATH}' を読み込んで実行します...")
        with open(SQL_FILE_PATH, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            cursor.executescript(sql_script)

        conn.commit()
        cursor.close()
        print("--- データベースの初期化が正常に完了しました ---")

    except FileNotFoundError:
        print(f"エラー: SQLファイルが見つかりません: {SQL_FILE_PATH}")
    except Exception as e:
        print(f"データベース初期化中にエラーが発生しました: {e}")
    finally:
        if conn:
            conn.close()
            print("データベース接続を閉じました。")

if __name__ == "__main__":
    initialize_database()