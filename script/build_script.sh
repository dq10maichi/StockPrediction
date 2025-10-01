#!/bin/bash

# アプリケーションの実行ログを保存するディレクトリ
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

# ログファイル名
LOG_FILE="$LOG_DIR/build_log_$(date +%Y%m%d_%H%M%S).log"

# エラー時にスクリプトを終了
set -e
set -o pipefail

# --- 引数解析 ---
MODE=""
TICKER=""
INDICATOR_ARGS=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --ticker)
      TICKER="$2"
      shift 2
      ;;
    --indicators)
      shift
      while (( "$#" )); do
        INDICATOR_ARGS+="$1 "
        shift
      done
      ;;
    *)
      echo "不明なオプションです: $1" | tee -a "$LOG_FILE"
      exit 1
      ;;
  esac
done

# --- 実行ログ ---
echo "--- 株価トレンド予測アプリケーションの構築と実行を開始します ---" | tee -a "$LOG_FILE"
echo "ログファイル: $LOG_FILE" | tee -a "$LOG_FILE"
echo "実行モード: ${MODE:-all}" | tee -a "$LOG_FILE"

# --- タスクの実行 ---

# データ更新タスク
run_update() {
    echo "--- データ更新タスクを開始します ---" | tee -a "$LOG_FILE"
    
    echo "データベースの初期化を開始..." | tee -a "$LOG_FILE"
    python script/initialize_db.py | tee -a "$LOG_FILE"
    
    echo "株価データの取得・更新を開始..." | tee -a "$LOG_FILE"
    python script/update_stock_data.py | tee -a "$LOG_FILE"
    
    echo "経済指標データの取得・更新を開始..." | tee -a "$LOG_FILE"
    if [ -n "$INDICATOR_ARGS" ]; then
        echo "指定された経済指標: $INDICATOR_ARGS" | tee -a "$LOG_FILE"
        python script/update_economic_data.py --indicators $INDICATOR_ARGS | tee -a "$LOG_FILE"
    else
        echo "経済指標はデフォルト値を使用します。" | tee -a "$LOG_FILE"
        python script/update_economic_data.py | tee -a "$LOG_FILE"
    fi
    
    echo "--- データ更新タスクが完了しました ---" | tee -a "$LOG_FILE"
}

# モデル学習タスク
run_train() {
    echo "--- モデル学習タスクを開始します ---" | tee -a "$LOG_FILE"
    
    if [ -z "$TICKER" ]; then
        echo "エラー: --mode train を使用するには --ticker 引数が必要です。" | tee -a "$LOG_FILE"
        exit 1
    fi
    echo "対象銘柄: $TICKER" | tee -a "$LOG_FILE"
    
    echo "株価トレンド予測モデルの学習と評価を開始..." | tee -a "$LOG_FILE"
    python script/train_model.py --ticker $TICKER | tee -a "$LOG_FILE"
    
    echo "--- モデル学習タスクが完了しました ---" | tee -a "$LOG_FILE"
}

# モードに応じて処理を分岐
case $MODE in
    update)
        run_update
        ;;
    train)
        run_train
        ;;
    ""|all)
        run_update
        run_train
        ;;
    *)
        echo "エラー: 無効なモードです: $MODE" | tee -a "$LOG_FILE"
        echo "利用可能なモード: update, train, all" | tee -a "$LOG_FILE"
        exit 1
        ;;
esac

echo "--- アプリケーションの実行が完了しました ---" | tee -a "$LOG_FILE"
echo "--- 詳細は $LOG_FILE を参照してください ---" | tee -a "$LOG_FILE"
