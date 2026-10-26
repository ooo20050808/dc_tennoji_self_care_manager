from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, user_name=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            user_name=user_name or email.split('@')[0],
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username=None, password=None, user_name=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_role', 3)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, user_name or username, **extra_fields)

#userモデル

class User(AbstractUser):
    # USERNAME_FIELDをemailに設定することで、Djangoの認証システムに
    # ユーザー名としてemailを使用するように指示
    USERNAME_FIELD = 'email'
    objects = UserManager()

    email = models.EmailField(
        verbose_name="メールアドレス",
        unique=True,
        help_text="ログインIDとして使用されるため、重複は許可されません"
    )

    # ユーザー作成時に必須とするフィールドを定義。
    # emailがUSERNAME_FIELDなので、ここではusernameとuser_nameを必須から除外。
    REQUIRED_FIELDS = ['user_name']

    # 権限の選択肢を定義
    CLIENT = 1
    STAFF = 2
    ADMIN = 3
    ROLE_CHOICES = (
        (CLIENT, '利用者'),
        (STAFF, 'スタッフ'),
        (ADMIN, '管理者'),
    )

    # groupsとuser_permissionsのリバースアクセサーの競合を解消
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='selfcare_user_set',
        blank=True,
        help_text='ユーザーグループ',
        related_query_name='selfcare_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='selfcare_user_permissions_set',
        blank=True,
        help_text='ユーザー権限グループ.',
        related_query_name='selfcare_user',
    )

    # user_nameフィールド
    user_name = models.CharField(
        verbose_name="ユーザーネーム",
        max_length=150,
        blank=False,
        help_text="ユーザーネーム"
    )

    # user_roleフィールド
    user_role = models.IntegerField(
        verbose_name="権限",
        help_text="ユーザーの権限を管理（利用者かスタッフか管理者か）",
        choices=ROLE_CHOICES,
        default=1  # ユーザーのデフォルト権限を利用者(1)に設定するのが一般的
    )

    # 作成日時と更新日時
    create_at = models.DateField(
        auto_now_add=True,
        verbose_name="作成日時"
    )
    update_at = models.DateField(
        auto_now=True,
        verbose_name="更新日時"
    )

    class Meta:
        db_table = "user"
        verbose_name = "ユーザー"
        verbose_name_plural = "ユーザー"

    def save(self, *args, **kwargs):
        # usernameが空の場合、emailから自動生成
        if not self.username:
            if self.email:
                base_username = self.email.split('@')[0]
            else:
                import uuid
                base_username = f"user_{uuid.uuid4().hex[:8]}"

            # usernameが既に存在する場合は一意になるように調整
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exclude(pk=self.pk).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            self.username = username

        super().save(*args, **kwargs)

    # __str__メソッドをクラスの直下に移動し、`user_name`または`email`を返すように修正
    def __str__(self):
        if self.user_name:
            return self.user_name
        else:
            return self.email


## home_screen（ホーム画面）のモデル

class HomeScreen(models.Model):
    date = models.DateField(
        verbose_name="日付",
        help_text="年月日を管理"
    )

    # userはuserモデルの外部キーとして設定
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="home_screens",
        verbose_name="ユーザー",
        help_text="ユーザー"
    )

    class Meta:
        db_table = "home_screen"
        verbose_name = "ホーム画面"
        verbose_name_plural = "ホーム画面"

    # __str__メソッド
    def __str__(self):
        return "日付: " + str(self.date) + " / ユーザー名: " + str(self.user.username)

## input_screenのモデル

class InputScreen(models.Model):
    date = models.ForeignKey(
        "HomeScreen",
        on_delete=models.CASCADE,
        related_name="input_screens",
        verbose_name="日付",
        help_text="紐づいているホーム画面の日付"
    )
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="input_screens_by_user",
        verbose_name="ユーザー",
        help_text="この入力画面を作成したユーザー"
    )
    entry_time = models.TimeField(
        verbose_name="入室時刻",
        help_text="入室時刻を管理",
        null=True,
        blank=True
    )
    leaving_time = models.TimeField(
        verbose_name="退出時刻",
        help_text="退出時刻を管理",
        null=True,  # 修正: NULLを許可
        blank=True
    )
    staff_entry_time = models.TimeField(
        verbose_name="スタッフ用入室時刻",
        help_text="スタッフが記録する入室時刻",
        null=True,
        blank=True
    )
    staff_leaving_time = models.TimeField(
        verbose_name="スタッフ用退出時刻",
        help_text="スタッフが記録する退出時刻",
        null=True,
        blank=True
    )
    sleep_time_hours = models.IntegerField(
        verbose_name="睡眠時間（時間）",
        help_text="睡眠時間を時間単位で管理",
        null=True,  # 修正: NULLを許可
        blank=True
    )
    morning_work_content = models.TextField(
        blank=True,
        null=True,
        verbose_name="午前作業内容",
        help_text="午前の作業内容を記録"
    )
    afternoon_work_content = models.TextField(
        blank=True,
        null=True,
        verbose_name="午後作業内容",
        help_text="午後の作業内容を記録"
    )
    condition = models.CharField(
        max_length=1,
        verbose_name="体調",
        help_text="体調を管理",
        null=True,  # 修正: NULLを許可
        blank=True
    )
    # 【追加】体調の詳細情報
    condition_detail_good = models.TextField(
        null=True,
        blank=True,
        help_text='体調が良好（〇）な場合の詳細説明'
    )
    condition_detail_caution = models.TextField(
        null=True,
        blank=True,
        help_text='体調に注意（△）が必要な場合の詳細説明（症状や予兆など）'
    )
    condition_detail_poor = models.TextField(
        null=True,
        blank=True,
        help_text='体調が不調（✕）な場合の詳細説明（症状など）'
    )
    medication_morning = models.BooleanField(
        default=False,  # 修正: NULLを許可する場合、default=None に変更することを推奨
        verbose_name="朝の服薬チェック",
        help_text="朝の服薬の有無を管理",
        null=True  # 必須修正: NULLを許可
    )
    medication_noon = models.BooleanField(
        default=False,  # 修正: NULLを許可する場合、default=None に変更することを推奨
        verbose_name="昼の服薬チェック",
        help_text="昼の服薬の有無を管理",
        null=True  # 必須修正: NULLを許可
    )
    medication_night = models.BooleanField(
        default=False,  # 修正: NULLを許可する場合、default=None に変更することを推奨
        verbose_name="夜の服薬チェック",
        help_text="夜の服薬の有無を管理",
        null=True  # 必須修正: NULLを許可
    )
    user_comment = models.CharField(
        max_length = 255,
        null = True, #  #ユーザー用コメントの空白を許容する
        blank = True,
        verbose_name = "ユーザーコメント"
    )
    staff_comment = models.CharField(
        max_length=255,
        blank = True,
        null = True,
        verbose_name = "スタッフコメント",
        help_text = "スタッフコメント"
    )
    at_home = models.BooleanField(
        default=False,
        verbose_name="在宅状況",
        help_text="ユーザーが在宅中かどうかを示す"
    )
    class Meta:
        db_table = "input_screen"
        verbose_name = "入力画面"
        verbose_name_plural = "入力画面"

    def __str__(self):
        return "Input for " + str(self.id)

#土曜日の開所日を記録するモデル
class SaturdayOpening(models.Model):
    open_date = models.DateField(
        unique=True,
        verbose_name="土曜開所日",
        help_text="開所する土曜日の日付"
    )
    registered_by = models.ForeignKey(
        "User", # 既存のUserモデルを参照
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="登録スタッフ"
    )
    registered_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="登録日時"
    )

    class Meta:
        verbose_name = "土曜開所日"
        verbose_name_plural = "土曜開所日"
        # open_dateの新しい日付から降順で並べる
        ordering = ['-open_date']

    def __str__(self):
        # 登録ユーザー名が取得できれば表示、なければ'N/A'
        registrant = self.registered_by.user_name if self.registered_by else 'N/A'
        return f"{self.open_date.isoformat()} (登録者: {registrant})"