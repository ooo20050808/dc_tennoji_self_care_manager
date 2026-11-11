#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# 静的ファイルの収集
python manage.py collectstatic --no-input

# マイグレーションの実行
python manage.py migrate

echo "Checking for newly created guest users in the database..."

# ホワイトリスト以外のユーザーが1件以上存在するかをPythonで判定（1なら存在、0なら不在）
GUEST_EXISTS=$(python manage.py shell -c "
from selfCare.models import User
whitelist = ['admin@example.com', 'a@example.com', 's@example.com', 'd@example.com']
exists = User.objects.exclude(email__in=whitelist).filter(is_superuser=False).exists()
print(1 if exists else 0)
" | tail -n 1)

if [ "$GUEST_EXISTS" = "1" ]; then
    echo "🚨 New guest user creation detected! Triggering database cleanup..."
    python manage.py clean_guest_users || true
else
    echo "✅ No new guest users detected. Skipping cleanup."
fi

# スーパーユーザー自動作成（--noinput と環境変数を使用）
python manage.py createsuperuser --noinput --email "$DJANGO_SUPERUSER_EMAIL" --user_name "管理者" || true

# テストデータ生成
echo "Triggering test data population..."
python manage.py generate_test_data