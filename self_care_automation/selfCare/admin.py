from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, HomeScreen, InputScreen


# カスタムUserAdminクラス
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # 管理者サイトでのフィールド表示設定
    list_display = ('email', 'user_name', 'user_role', 'is_staff', 'is_superuser')
    list_filter = ('user_role', 'is_staff', 'is_superuser')
    search_fields = ('email', 'user_name')

    # ユーザー編集画面のフィールド設定
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('個人情報', {'fields': ('user_name',)}),
        ('権限', {'fields': ('user_role', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('重要な日付', {'fields': ('last_login', 'date_joined')}),
    )

    # ユーザー作成画面のフィールド設定
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'user_name', 'password1', 'password2'),
        }),
    )

    # ユーザー検索の順序
    ordering = ('email',)


# 他のモデルを登録
admin.site.register(HomeScreen)
admin.site.register(InputScreen)