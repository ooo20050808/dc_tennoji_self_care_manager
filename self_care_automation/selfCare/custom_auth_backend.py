from typing import Any, Optional
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest


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
        メールアドレスとパスワードを用いてユーザーを検証する。
        """
        UserModel = get_user_model()

        # 管理者サイト等では 'username' フィールドにメールアドレスが渡されるため、これを補完する
        lookup_email = email or username

        if not lookup_email or not password:
            return None

        # 同一メールアドレスのユーザーが存在する場合、最初のユーザーを取得する
        # ※ first() は存在しない場合に None を返すため、DoesNotExist は発生しない
        user = UserModel.objects.filter(email=lookup_email).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None