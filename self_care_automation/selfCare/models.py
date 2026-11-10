from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
	"""カスタムユーザーマネージャー：メールアドレスを主キー（USERNAME_FIELD）としたユーザー作成を管理します。"""

	def create_user(self, email, password=None, user_name=None, **extra_fields):
		if not email:
			raise ValueError('Users must have an email address')

		email = self.normalize_email(email)
		user = self.model(
			email=email,
			user_name=user_name or email.split('@')[0],
			**extra_fields,
		)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email, username=None, password=None, user_name=None, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		extra_fields.setdefault('user_role', User.ADMIN)

		if not extra_fields.get('is_staff'):
			raise ValueError('Superuser must have is_staff=True.')
		if not extra_fields.get('is_superuser'):
			raise ValueError('Superuser must have is_superuser=True.')

		return self.create_user(email, password, user_name or username, **extra_fields)


class User(AbstractUser):
	"""メールアドレスをログインIDとして使用するカスタムユーザーモデル。"""

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = ['user_name']
	objects = UserManager()

	CLIENT = 1
	STAFF = 2
	ADMIN = 3
	ROLE_CHOICES = (
		(CLIENT, '利用者'),
		(STAFF, 'スタッフ'),
		(ADMIN, '管理者'),
	)

	email = models.EmailField(verbose_name="メールアドレス", unique=True, help_text="ログインIDとして使用されます")
	user_name = models.CharField(verbose_name="ユーザーネーム", max_length=150, blank=False)
	user_role = models.IntegerField(verbose_name="権限", choices=ROLE_CHOICES, default=CLIENT)

	# 慣習に合わせて DateTimeField（タイムスタンプ）に、変数名を created_at に修正
	created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
	updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

	groups = models.ManyToManyField(
		'auth.Group',
		related_name='selfcare_user_set',
		blank=True,
		related_query_name='selfcare_user',
	)
	user_permissions = models.ManyToManyField(
		'auth.Permission',
		related_name='selfcare_user_permissions_set',
		blank=True,
		related_query_name='selfcare_user',
	)

	class Meta:
		db_table = "user"
		verbose_name = "ユーザー"
		verbose_name_plural = "ユーザー"

	def save(self, *args, **kwargs):
		if not self.username:
			base_username = self.email.split('@')[0] if self.email else f"user_{__import__('uuid').uuid4().hex[:8]}"
			username = base_username
			counter = 1
			while User.objects.filter(username=username).exclude(pk=self.pk).exists():
				username = f"{base_username}_{counter}"
			counter += 1
			self.username = username
		super().save(*args, **kwargs)

	def __str__(self):
		return self.user_name or self.email


class HomeScreen(models.Model):
	"""ユーザーの毎日のホーム画面データを管理するモデル。"""

	date = models.DateField(verbose_name="日付", help_text="年月日を管理")
	user = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name="home_screens",
		verbose_name="ユーザー"
	)

	class Meta:
		db_table = "home_screen"
		verbose_name = "ホーム画面"
		verbose_name_plural = "ホーム画面"
		# 1人のユーザーが同じ日付のレコードを複数作れないように一意性制約を追加
		unique_together = ('date', 'user')

	def __str__(self):
		return f"日付: {self.date} / ユーザー名: {self.user.user_name}"


class InputScreen(models.Model):
	"""毎日の勤怠・体調・服薬などの詳細記録を管理するモデル。"""

	# 1日1件の仕様であれば ForeignKey から OneToOneField に変更し、変数名も直感的に修正
	home_screen = models.OneToOneField(
		HomeScreen,
		on_delete=models.CASCADE,
		related_name="input_screen",
		verbose_name="ホーム画面"
	)
	user = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name="input_screens_by_user",
		verbose_name="ユーザー"
	)
	entry_time = models.TimeField(verbose_name="入室時刻", null=True, blank=True)
	leaving_time = models.TimeField(verbose_name="退出時刻", null=True, blank=True)
	staff_entry_time = models.TimeField(verbose_name="スタッフ用入室時刻", null=True, blank=True)
	staff_leaving_time = models.TimeField(verbose_name="スタッフ用退出時刻", null=True, blank=True)
	sleep_time_hours = models.IntegerField(verbose_name="睡眠時間（時間）", null=True, blank=True)
	morning_work_content = models.TextField(blank=True, null=True, verbose_name="午前作業内容")
	afternoon_work_content = models.TextField(blank=True, null=True, verbose_name="午後作業内容")
	condition = models.CharField(max_length=1, verbose_name="体調", null=True, blank=True)

	condition_detail_good = models.TextField(null=True, blank=True, verbose_name="体調詳細（良好）")
	condition_detail_caution = models.TextField(null=True, blank=True, verbose_name="体調詳細（注意）")
	condition_detail_poor = models.TextField(null=True, blank=True, verbose_name="体調詳細（悪化）")

	# BooleanField の null=True を廃止し、2値（True/False）に統一
	medication_morning = models.BooleanField(default=False, verbose_name="朝の服薬チェック")
	medication_noon = models.BooleanField(default=False, verbose_name="昼の服薬チェック")
	medication_night = models.BooleanField(default=False, verbose_name="夜の服薬チェック")

	user_comment = models.CharField(max_length=255, null=True, blank=True, verbose_name="ユーザーコメント")
	staff_comment = models.CharField(max_length=255, null=True, blank=True, verbose_name="スタッフコメント")
	at_home = models.BooleanField(default=False, verbose_name="在宅状況")

	class Meta:
		db_table = "input_screen"
		verbose_name = "入力画面"
		verbose_name_plural = "入力画面"

	def __str__(self):
		return f"Input for {self.id} ({self.user.user_name})"


class SaturdayOpening(models.Model):
	"""土曜日の開所日を管理するモデル。"""

	open_date = models.DateField(unique=True, verbose_name="土曜開所日")
	registered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="登録スタッフ")
	registered_at = models.DateTimeField(auto_now_add=True, verbose_name="登録日時")

	class Meta:
		verbose_name = "土曜開所日"
		verbose_name_plural = "土曜開所日"
		ordering = ['-open_date']

	def __str__(self):
		registrant = self.registered_by.user_name if self.registered_by else 'N/A'
		return f"{self.open_date.isoformat()} (登録者: {registrant})"
