import pandas as pd
import numpy as np
import pandas_ta as ta
from db_connector import DBConnector
from config_loader import config_loader
import sqlite3

# --- 設定 ---
# 特徴量生成のための設定をコンフィグファイルから読み込む
FEATURE_LAG_DAYS, MA_PERIODS = config_loader.get_feature_settings()

# 出力ディレクトリ
MODELS_DIR = 'models'
PREDICTION_OUTPUT_DIR = 'predictions'
PLOTS_OUTPUT_DIR = 'plots'


def load_all_data(db_connector, target_ticker, external_tickers):
    """
    予測対象銘柄、外部指標、マクロ経済指標をDBから読み込む
    """
    try:
        with db_connector.connect() as conn:
            # 1. 予測対象と外部指標の株価データを取得
            all_tickers = [target_ticker] + external_tickers
            # SQLiteのIN句用にプレースホルダを生成
            placeholders = ', '.join(['?' for _ in all_tickers])
            query_prices = f"""
            SELECT ticker_symbol, trade_date, open_price, high_price, low_price, adj_close_price, volume
            FROM daily_stock_prices
            WHERE ticker_symbol IN ({placeholders})
            ORDER BY trade_date;
            """
            df_prices = pd.read_sql(query_prices, conn, params=all_tickers, parse_dates=['trade_date'])
            
            # データをティッカーごとに分割
            main_df = df_prices[df_prices['ticker_symbol'] == target_ticker].set_index('trade_date').drop('ticker_symbol', axis=1)
            external_dfs = {
                ticker: df_prices[df_prices['ticker_symbol'] == ticker].set_index('trade_date').drop('ticker_symbol', axis=1)
                for ticker in external_tickers
            }

            # 2. マクロ経済指標を取得
            query_macro = "SELECT series_id, indicator_date, value FROM macro_economic_indicators ORDER BY indicator_date;"
            df_macro = pd.read_sql(query_macro, conn, parse_dates=['indicator_date'])
            
            # マクロ経済指標をピボットし、日付をインデックスにする
            df_macro_pivot = df_macro.pivot(index='indicator_date', columns='series_id', values='value')
            df_macro_pivot.index.name = 'trade_date'

            print("データの読み込みが完了しました。")
            return main_df, external_dfs, df_macro_pivot

    except Exception as e:
        print(f"データ読み込み中にエラーが発生しました: {e}")
        return pd.DataFrame(), {}, pd.DataFrame()

def create_features(main_df, external_dfs, macro_df):
    """
    すべての入力データから特徴量を作成する（データ駆動型）
    """
    df_copy = main_df.copy()

    # 株式分割や配当を考慮し、すべての価格データを調整後終値のスケールに統一する
    # これにより、分割をまたいだ不整合がなくなり、特徴量計算が安定する
    if 'adj_close_price' in df_copy and 'close_price' in df_copy and (df_copy['close_price'] != 0).all():
        adjustment_ratio = df_copy['adj_close_price'] / df_copy['close_price']
        df_copy['open'] = df_copy['open_price'] * adjustment_ratio
        df_copy['high'] = df_copy['high_price'] * adjustment_ratio
        df_copy['low'] = df_copy['low_price'] * adjustment_ratio
        df_copy['close'] = df_copy['adj_close_price']
        # Volumeは調整しない。調整する場合はより複雑なロジックが必要。
        df_copy['volume'] = df_copy['volume']
    else:
        # 古いデータや互換性のために、リネーム処理も残す
        df_copy.rename(columns={
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'adj_close_price': 'close',
            'volume': 'volume'
        }, inplace=True)

    # 1. 外部市場指標を結合と特徴量生成
    columns_to_drop = []
    for ticker, df_ext in external_dfs.items():
        safe_ticker_name = ticker.replace('^', '')
        # 外部指標のDFもカラム名をpandas-taが認識できる名前に変更
        df_ext.rename(columns={
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'adj_close_price': 'close',
            'volume': 'volume'
        }, inplace=True)
        df_ext_renamed = df_ext.add_prefix(f'{safe_ticker_name}_')
        df_copy = pd.merge(df_copy, df_ext_renamed, left_index=True, right_index=True, how='left')
        
        # 特徴量生成ロジック
                # 特徴量生成ロジック
        close_col = f'{safe_ticker_name}_close'
        
        # VIXは価格そのものを特徴量とする
        if ticker == '^' + 'VIX':
            df_copy['vix_price'] = df_copy[close_col]
        # それ以外の外部指標はリターンを特徴量とする
        else:
            for days in FEATURE_LAG_DAYS:
                feature_name = f'{safe_ticker_name.lower()}_return_{days}d'
                df_copy[feature_name] = df_copy[close_col].pct_change(periods=days)
        
        # 結合に使用した元のカラムを削除リストに追加
        columns_to_drop.extend(df_ext_renamed.columns.tolist())

    # 2. マクロ経済指標を結合
    df_copy = pd.merge(df_copy, macro_df, left_index=True, right_index=True, how='left')
    
    # 結合による欠損値を前方補完
    df_copy.ffill(inplace=True)

    # 3. 予測対象自身のデータから特徴量を作成
    for days in FEATURE_LAG_DAYS:
        df_copy[f'return_{days}d'] = df_copy['close'].pct_change(periods=days)
    for period in MA_PERIODS:
        df_copy[f'SMA_{period}'] = df_copy['close'].rolling(window=period).mean()
        df_copy[f'SMA_diff_ratio_{period}'] = (df_copy['close'] - df_copy[f'SMA_{period}']) / df_copy[f'SMA_{period}']
    
    df_copy['volume_change'] = df_copy['volume'].pct_change()
    df_copy['day_of_week'] = df_copy.index.dayofweek
    df_copy['month'] = df_copy.index.month
    df_copy['year'] = df_copy.index.year
    
    # 4. テクニカル指標を追加 (pandas-ta)
    print("テクニカル指標を追加中...")
    df_copy.ta.rsi(length=14, append=True)
    df_copy.ta.macd(fast=12, slow=26, signal=9, append=True)
    df_copy.ta.bbands(length=20, std=2, append=True)
    df_copy.ta.atr(length=14, append=True) # ATR (Average True Range) を追加

    # 5. 不要な元データを削除
    df_copy.drop(columns=columns_to_drop, inplace=True, errors='ignore')
    
    # 元のadj_close_priceを復元
    df_copy.rename(columns={'close': 'adj_close_price'}, inplace=True)

    # 無限大の値をNaNに置換し、欠損行を削除
    df_copy.replace([np.inf, -np.inf], np.nan, inplace=True)
    df_copy.dropna(inplace=True)
    
    print("特徴量の生成が完了しました。")
    return df_copy