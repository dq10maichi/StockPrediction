from db_connector import get_db_connection
import json
import sqlite3

conn = None
try:
    conn, _ = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT model_id, ticker_symbol, model_name, model_version, performance_metrics, feature_list FROM trained_models;")
            rows = cur.fetchall()
            if rows:
                print("Models found in trained_models table:")
                for row in rows:
                    model_id, ticker_symbol, model_name, model_version, perf_metrics_json, feature_list_json = row
                    perf_metrics = json.loads(perf_metrics_json) if perf_metrics_json else None
                    feature_list = json.loads(feature_list_json) if feature_list_json else None
                    print(f"  ID: {model_id}, Ticker: {ticker_symbol}, Name: {model_name}, Version: {model_version}")
                    print(f"    Performance: {json.dumps(perf_metrics)}")
                    print(f"    Features: {json.dumps(feature_list)}")
            else:
                print("No models found in trained_models table.")
    else:
        print("Failed to connect to the database.")
except Exception as e:
    print(f"Error querying database: {e}")
finally:
    if conn:
        conn.close()