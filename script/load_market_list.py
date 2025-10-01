import pandas as pd
from db_connector import DBConnector
import os
from datetime import date
import argparse

def load_market_list(file_path):
    """
    指定されたCSVファイルから国内株式の銘柄を抽出し、market_listテーブルにロードします。
    """
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    target_markets = ['プライム（内国株式）', 'スタンダード（内国株式）', 'グロース（内国株式）']
    df_stocks = df[df['市場・商品区分'].isin(target_markets)].copy()
    df_stocks['ticker'] = df_stocks['コード'].astype(str) + '.T'
    
    db_connector = DBConnector()
    try:
        with db_connector.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE market_list")
                print("Truncated market_list table.")

                today = date.today()
                for _, row in df_stocks.iterrows():
                    cursor.execute(
                        """
                        INSERT INTO market_list (
                            ticker, name, market_segment, industry_code_33, industry_name_33,
                            industry_code_17, industry_name_17, scale_code, scale_segment, load_date
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ticker) DO NOTHING;
                        """,
                        (
                            row['ticker'], row['銘柄名'], row['市場・商品区分'],
                            str(row['33業種コード']), row['33業種区分'], str(row['17業種コード']),
                            row['17業種区分'], str(row['規模コード']), row['規模区分'], today
                        )
                    )
                conn.commit()
        print(f"Successfully loaded {len(df_stocks)} stocks into market_list from {os.path.basename(file_path)}.")

    except Exception as e:
        print(f"An error occurred during market list loading: {e}")

def main():
    parser = argparse.ArgumentParser(description="CSVファイルから銘柄リストをDBにロードします。")
    parser.add_argument('--file', type=str, default='list.csv', help='銘柄リストのCSVファイルパス')
    args = parser.parse_args()
    
    # Inside docker, the script runs from /app. The file path should be relative to that.
    file_full_path = os.path.join(os.path.dirname(__file__), '..', args.file)
    load_market_list(file_full_path)

if __name__ == '__main__':
    main()
