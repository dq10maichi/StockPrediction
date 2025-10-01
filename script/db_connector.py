import sqlite3
from contextlib import contextmanager
import os

class DBConnector:
    """
    SQLiteデータベースへの接続を管理するクラス。
    `with`ステートメントと組み合わせて使用することで、接続のクリーンアップを自動化する。

    使用例:
    db_connector = DBConnector()
    with db_connector.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
    """
    def __init__(self, db_name="stock_trader.db"):
        # プロジェクトルートにデータベースファイルを配置
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_name)

    @contextmanager
    def connect(self):
        """
        データベース接続を提供するコンテキストマネージャ。
        """
        conn = None
        try:
            # SQLiteデータベースに接続
            conn = sqlite3.connect(self.db_path)
            print(f"--- SQLiteデータベース '{self.db_path}' への接続が成功しました ---")
            yield conn
        except sqlite3.Error as e:
            print(f"接続エラー: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
                print("--- データベース接続を閉じました ---")

# 下位互換性のための古い関数 (新しいコードではDBConnectorの使用を推奨)
def get_db_connection():
    """
    下位互換性のために残された関数。
    DBConnectorクラスのインスタンスを作成し、手動で接続を開始する。
    呼び出し側がconn.close()を管理する必要がある。
    """
    connector = DBConnector()
    try:
        conn = sqlite3.connect(connector.db_path)
        print(f"--- SQLiteデータベース '{connector.db_path}' への接続が成功しました ---")
        return conn, None  # tunnelオブジェクトはNoneを返す
    except sqlite3.Error as e:
        print(f"接続エラー: {e}")
        return None, None

if __name__ == '__main__':
    # DBConnectorクラスのテスト
    print("--- DBConnector クラスのテスト ---")
    db_connector = DBConnector()
    try:
        with db_connector.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sqlite_version();")
            db_version = cursor.fetchone()
            print(f"接続成功！ SQLiteバージョン: {db_version[0]}")
    except Exception as e:
        print(f"テスト中にエラーが発生しました: {e}")