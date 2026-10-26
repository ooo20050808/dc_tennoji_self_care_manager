from datetime import date, time
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import HomeScreen, InputScreen, SaturdayOpening
from .forms import (
    UserEditForm,
    InputScreenForm,
    SaturdayOpeningForm,
)

User = get_user_model()


# ==============================================================================
# 3.1 モデルテスト (models.py)
# ==============================================================================
class UserModelTest(TestCase):
    def test_ut_mod_001_create_user_success(self):
        """UT-MOD-001: ユーザー作成（正常系）

        【期待】ユーザー作成成功、USERNAME_FIELDがemail動作
        """
        user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            user_name="テスト太郎"
        )
        self.assertEqual(user.email, "testuser@example.com")
        self.assertEqual(user.user_name, "テスト太郎")
        self.assertTrue(user.check_password("password123"))
        self.assertEqual(User.USERNAME_FIELD, "email")

    def test_ut_mod_002_email_required(self):
        """UT-MOD-002: メールアドレス必須検証

        【期待】email空時に ValueError 発生
        """
        with self.assertRaises(ValueError) as cm:
            User.objects.create_user(
                email="",
                password="password123",
                user_name="テスト花子"
            )
        self.assertIn("Users must have an email address", str(cm.exception))

    def test_ut_mod_003_create_superuser(self):
        """UT-MOD-003: スーパーユーザー作成

        【期待】is_staff=True, is_superuser=True, user_role=3
        """
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword",
            user_name="管理者"
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.user_role, 3)

    def test_ut_mod_004_username_autocompletion_and_uniqueness(self):
        """UT-MOD-004: username自動補完・重複解消

        【期待】同名email前置詞の場合、user_1 等の連番付与
        """
        user1 = User.objects.create_user(
            email="duplicate@example.com",
            password="password123",
            user_name="ユーザー1"
        )
        # 1人目は email の @ より前 (duplicate) が username にセットされる
        self.assertEqual(user1.username, "duplicate")

        # 2人目: username を未指定のまま、同じ email 前置詞（メール自体は別ドメインなど）で作成
        user2 = User.objects.create_user(
            email="duplicate@example.jp",
            password="password123",
            user_name="ユーザー2"
        )
        # save() の自動補完ロジックにより重複が検知され "duplicate_1" が付与される
        self.assertEqual(user2.username, "duplicate_1")


class HomeScreenModelTest(TestCase):
    def test_ut_mod_005_str_representation(self):
        """UT-MOD-005: HomeScreen 文字列化（__str__）

        【期待】"日付: YYYY-MM-DD / ユーザー名: xxx" 返却
        """
        user = User.objects.create_user(
            email="hs_user@example.com",
            password="password123",
            user_name="ホーム太郎"
        )
        home_screen = HomeScreen.objects.create(
            date=date(2026, 10, 24),
            user=user
        )
        expected_str = f"日付: 2026-10-24 / ユーザー名: {user.username}"
        self.assertEqual(str(home_screen), expected_str)


class SaturdayOpeningModelTest(TestCase):
    def test_ut_mod_006_ordering(self):
        """UT-MOD-006: SaturdayOpening 並び順（ordering）

        【期待】open_date の降順（新しい日付順）取得
        """
        so1 = SaturdayOpening.objects.create(open_date=date(2026, 10, 31))
        so2 = SaturdayOpening.objects.create(open_date=date(2026, 11, 7))
        so3 = SaturdayOpening.objects.create(open_date=date(2026, 10, 24))

        openings = list(SaturdayOpening.objects.all())
        self.assertEqual(openings, [so2, so1, so3])


class InputScreenModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="input_user@example.com",
            password="password123",
            user_name="入力太郎"
        )
        self.home_screen = HomeScreen.objects.create(
            date=date(2026, 10, 24),
            user=self.user
        )

    def test_ut_mod_007_str_representation(self):
        """UT-MOD-007: InputScreen 文字列化（__str__）

        【期待】"Input for <id>" フォーマット返却
        """
        input_screen = InputScreen.objects.create(
            date=self.home_screen,
            user=self.user
        )
        self.assertEqual(str(input_screen), f"Input for {input_screen.id}")

    def test_ut_mod_008_cascade_delete(self):
        """UT-MOD-008: InputScreen カスケード削除

        【期待】紐づく User / HomeScreen 削除時に自動削除
        """
        input_screen = InputScreen.objects.create(
            date=self.home_screen,
            user=self.user
        )
        input_id = input_screen.id

        # HomeScreenの削除に伴いカスケード削除されるか
        self.home_screen.delete()
        self.assertFalse(InputScreen.objects.filter(id=input_id).exists())

        # 再度生成し、Userの削除に伴いカスケード削除されるか検証
        new_home_screen = HomeScreen.objects.create(
            date=date(2026, 10, 25),
            user=self.user
        )
        input_screen2 = InputScreen.objects.create(
            date=new_home_screen,
            user=self.user
        )
        input_id2 = input_screen2.id

        self.user.delete()
        self.assertFalse(InputScreen.objects.filter(id=input_id2).exists())

    def test_ut_mod_009_null_allowed_fields(self):
        """UT-MOD-009: InputScreen NULL許可フィールド検証

        【期待】時刻・睡眠時間・体調等の未入力時NULL保存
        """
        input_screen = InputScreen.objects.create(
            date=self.home_screen,
            user=self.user,
            entry_time=None,
            leaving_time=None,
            sleep_time_hours=None,
            condition=None,
            medication_morning=None,
            medication_noon=None,
            medication_night=None
        )
        input_screen.refresh_from_db()
        self.assertIsNone(input_screen.entry_time)
        self.assertIsNone(input_screen.leaving_time)
        self.assertIsNone(input_screen.sleep_time_hours)
        self.assertIsNone(input_screen.condition)
        self.assertIsNone(input_screen.medication_morning)
        self.assertIsNone(input_screen.medication_noon)
        self.assertIsNone(input_screen.medication_night)


# ==============================================================================
# 3.2 フォームテスト (forms.py)
# ==============================================================================
class UserEditFormTest(TestCase):
    def test_ut_frm_001_password_mismatch_validation(self):
        """UT-FRM-001: UserEditForm パスワード一致検証

        【期待】不一致時にバリデーションエラー発生
        """
        form_data = {
            "email": "edituser@example.com",
            "user_name": "編集太郎",
            "password": "newpassword123",
            "password_confirm": "differentpassword"
        }
        form = UserEditForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("password_confirm", form.errors)
        self.assertIn("パスワードが一致しません", form.errors["password_confirm"])


class InputScreenFormTest(TestCase):
    def test_ut_frm_002_sleep_time_boundary_values(self):
        """UT-FRM-002: InputScreenForm 睡眠時間（境界値）

        【期待】0, 12, 24 時間でバリデーション通過
        """
        for valid_sleep in [0, 12, 24]:
            form_data = {
                "sleep_time_hours": valid_sleep,
            }
            form = InputScreenForm(data=form_data)
            self.assertTrue(form.is_valid(), f"Sleep time {valid_sleep} should be valid. Errors: {form.errors}")

    def test_ut_frm_003_sleep_time_out_of_range(self):
        """UT-FRM-003: InputScreenForm 睡眠時間（範囲外）

        【期待】-1 や 25 時間でエラーメッセージ発生
        """
        for invalid_sleep in [-1, 25]:
            form_data = {
                "sleep_time_hours": invalid_sleep,
            }
            form = InputScreenForm(data=form_data)
            self.assertFalse(form.is_valid())
            self.assertIn("sleep_time_hours", form.errors)

    def test_ut_frm_004_attendance_time_order(self):
        """UT-FRM-004: InputScreenForm 出社時の時刻前後関係

        【期待】入室時刻 ＞ 退出時刻の場合にエラー発生
        """
        form_data = {
            "entry_time": "15:00",
            "leaving_time": "10:00",
            "at_home": False,
        }
        form = InputScreenForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("leaving_time", form.errors)
        self.assertIn("退出時刻は入室時刻より後の時刻を入力してください。", form.errors["leaving_time"])

    def test_ut_frm_005_at_home_staff_time_required(self):
        """UT-FRM-005: InputScreenForm 在宅時のスタッフ時刻必須

        【期待】at_home=True かつスタッフ時刻空でエラー発生
        """
        form_data = {
            "at_home": True,
            "staff_entry_time": "",
            "staff_leaving_time": "",
        }
        form = InputScreenForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("staff_entry_time", form.errors)
        self.assertIn("staff_leaving_time", form.errors)


class SaturdayOpeningFormTest(TestCase):
    def test_ut_frm_006_flexible_date_parsing(self):
        """UT-FRM-006: SaturdayOpeningForm 柔軟な日付パース

        【期待】カンマ/改行区切り、全角日付が正常パース
        """
        form_data = {
            "date_list": "２０２６/１０/３１, 2026-11-07"
        }
        form = SaturdayOpeningForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        cleaned_dates = form.cleaned_data["date_list"]
        self.assertIn(date(2026, 10, 31), cleaned_dates)
        self.assertIn(date(2026, 11, 7), cleaned_dates)

    def test_ut_frm_007_non_saturday_validation(self):
        """UT-FRM-007: SaturdayOpeningForm 土曜日以外の判定

        【期待】平日・日曜日指定時にエラー発生
        """
        form_data = {
            "date_list": "2026-10-25"  # 日曜日
        }
        form = SaturdayOpeningForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("2026-10-25 は土曜日ではありません。", str(form.errors))