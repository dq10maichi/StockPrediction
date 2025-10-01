
import sys
import os

# 'script'ディレクトリの絶対パスを取得してsys.pathに追加
# これにより、`db_connector`モジュールを正しくインポートできる
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from db_connector import DBConnector

def column_exists(cursor, table_name, column_name):
    """指定されたテーブルにカラムが存在するかどうかを確認する"""
    cursor.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        AND column_name = %s
    """, (table_name, column_name))
    return cursor.fetchone() is not None

def apply_migration():
    """
    データベーススキーマのマイグレーションを実行する。
    - trained_modelsテーブルにnotification_sentカラムを追加
    - prediction_resultsテーブルにnotification_sentカラムを追加
    カラムが既に存在する場合は、何も行わない。
    """
    db_connector = DBConnector()
    
    # ALTER TABLEクエリのリスト
    migrations = [
        {
            "table": "trained_models",
            "column": "notification_sent",
            "query": "ALTER TABLE trained_models ADD COLUMN notification_sent BOOLEAN DEFAULT false;"
        },
        {
            "table": "prediction_results",
            "column": "notification_sent",
            "query": "ALTER TABLE prediction_results ADD COLUMN notification_sent BOOLEAN DEFAULT false;"
        }
    ]

    print("--- データベースマイグレーションを開始します ---")
    try:
        with db_connector.connect() as conn:
            with conn.cursor() as cursor:
                for migration in migrations:
                    table = migration["table"]
                    column = migration["column"]
                    query = migration["query"]
                    
                    print(f"テーブル '{table}' のカラム '{column}' の存在を確認中...")
                    if not column_exists(cursor, table, column):
                        print(f"-> カラムが存在しません。'{table}' に '{column}' カラムを追加します。")
                        cursor.execute(query)
                        print(f"   '{query}' を実行しました。")
                    else:
                        print(f"-> カラムは既に存在します。スキップします。")
            
            # 変更をコミット
            conn.commit()
            print("\nマイグレーションが正常に完了しました。")

    except Exception as e:
        print(f"\nマイグレーション中にエラーが発生しました: {e}")
        # エラーが発生した場合はロールバック
        if 'conn' in locals() and conn:
            conn.rollback()
        print("変更はロールバックされました。")

if __name__ == "__main__":
    apply_migration()
