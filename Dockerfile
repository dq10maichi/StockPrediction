# Python 3.12 のスリムバージョンをベースイメージとして使用
FROM python:3.12-slim

# lightgbmが必要とするシステムライブラリをインストール
RUN apt-get update && apt-get install -y libgomp1
RUN pip install setuptools

# コンテナ内の作業ディレクトリを設定
WORKDIR /app

# 最初に requirements.txt をコピーして、依存関係をインストール
# このステップはキャッシュされるため、コードの変更のたびに再インストールが走るのを防ぐ
COPY requirements.txt .
RUN pip install numpy==1.26.4
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
COPY . .

# ビルドスクリプトに実行権限を付与
RUN chmod +x /app/script/build_script.sh

# コンテナ起動時に実行されるコマンド
CMD ["/app/script/build_script.sh"]