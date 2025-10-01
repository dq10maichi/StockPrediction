import argparse
import pandas as pd
import datetime
import time
import os
import sys

# Add parent dir to path to allow importing other scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from script.db_connector import DBConnector
from script.stock_utils import load_all_data, create_features
from script.train_model import (
    create_classification_target,
    train_and_evaluate_classification,
    PREDICTION_HORIZON,
    RETURN_THRESHOLD
)

# --- Constants ---
COMMON_FEATURES = ['^N225', '^TPX', '^GSPC', 'JPY=X', 'CL=F']
TRAINING_YEARS = 5
TEST_SIZE = 0.2

def get_tickers_from_market_list(db_connector):
    """Gets the list of tickers to evaluate from the market_list table."""
    with db_connector.connect() as conn:
        df = pd.read_sql("SELECT ticker FROM market_list ORDER BY ticker", conn)
    return df['ticker'].tolist()

def get_existing_data_tickers(db_connector):
    """Gets a set of tickers that already have data in the daily_stock_prices table."""
    with db_connector.connect() as conn:
        df = pd.read_sql("SELECT DISTINCT ticker_symbol FROM daily_stock_prices", conn)
    return set(df['ticker_symbol'].tolist())

def get_completed_tickers(db_connector):
    """Gets a set of tickers that have successfully completed evaluation for both directions."""
    with db_connector.connect() as conn:
        try:
            df = pd.read_sql("""
                SELECT ticker FROM performance_log 
                WHERE status = 'success'
                GROUP BY ticker 
                HAVING COUNT(DISTINCT direction) = 2
            """, conn)
            return set(df['ticker'].tolist())
        except Exception:
            return set()

def prepare_data(db_connector, target_tickers):
    """Prepares the necessary data for the evaluation."""
    print("--- Starting Data Preparation ---")
    existing_tickers = get_existing_data_tickers(db_connector)
    
    # Tickers for which we need to fetch daily price data
    # This includes new evaluation targets and the common feature tickers (indexes, etc.)
    new_evaluation_tickers = [t for t in target_tickers if t not in existing_tickers]
    tickers_to_update = list(set(new_evaluation_tickers + COMMON_FEATURES))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    update_stock_script_path = os.path.join(script_dir, "update_stock_data.py")
    update_eco_script_path = os.path.join(script_dir, "update_economic_data.py")

    if tickers_to_update:
        print(f"Updating/fetching price data for {len(tickers_to_update)} tickers...")
        ticker_str = ' '.join(tickers_to_update)
        os.system(f"python {update_stock_script_path} --tickers {ticker_str}")
    else:
        print("No new stock price data to fetch.")

    # Update macroeconomic data from FRED
    print("Updating macroeconomic data...")
    os.system(f"python {update_eco_script_path}")
    
    print("--- Data Preparation Complete ---")
    # Return only the new tickers that are part of the evaluation, for cleanup later
    return new_evaluation_tickers

def cleanup_data(db_connector, new_tickers):
    """Removes temporarily added ticker data."""
    if not new_tickers:
        print("\nNo data to clean up.")
        return
        
    print(f"\n--- Starting Cleanup: Removing data for {len(new_tickers)} tickers ---")
    try:
        with db_connector.connect() as conn:
            with conn.cursor() as cur:
                tickers_tuple = tuple(new_tickers)
                cur.execute("DELETE FROM daily_stock_prices WHERE ticker_symbol IN %s", (tickers_tuple,))
                print(f"Cleanup complete: {cur.rowcount} rows deleted from daily_stock_prices.")
                conn.commit()
    except Exception as e:
        print(f"An error occurred during cleanup: {e}")

def save_performance_log(db_connector, ticker, direction, version, metrics, features, start_date, end_date, status, error_msg=""):
    """Saves the evaluation results to the performance_log table."""
    with db_connector.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO performance_log (
                    ticker, direction, model_version, evaluation_datetime, 
                    accuracy, precision_score, recall_score, f1_score, roc_auc,
                    features, training_period_start, training_period_end, status, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ticker, direction, version,
                    datetime.datetime.now(),
                    metrics.get('accuracy'), metrics.get('precision'), metrics.get('recall'), 
                    metrics.get('f1_score'), metrics.get('roc_auc'),
                    ','.join(features) if features else None,
                    start_date, end_date, status, error_msg
                )
            )
            conn.commit()

def run_evaluation(db_connector, fresh_run=False, test_mode=False, source_file='list.csv'):
    """Runs the entire evaluation pipeline."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prepare_script_path = os.path.join(script_dir, "prepare_evaluation_db.py")
    load_script_path = os.path.join(script_dir, "load_market_list.py")

    print("--- Preparing evaluation tables ---")
    os.system(f"python {prepare_script_path}")
    print(f"--- Loading ticker list from {source_file} ---")
    os.system(f"python {load_script_path} --file {source_file}")

    if fresh_run:
        print("--- FRESH RUN: Clearing performance_log table ---")
        with db_connector.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE performance_log")
                conn.commit()

    all_tickers = get_tickers_from_market_list(db_connector)
    newly_added_tickers = prepare_data(db_connector, all_tickers)
    completed_tickers = get_completed_tickers(db_connector)
    
    target_tickers = [t for t in all_tickers if t not in completed_tickers]
    print(f"\nTotal tickers for evaluation: {len(all_tickers)}. Already completed: {len(completed_tickers)}. Remaining: {len(target_tickers)}.")
    if test_mode:
        print("*** RUNNING IN TEST MODE ***")

    start_time = time.time()
    
    for i, ticker in enumerate(target_tickers):
        print(f"\n--- Evaluating ticker {i+1}/{len(target_tickers)}: {ticker} ---")
        try:
            main_data, external_data, macro_data = load_all_data(db_connector, ticker, COMMON_FEATURES)
            if main_data.empty or len(main_data) < 200:
                print(f"Skipping {ticker} due to insufficient data.")
                save_performance_log(db_connector, ticker, 'N/A', -1, {}, COMMON_FEATURES, None, None, 'skipped', 'Insufficient data')
                continue

            features_df = create_features(main_data, external_data, macro_data)

            for direction in ['up', 'down']:
                print(f"\n==> Training {direction} model for {ticker}...")
                
                targets_df, target_col = create_classification_target(features_df, PREDICTION_HORIZON, RETURN_THRESHOLD, direction)
                final_df = targets_df.dropna()
                
                if final_df.empty:
                    print(f"Skipping {ticker}/{direction} because no data remains after feature creation.")
                    save_performance_log(db_connector, ticker, direction, -1, {}, COMMON_FEATURES, None, None, 'skipped', 'No data after feature creation')
                    continue

                latest_date = final_df.index.max()
                start_date = latest_date - pd.DateOffset(years=TRAINING_YEARS)
                window_df = final_df.loc[start_date:]
                features_columns = features_df.columns.intersection(window_df.columns)
                X = window_df[features_columns]
                y = window_df[target_col]
                
                if len(X) < 100 or y.nunique() < 2:
                    print(f"Skipping {ticker}/{direction} due to insufficient training data or single class label.")
                    save_performance_log(db_connector, ticker, direction, -1, {}, COMMON_FEATURES, start_date.date(), latest_date.date(), 'skipped', 'Insufficient training data or single class')
                    continue

                train_size = int(len(X) * (1 - TEST_SIZE))
                X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
                y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]

                _model, _scaler, _params, metrics, _version = train_and_evaluate_classification(
                    db_connector, X_train, y_train, X_test, y_test, target_col, ticker, direction, 
                    test_mode=test_mode, search_method='optuna', save_model=False
                )
                
                save_performance_log(db_connector, ticker, direction, -1, metrics, COMMON_FEATURES, start_date.date(), latest_date.date(), 'success')
                print(f"Successfully saved performance log for {ticker}/{direction}.")

        except Exception as e:
            print(f"An error occurred while evaluating {ticker}: {e}")
            save_performance_log(db_connector, ticker, 'N/A', -1, {}, COMMON_FEATURES, None, None, 'failed', str(e))

    cleanup_data(db_connector, newly_added_tickers)
    end_time = time.time()
    print(f"\n--- Bulk Evaluation Complete ---")
    print(f"Total execution time: {(end_time - start_time) / 60:.2f} minutes.")

def main():
    parser = argparse.ArgumentParser(description="Run a bulk evaluation of models for a list of tickers.")
    parser.add_argument('--fresh', action='store_true', help='Clear the performance_log and start from scratch.')
    parser.add_argument('--test-mode', action='store_true', help='Run in test mode with simplified hyperparameter search.')
    parser.add_argument('--source-file', type=str, default='list.csv', help='The CSV file containing the list of tickers to evaluate.')
    args = parser.parse_args()

    db_connector = DBConnector()
    run_evaluation(db_connector, args.fresh, args.test_mode, args.source_file)

if __name__ == "__main__":
    main()