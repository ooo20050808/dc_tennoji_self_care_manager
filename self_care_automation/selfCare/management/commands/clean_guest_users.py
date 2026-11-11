# selfCare/management/commands/clean_guest_users.py

from django.core.management.base import BaseUserManager, BaseCommand
from django.utils import timezone
from selfCare.models import User


class Command(BaseCommand):
	help = '開発者（あなた）が用意した初期アカウント以外の、ゲストが作成したユーザーを安全に削除します。'

	def handle(self, *args, **options):
		# 🟢 残したい（絶対に削除しない）あなたのアカウントのメールアドレスをリストに指定します
		WHITE_LIST_EMAILS = [
			'admin@example.com',
			'a@example.com',
			's@example.com',
			'd@example.com'
		]

		self.stdout.write(self.style.NOTICE('ゲストユーザーのクリーンアップ処理を開始します...'))

		# ホワイトリストに含まれておらず、かつスーパーユーザー（is_superuser=True）でもないユーザーを抽出
		# (万が一コマンド実行用のアカウントが消えないようにセーフティをかけています)
		target_users = User.objects.exclude(email__in=WHITE_LIST_EMAILS).filter(is_superuser=False)

		count = target_users.count()

		if count == 0:
			self.stdout.write(self.style.SUCCESS('削除対象のゲストユーザーは存在しませんでした。'))
			return

		# 関連するデータ（InputScreen, HomeScreenなど）はモデルの on_delete=models.CASCADE により自動で連動削除されます
		target_users.delete()

		self.stdout.write(self.style.SUCCESS(f'正常に {count} 件のゲストユーザーを削除しました。'))
