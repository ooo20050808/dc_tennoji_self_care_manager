#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# 静的ファイルの収集
python manage.py collectstatic --no-input

# 1. データベースのマイグレーションを実行
python manage.py migrate

echo "Executing legacy column adjustment..."
if [ -n "$DATABASE_URL" ]; then
    psql "$DATABASE_URL" -c "ALTER TABLE input_screen ALTER COLUMN date_id DROP NOT NULL;" || echo "Column date_id might not exist, skipping."
else
    echo "DATABASE_URL is not set, skipping column adjustment."
fi

echo "Executing forced physical index drop before data seeding..."
if [ -n "$DATABASE_URL" ]; then
    psql "$DATABASE_URL" -c "DROP INDEX IF EXISTS input_screen_home_screen_id_key;"
else
    echo "DATABASE_URL is not set, skipping physical drop index."
fi

# 3. 障害物が完全に取り除かれた安全な状態で、テストデータ生成を走らせます。
echo "Triggering test data population..."
python manage.py generate_test_data
