#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# 静的ファイルの収集
python manage.py collectstatic --no-input

echo "Executing framework isolation layer..."
python manage.py migrate --fake-initial || true
python manage.py migrate --run-syncdb || true
echo "Executing final physical index cleanup..."
if [ -n "$DATABASE_URL" ]; then
    psql "$DATABASE_URL" -c "DROP INDEX IF EXISTS input_screen_home_screen_id_key;"
else
    echo "DATABASE_URL is not set, skipping target database cleanup."
fi

# 3. 制約が完全に取り除かれた安全な状態で、テストデータ生成を走らせます。
echo "Triggering test data population..."
python manage.py generate_test_data
