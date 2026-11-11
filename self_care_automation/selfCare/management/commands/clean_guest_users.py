from django.core.management.base import BaseCommand
from selfCare.models import User

class Command(BaseCommand):
	help = '開発者（あなた）が用意した初期アカウント以外の、ゲストが作成したユーザーを安全に削除します。'

	def handle(self, *args, **options):
		# 残したい（絶対に削除しない）あなたのアカウントのメールアドレスをリストに指定します
		WHITE_LIST_EMAILS = [
			'admin@example.com',
			'staff@example.com',
			'client@example.com',
		]

		self.stdout.write(self.style.NOTICE('ゲストユーザーのクリーンアップ処理を開始します...'))

		# ホワイトリストに含まれておらず、かつスーパーユーザーでもないユーザーを抽出
		target_users = User.objects.exclude(email__in=WHITE_LIST_EMAILS).filter(is_superuser=False)

		count = target_users.count()

		if count == 0:
			self.stdout.write(self.style.SUCCESS('削除対象のゲストユーザーは存在しませんでした。'))
			return

		# 関連データ（InputScreen等）も含めて一括削除
		target_users.delete()

		self.stdout.write(self.style.SUCCESS(f'正常に {count} 件のゲストユーザーを削除しました。'))
