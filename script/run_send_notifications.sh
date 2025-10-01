#!/bin/bash

# プロジェクトのルートディレクトリに移動します。
# cronから実行する場合、カレントディレクトリが異なる可能性があるため、絶対パスで指定します。
cd /home/hoge/work/stockpred

# .env ファイルが存在すれば読み込みます。
# これにより、環境変数が設定されます。
if [ -f .env ]; then
    source .env
fi

# make send-notifications コマンドを実行します。
# makeコマンドの絶対パスを指定することをお勧めします（例: /usr/bin/make）。
/usr/bin/make send-notifications
