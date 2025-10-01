import os
from db_connector import DBConnector

def main():
    """
    評価用のデータベーステーブルを準備します。
    SQL/create_evaluation_tables.sql ファイルを読み込み、実行します。
    """
    db_connector = DBConnector()
    try:
        with db_connector.connect() as conn:
            with conn.cursor() as cursor:
                sql_file_path = os.path.join(os.path.dirname(__file__), '..', 'SQL', 'create_evaluation_tables.sql')
                
                with open(sql_file_path, 'r') as f:
                    sql_script = f.read()
                
                # SQLスクリプトを個別の文に分割して実行
                for statement in sql_script.split(';'):
                    if statement.strip():
                        cursor.execute(statement)
                
                conn.commit()
        print("Successfully created evaluation tables.")

    except Exception as e:
        print(f"An error occurred while preparing evaluation DB: {e}")

if __name__ == '__main__':
    main()
