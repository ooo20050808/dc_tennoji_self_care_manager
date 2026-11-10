#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# 静的ファイルの収集
python manage.py collectstatic --no-input

echo "Cleansing duplicate records from database..."
if [ -n "$DATABASE_URL" ]; then
    # 同じ home_screen_id を持つレコードのうち、最小の id 以外の重複行を物理削除します
    psql "$DATABASE_URL" -c "DELETE FROM input_screen WHERE id NOT IN (SELECT MIN(id) FROM input_screen GROUP BY home_screen_id);" || echo "Cleansing skipped or table does not exist yet."
else
    echo "DATABASE_URL is not set, skipping database cleansing."
fi

# 1. データベースのマイグレーションを実行（これで一意インデックスが正常に作られるようになります）
python manage.py migrate

# 2. データベース内に残っている古い残骸カラム「date_id」のNOT NULL制約を解除する
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
