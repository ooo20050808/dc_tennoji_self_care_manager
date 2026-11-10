#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# 静的ファイルの収集
python manage.py collectstatic --no-input

# マイグレーションの実行
python manage.py migrate

# スーパーユーザー自動作成（--noinput と環境変数を使用）
python manage.py createsuperuser

# テストデータ生成
echo "Triggering test data population..."
python manage.py generate_test_data