#authenticate関数がメールアドレスで認証できるようにするためのカスタム認証バックエンド

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, email=None, password=None, **kwargs):
        UserModel = get_user_model()
        
        # 管理者サイトはusernameフィールドを使用するため、usernameをemailとして扱う
        if username is not None and email is None:
            email = username
        elif email is not None and username is None:
            email = email
            
        if email is None:
            return None
            
        try:
            #同じメールアドレスのユーザーがいた場合始めのユーザーを取得
            user = UserModel.objects.filter(email=email).first()
            if user is not None and user.check_password(password):
                return user

        except UserModel.DoesNotExist:
            #ユーザーが見つからない場合は認証失敗
            return None
        return None
