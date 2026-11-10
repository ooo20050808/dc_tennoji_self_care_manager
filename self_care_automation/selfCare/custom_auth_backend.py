from typing import Any, Optional
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest

UserModel = get_user_model()


class EmailBackend(ModelBackend):
    """
    メールアドレスを使用してユーザー認証を行うためのカスタム認証バックエンド。
    Django標準の管理者サイト（usernameを使用）およびフロントエンド（emailを使用）の両方に対応します。
    """

    def authenticate(
        self,
        request: Optional[HttpRequest],
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[AbstractBaseUser]:
        """
        メールアドレスとパスワードを用いてユーザーを検証します。
        """
        # 管理者サイト等では 'username' フィールドにメールアドレスが渡されるため、これを補完する
        lookup_email = email or username

        if not lookup_email or not password:
            return None

        try:
            # ユーザーモデルのemailフィールドに一意性制約(unique=True)が設定されている前提
            user = UserModel.objects.get(email=lookup_email)
        except UserModel.DoesNotExist:
            # 認証失敗時のタイミング攻撃（タイミングサイドチャネル）を防ぐため、
            # ユーザーが存在しない場合でもダミーのパスワード検証を行い、処理時間を一定に保つ（Django標準のセキュリティ対策）
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
