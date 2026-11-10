#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# 静的ファイルの収集
python manage.py collectstatic --no-input


python manage.py migrate

python manage.py createsuperuser

# 4. 安全な状態で、テストデータ生成を走らせます
echo "Triggering test data population..."
python manage.py generate_test_data
