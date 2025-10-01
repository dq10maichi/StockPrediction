import sqlite3
from db_connector import get_db_connection

def main():
    print("--- Temporary ticker registration script started ---")

    tickers_to_add = [
        # Feature Tickers
        ('^N225', 'Nikkei 225', 'INDEX', 'Index', 'Market Index', 'Japan', 'JPY'),
        ('^TPX', 'TOPIX', 'INDEX', 'Index', 'Market Index', 'Japan', 'JPY'),
        ('^GSPC', 'S&P 500', 'INDEX', 'Index', 'Market Index', 'USA', 'USD'),
        ('^DJI', 'Dow Jones Industrial Average', 'INDEX', 'Index', 'Market Index', 'USA', 'USD'),
        ('JPY=X', 'USD/JPY Exchange Rate', 'CURRENCY', 'Currency', 'FX Rate', 'N/A', 'JPY'),
        ('^TNX', 'US 10-Year Treasury Yield', 'INDEX', 'Bond', 'Interest Rate', 'USA', 'USD'),
        ('^VIX', 'CBOE Volatility Index', 'INDEX', 'Index', 'Volatility', 'USA', 'USD'),
        ('CL=F', 'Crude Oil WTI Futures', 'COMMODITY', 'Energy', 'Futures', 'N/A', 'USD'),

        # Target Tickers
        ('4502.T', 'Takeda Pharmaceutical', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('6501.T', 'Hitachi', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('6674.T', 'GS Yuasa', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('6723.T', 'Renesas Electronics', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('6758.T', 'Sony', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('6902.T', 'Denso Corp', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('6971.T', 'Kyocera', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('6981.T', 'Murata Manufacturing', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('8035.T', 'Tokyo Electron', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('7203.T', 'Toyota Motor', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('7272.T', 'Yamaha Motor', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('9432.T', 'NTT', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('9433.T', 'KDDI', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('9984.T', 'SoftBank Group', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('8306.T', 'Mitsubishi UFJ', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('8591.T', 'Orix', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('2002.T', 'Nisshin Seifun Group', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('2802.T', 'Ajinomoto', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('4751.T', 'CyberAgent', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('4755.T', 'Rakuten', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('6098.T', 'Recruit Holdings', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('7974.T', 'Nintendo', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('5019.T', 'Idemitsu Kosan', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('8031.T', 'Mitsui & Co.', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('7011.T', 'Mitsubishi Heavy Industries', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('7013.T', 'IHI', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('7012.T', 'Kawasaki Heavy Industries', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('7832.T', 'Bandai Namco', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY'),
        ('9502.T', 'Chubu Electric Power', 'TSE', 'N/A', 'N/A', 'Japan', 'JPY')
    ]

    conn = None
    try:
        conn, _ = get_db_connection()
        if conn is None:
            print("DB connection failed.")
            return

        with conn:
            cursor = conn.cursor()
            insert_query = """
                INSERT OR IGNORE INTO stock_info (ticker_symbol, company_name, exchange, sector, industry, country, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """
            cursor.executemany(insert_query, tickers_to_add)
            conn.commit()
            print(f"DB write successful. {cursor.rowcount} new tickers might have been added.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

    print("--- Temporary ticker registration script finished ---")

if __name__ == "__main__":
    main()