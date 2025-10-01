import sys
import os
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 'script'ディレクトリの絶対パスを取得してsys.pathに追加
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from db_connector import DBConnector

# --- 定数 ---
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive' # Added back drive scope
]
SERVICE_ACCOUNT_FILE = os.path.join('/app', 'secrets', 'service_account.json')

def get_google_api_creds():
    """サービスアカウントの認証情報を取得する"""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"サービスアカウントキーが見つかりません: {SERVICE_ACCOUNT_FILE}")
    return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

def get_gspread_client(creds):
    """gspreadクライアントを返す"""
    print("--- Google Sheets APIに認証中...")
    client = gspread.authorize(creds)
    print("認証成功。")
    return client

def write_to_spreadsheet(client, df, sheet_name, worksheet_name):
    """DataFrameをスプレッドシートに書き込む"""
    if df.empty:
        return
    print(f"--- スプレッドシート '{sheet_name}' の '{worksheet_name}' シートに書き込み中...")
    try:
        spreadsheet = client.open(sheet_name)
        worksheet = spreadsheet.worksheet(worksheet_name)
        if not worksheet.get_all_values():
            header = df.columns.tolist()
            worksheet.append_row(header)
            print("ヘッダーを書き込みました。")
        df_list = df.fillna('').values.tolist()
        worksheet.append_rows(df_list)
        print(f"{len(df_list)}行を '{worksheet_name}' シートに正常に追記しました。")
    except gspread.exceptions.SpreadsheetNotFound:
        raise Exception(f"スプレッドシート '{sheet_name}' が見つかりません。")
    except gspread.exceptions.WorksheetNotFound:
        raise Exception(f"ワークシート '{worksheet_name}' が見つかりません。")
    except gspread.exceptions.APIError as e:
        print(f"Google Sheets APIエラーが発生しました: {e}", file=sys.stderr)
        raise

def fetch_pending_notifications(conn):
    """未通知のレコードを取得する"""
    print("--- 未通知のレコードを取得中...")
    pending_models_df = pd.read_sql("""SELECT tm.*, si.company_name FROM trained_models tm JOIN stock_info si ON tm.ticker_symbol = si.ticker_symbol WHERE tm.notification_sent = false""", conn)
    pending_predictions_df = pd.read_sql("""SELECT pr.*, si.company_name FROM prediction_results pr JOIN stock_info si ON pr.ticker = si.ticker_symbol WHERE pr.notification_sent = false""", conn)
    print(f"未通知のモデル: {len(pending_models_df)}件")
    print(f"未通知の予測結果: {len(pending_predictions_df)}件")
    return pending_models_df, pending_predictions_df

def send_email_notification(models_df, predictions_df):
    """Eメールで通知し、成功したかどうかを返す"""
    print("--- メール通知の準備中...")
    smtp_vars = {v: os.getenv(v) for v in ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_SENDER', 'SMTP_RECIPIENT']}
    if not all(smtp_vars.values()):
        print("警告: SMTP関連の環境変数が不足しているため、メール通知をスキップします。")
        return False

    subject = "【通知】新しいモデルと予測結果"
    models_html_df = models_df.copy()
    if 'performance_metrics' in models_html_df.columns:
        models_html_df['performance_metrics'] = models_html_df['performance_metrics'].apply(json.dumps)

    body_html = "<html><body><h2>新しいモデル</h2>" + (models_html_df.to_html(index=False) if not models_html_df.empty else "<p>なし</p>")
    body_html += "<h2>新しい予測</h2>" + (predictions_df.to_html(index=False) if not predictions_df.empty else "<p>なし</p>") + "</body></html>"

    msg = MIMEMultipart()
    msg['From'] = smtp_vars['SMTP_SENDER']
    msg['To'] = smtp_vars['SMTP_RECIPIENT']
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html'))

    try:
        print(f"--- {smtp_vars['SMTP_RECIPIENT']} 宛にメールを送信中...")
        with smtplib.SMTP(smtp_vars['SMTP_HOST'], int(smtp_vars['SMTP_PORT'])) as server:
            server.starttls()
            server.login(smtp_vars['SMTP_USER'], smtp_vars['SMTP_PASSWORD'])
            server.send_message(msg)
        print("メールを正常に送信しました。")
        return True
    except Exception as e:
        print(f"メール送信中にエラーが発生しました: {e}", file=sys.stderr)
        return False

def update_notification_flags(conn, model_ids, prediction_ids):
    """通知フラグを更新する"""
    if not model_ids and not prediction_ids:
        return
    print("--- データベースの通知フラグを更新中...")
    try:
        with conn.cursor() as cursor:
            if model_ids:
                cursor.execute("UPDATE trained_models SET notification_sent = true WHERE model_id IN %s", (tuple(model_ids),))
                print(f"{cursor.rowcount}件のモデルのフラグを更新しました。")
            if prediction_ids:
                cursor.execute("UPDATE prediction_results SET notification_sent = true WHERE id IN %s", (tuple(prediction_ids),))
                print(f"{cursor.rowcount}件の予測結果のフラグを更新しました。")
        conn.commit()
        print("フラグの更新が完了しました。")
    except Exception as e:
        conn.rollback()
        print(f"フラグ更新中にエラーが発生しました: {e}", file=sys.stderr)
        raise

def main():
    """メイン関数"""
    print("--- 通知送信プロセスを開始します ---")
    spreadsheet_name = os.getenv('GSPREAD_SHEET_NAME')
    if not spreadsheet_name:
        print("エラー: GSPREAD_SHEET_NAMEが設定されていません。", file=sys.stderr)
        sys.exit(1)

    db_connector = DBConnector()
    try:
        with db_connector.connect() as conn:
            pending_models, pending_predictions = fetch_pending_notifications(conn)
            
            if pending_models.empty and pending_predictions.empty:
                print("通知対象のレコードはありません。")
                return

            creds = get_google_api_creds()
            gspread_client = get_gspread_client(creds)

            # --- Googleスプレッドシートへの書き込み ---
            if not pending_models.empty:
                models_to_write = pending_models.copy()
                metrics_df = models_to_write['performance_metrics'].apply(lambda x: pd.Series(json.loads(x) if isinstance(x, str) else x))
                models_to_write = pd.concat([models_to_write.drop(columns=['performance_metrics']), metrics_df], axis=1)
                models_to_write['creation_timestamp'] = pd.to_datetime(models_to_write['creation_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                models_to_write['direction'] = models_to_write['model_name'].apply(lambda x: 'up' if 'up' in x else 'down')
                models_to_write['hyperparameters'] = models_to_write['hyperparameters'].apply(json.dumps)
                
                model_sheet_columns = ['creation_timestamp', 'ticker_symbol', 'company_name', 'model_name', 'model_version', 'direction', 'roc_auc', 'precision', 'recall', 'f1_score', 'accuracy', 'hyperparameters']
                write_to_spreadsheet(gspread_client, models_to_write[model_sheet_columns], spreadsheet_name, "Models")

            if not pending_predictions.empty:
                predictions_to_write = pending_predictions.copy()
                predictions_to_write['prediction_timestamp'] = pd.to_datetime(predictions_to_write['prediction_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                predictions_to_write['target_date'] = pd.to_datetime(predictions_to_write['target_date']).dt.strftime('%Y-%m-%d')
                predictions_to_write = predictions_to_write.rename(columns={'ticker': 'ticker_symbol','target_date': 'prediction_date','probability': 'prediction_probability','model_version': 'model_version_used'})
                prediction_sheet_columns = ['prediction_timestamp', 'ticker_symbol', 'company_name', 'prediction_date', 'direction', 'prediction_probability', 'model_version_used']
                predictions_to_write = predictions_to_write[prediction_sheet_columns]
                write_to_spreadsheet(gspread_client, predictions_to_write, spreadsheet_name, "Predictions")

            # --- メール通知 ---
            email_sent_successfully = send_email_notification(pending_models, pending_predictions)

            # --- フラグ更新 ---
            if email_sent_successfully:
                model_ids = pending_models['model_id'].tolist()
                prediction_ids = pending_predictions['id'].tolist()
                update_notification_flags(conn, model_ids, prediction_ids)
            else:
                print("メール送信に失敗したため、通知フラグの更新をスキップしました。")

    except Exception as e:
        print(f"\nプロセス中に予期せぬエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)


def update_notification_flags(conn, model_ids, prediction_ids):
    """通知フラグを更新する"""
    if not model_ids and not prediction_ids:
        return
    print("--- データベースの通知フラグを更新中...")
    try:
        with conn.cursor() as cursor:
            if model_ids:
                cursor.execute("UPDATE trained_models SET notification_sent = true WHERE model_id IN %s", (tuple(model_ids),))
                print(f"{cursor.rowcount}件のモデルのフラグを更新しました。")
            if prediction_ids:
                cursor.execute("UPDATE prediction_results SET notification_sent = true WHERE id IN %s", (tuple(prediction_ids),))
                print(f"{cursor.rowcount}件の予測結果のフラグを更新しました。")
        conn.commit()
        print("フラグの更新が完了しました。")
    except Exception as e:
        conn.rollback()
        print(f"フラグ更新中にエラーが発生しました: {e}", file=sys.stderr)
        raise

def main():
    """メイン関数"""
    print("--- 通知送信プロセスを開始します ---")
    spreadsheet_name = os.getenv('GSPREAD_SHEET_NAME')
    if not spreadsheet_name:
        print("エラー: GSPREAD_SHEET_NAMEが設定されていません。", file=sys.stderr)
        sys.exit(1)

    db_connector = DBConnector()
    try:
        with db_connector.connect() as conn:
            pending_models, pending_predictions = fetch_pending_notifications(conn)
            
            if pending_models.empty and pending_predictions.empty:
                print("通知対象のレコードはありません。")
                return

            creds = get_google_api_creds()
            gspread_client = get_gspread_client(creds)

            # --- Googleスプレッドシートへの書き込み ---
            if not pending_models.empty:
                models_to_write = pending_models.copy()
                metrics_df = models_to_write['performance_metrics'].apply(lambda x: pd.Series(json.loads(x) if isinstance(x, str) else x))
                models_to_write = pd.concat([models_to_write.drop(columns=['performance_metrics']), metrics_df], axis=1)
                models_to_write['creation_timestamp'] = pd.to_datetime(models_to_write['creation_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                models_to_write['direction'] = models_to_write['model_name'].apply(lambda x: 'up' if 'up' in x else 'down')
                models_to_write['hyperparameters'] = models_to_write['hyperparameters'].apply(json.dumps)
                
                model_sheet_columns = ['creation_timestamp', 'ticker_symbol', 'company_name', 'model_name', 'model_version', 'direction', 'roc_auc', 'precision', 'recall', 'f1_score', 'accuracy', 'hyperparameters']
                write_to_spreadsheet(gspread_client, models_to_write[model_sheet_columns], spreadsheet_name, "Models")

            if not pending_predictions.empty:
                predictions_to_write = pending_predictions.copy()
                predictions_to_write['prediction_timestamp'] = pd.to_datetime(predictions_to_write['prediction_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                predictions_to_write['target_date'] = pd.to_datetime(predictions_to_write['target_date']).dt.strftime('%Y-%m-%d')
                predictions_to_write = predictions_to_write.rename(columns={'ticker': 'ticker_symbol','target_date': 'prediction_date','probability': 'prediction_probability','model_version': 'model_version_used'})
                prediction_sheet_columns = ['prediction_timestamp', 'ticker_symbol', 'company_name', 'prediction_date', 'direction', 'prediction_probability', 'model_version_used']
                predictions_to_write = predictions_to_write[prediction_sheet_columns]
                write_to_spreadsheet(gspread_client, predictions_to_write, spreadsheet_name, "Predictions")

            # --- メール通知 ---
            send_email_notification(pending_models, pending_predictions)

            # --- フラグ更新 ---
            model_ids = pending_models['model_id'].tolist()
            prediction_ids = pending_predictions['id'].tolist()
            update_notification_flags(conn, model_ids, prediction_ids)

    except Exception as e:
        print(f"\nプロセス中に予期せぬエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()