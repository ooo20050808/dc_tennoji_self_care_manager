#!/usr/bin/env bash
set -o errexit

# 1. 依存パッケージのインストール
pip install -r requirements.txt

echo "=== 現在のディレクトリ構造 ==="
ls -la

echo "=== templates フォルダの存在確認 ==="
ls -R templates || echo "templates フォルダが見つかりません"

# 2. テンプレートの同期処理
echo "=== テンプレートの同期処理 ==="
mkdir -p self_care_automation/templates
if [ -d "templates" ]; then
    cp -r templates/* self_care_automation/templates/
    echo "templates を self_care_automation/templates にコピーしました。"
fi

# 3. 静的ファイルの収集 (collectstatic を実行して WhiteNoise 用のファイルを生成)
echo "=== 静的ファイルの収集 ==="
python manage.py collectstatic --noinput --clear

# 4. データベースのマイグレーション
python manage.py migrate

# 5. スーパーユーザーの自動作成
python manage.py shell -c "
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

print(f'DEBUG: username={username}, email={email}')

if username and password:
    if not User.objects.filter(username=username).exists():
        try:
            User.objects.create_superuser(username=username, email=email, password=password)
            print('Superuser created successfully.')
        except Exception as e:
            print(f'Error creating superuser: {e}')
    else:
        print('Superuser already exists.')
else:
    print('WARNING: Superuser environment variables are not fully set.')
"