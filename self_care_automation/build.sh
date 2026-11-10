#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# 静的ファイルの収集
python manage.py collectstatic --no-input

# 1. 【最重要】マイグレーションの邪魔をする過去の重複ゴミデータを完全にクレンジング
echo "Forcing database cleansing before migrations..."
if [ -n "$DATABASE_URL" ]; then
    # input_screen 内の重複データを一掃
    psql "$DATABASE_URL" -c "DELETE FROM input_screen WHERE id NOT IN (SELECT MIN(id) FROM input_screen GROUP BY home_screen_id);" || echo "Cleansing home_screen_id skipped."
    psql "$DATABASE_URL" -c "DELETE FROM input_screen WHERE id NOT IN (SELECT MIN(id) FROM input_screen GROUP BY date_id);" || echo "Cleansing date_id skipped."
else
    echo "DATABASE_URL is not set, skipping physical database cleansing."
fi

# 2. データベースのマイグレーションを実行
echo "Running database migrations..."
python manage.py migrate

# 3. データベース内に残っている古い残骸カラム「date_id」のNOT NULL制約を解除する
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

# 4. 安全な状態で、テストデータ生成を走らせます
echo "Triggering test data population..."
python manage.py generate_test_data
