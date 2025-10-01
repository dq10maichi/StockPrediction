#!/bin/bash
# このスクリプトはプロジェクトのルートディレクトリで実行することを想定しています。

echo "データベースから学習対象のティッカーリストを取得します..."

# `make list-tickers` を実行し、その出力からヘッダーと不要な行を除外し、
# ティッカーシンボル（最初の列）だけを抽出します。
TICKERS=$(make list-tickers | awk 'NR > 2 {print $1}')

if [ -z "$TICKERS" ]; then
  echo "エラー: 学習対象のティッカーが見つかりませんでした。"
  exit 1
fi

echo "以下のティッカーのモデルを再学習します: $TICKERS"

for TICKER in $TICKERS
do
  echo "--- モデルを学習中: $TICKER ---"
  # タイムアウトを120分に設定
  timeout 7200 make train TICKER=$TICKER
  if [ $? -eq 124 ]; then
    echo "警告: $TICKER の学習がタイムアウトしました（120分）。"
  fi
done

echo "--- 全てのモデルの学習が完了しました ---"