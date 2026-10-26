import base64
from datetime import date, time, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages

from .models import HomeScreen, InputScreen, SaturdayOpening
from .forms import InputScreenForm, SaturdayOpeningForm

User = get_user_model()


# ==============================================================================
# 3.1 認証・権限管理および初期リダイレクト連携 (IT-AUTH)
# ==============================================================================
class AuthIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.client_user = User.objects.create_user(
            email="client@example.com",
            password="password123",
            user_name="利用太郎",
            user_role=1
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            user_name="スタッフ次郎",
            user_role=2,
            is_staff=True
        )
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
            user_name="管理者三郎"
        )

    def test_it_auth_01_client_login_and_homescreen_init(self):
        """IT-AUTH-01: 利用者ログインとHomeScreen初期化連携"""
        today = date.today()
        self.assertFalse(HomeScreen.objects.filter(user=self.client_user, date=today).exists())

        response = self.client.post(reverse('selfCare:login'), {
            'email': 'client@example.com',
            'password': 'password123'
        }, follow=True)

        home_screen = HomeScreen.objects.get(user=self.client_user, date=today)
        self.assertRedirects(response, reverse('selfCare:detail_select', kwargs={'home_screen_id': home_screen.id}))

    def test_it_auth_02_staff_and_admin_login_redirection(self):
        """IT-AUTH-02: スタッフ/管理者ログインの遷移制御"""
        response_staff = self.client.post(reverse('selfCare:login'), {
            'email': 'staff@example.com',
            'password': 'password123'
        })
        self.assertRedirects(response_staff, reverse('selfCare:saturday_choice'))
        self.client.logout()

        response_admin = self.client.post(reverse('selfCare:login'), {
            'email': 'admin@example.com',
            'password': 'password123'
        })
        self.assertRedirects(response_admin, reverse('selfCare:admin_screen'))

    def test_it_auth_03_admin_two_step_auth_session(self):
        """IT-AUTH-03: 管理者二段階認証とセッション連携"""
        self.client.force_login(self.admin_user)

        session = self.client.session
        session['target_user_id'] = self.client_user.id
        session['target_action'] = 'edit'
        session.save()

        response = self.client.get(
            reverse('selfCare:admin_screen_action', kwargs={'user_id': self.client_user.id, 'action': 'edit'})
        )
        self.assertEqual(self.client.session.get('target_user_id'), self.client_user.id)
        self.assertEqual(self.client.session.get('target_action'), 'edit')


# ==============================================================================
# 3.2 勤怠入力画面 (InputScreenForm & InputScreenView) 連携 (IT-INPUT)
# ==============================================================================
class InputScreenIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="client@example.com",
            password="password123",
            user_name="利用太郎",
            user_role=1
        )
        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            user_name="スタッフ次郎",
            user_role=2,
            is_staff=True
        )
        self.home_screen = HomeScreen.objects.create(user=self.user, date=date.today())
        self.input_screen = InputScreen.objects.create(date=self.home_screen, user=self.user)
        self.url = reverse('selfCare:input_screen', kwargs={'home_screen_id': self.home_screen.id})

    def test_it_input_01_attendance_time_order_validation(self):
        """IT-INPUT-01: 通常出勤時の入退出時刻・前後関係バリデーション"""
        self.client.force_login(self.user)

        res1 = self.client.post(self.url, {'entry_time': '10:00', 'leaving_time': '', 'at_home': ''})
        self.assertFormError(res1.context['form'], 'leaving_time', '退出時刻を入力してください。')

        res2 = self.client.post(self.url, {'entry_time': '15:00', 'leaving_time': '10:00', 'at_home': ''})
        self.assertFormError(res2.context['form'], 'leaving_time', '退出時刻は入室時刻より後の時刻を入力してください。')

        res3 = self.client.post(self.url, {'entry_time': '10:00', 'leaving_time': '15:00', 'at_home': ''})
        self.assertRedirects(res3, reverse('selfCare:complete_screen', kwargs={'home_screen_id': self.home_screen.id}))
        self.input_screen.refresh_from_db()
        self.assertEqual(self.input_screen.entry_time, time(10, 0))
        self.assertEqual(self.input_screen.leaving_time, time(15, 0))

    def test_it_input_02_at_home_staff_time_required(self):
        """IT-INPUT-02: 在宅勤務(at_home=True)時のスタッフ時刻必須連携"""
        self.client.force_login(self.user)

        res1 = self.client.post(self.url, {'at_home': 'on', 'staff_entry_time': '', 'staff_leaving_time': ''})
        self.assertFormError(res1.context['form'], 'staff_entry_time', '在宅の場合、スタッフ入室時刻は必須です。')
        self.assertFormError(res1.context['form'], 'staff_leaving_time', '在宅の場合、スタッフ退出時刻は必須です。')

        res2 = self.client.post(self.url, {
            'at_home': 'on',
            'staff_entry_time': '09:00',
            'staff_leaving_time': '12:00'
        })
        self.assertRedirects(res2, reverse('selfCare:complete_screen', kwargs={'home_screen_id': self.home_screen.id}))
        self.input_screen.refresh_from_db()
        self.assertTrue(self.input_screen.at_home)
        self.assertEqual(self.input_screen.staff_entry_time, time(9, 0))

    def test_it_input_03_sleep_time_validation_and_null(self):
        """IT-INPUT-03: 睡眠時間範囲バリデーション・NULL許容処理"""
        self.client.force_login(self.user)

        self.client.post(self.url, {'sleep_time_hours': '', 'entry_time': '10:00', 'leaving_time': '15:00'})
        self.input_screen.refresh_from_db()
        self.assertIsNone(self.input_screen.sleep_time_hours)

        # Django標準のIntegerField範囲エラーメッセージに合わせる
        res2 = self.client.post(self.url, {'sleep_time_hours': '25', 'entry_time': '10:00', 'leaving_time': '15:00'})
        self.assertFormError(res2.context['form'], 'sleep_time_hours', 'この値は 24 以下でなければなりません。')

        self.client.post(self.url, {'sleep_time_hours': '7', 'entry_time': '10:00', 'leaving_time': '15:00'})
        self.input_screen.refresh_from_db()
        self.assertEqual(self.input_screen.sleep_time_hours, 7)

    def test_it_input_04_condition_detail_auto_clearing(self):
        """IT-INPUT-04: 体調選択と動的モーダル詳細テキストの非連動データ消去"""
        self.client.force_login(self.user)

        self.client.post(self.url, {
            'condition': '〇',
            'condition_detail_good': 'すこぶる元気です',
            'entry_time': '10:00',
            'leaving_time': '15:00'
        })
        self.input_screen.refresh_from_db()
        self.assertEqual(self.input_screen.condition_detail_good, 'すこぶる元気です')

        self.client.post(self.url, {
            'condition': '△',
            'condition_detail_caution': '少し頭痛がします',
            'entry_time': '10:00',
            'leaving_time': '15:00'
        })
        self.input_screen.refresh_from_db()
        self.assertEqual(self.input_screen.condition_detail_good, '')
        self.assertEqual(self.input_screen.condition_detail_caution, '少し頭痛がします')

    def test_it_input_05_field_permission_control_by_role(self):
        """IT-INPUT-05: 利用者 vs スタッフの入力フィールド編集権限制御"""
        self.client.force_login(self.user)
        res_client = self.client.get(self.url)
        form_client = res_client.context['form']
        self.assertEqual(form_client.fields['staff_comment'].widget.attrs.get('disabled'), 'disabled')

        self.client.force_login(self.staff)
        res_staff = self.client.get(self.url)
        form_staff = res_staff.context['form']
        self.assertEqual(form_staff.fields['user_comment'].widget.attrs.get('disabled'), 'disabled')


# ==============================================================================
# 3.3 土曜開所日管理 (SaturdayOpening) & カレンダー連携 (IT-SAT)
# ==============================================================================
class SaturdayOpeningIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.client_user = User.objects.create_user(
            email="client@example.com",
            password="password123",
            user_name="利用太郎",
            user_role=1
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            user_name="スタッフ次郎",
            user_role=2,
            is_staff=True
        )

    def test_it_sat_01_bulk_registration_and_validation(self):
        """IT-SAT-01: 複数土曜日一括登録と多重バリデーション"""
        self.client.force_login(self.staff_user)
        url = reverse('selfCare:saturday_register')

        res1 = self.client.post(url, {'date_list': '2026-10-25\n2020-01-01'})
        # 複数エラーが発生する場合の検証用にリストや部分一致を確認
        form_errors = res1.context['form'].errors['date_list']
        self.assertTrue(any('土曜日ではありません' in err for err in form_errors))

        res2 = self.client.post(url, {'date_list': '2026-11-07, 2026-11-14'})
        self.assertRedirects(res2, reverse('selfCare:saturday_complete'))
        self.assertTrue(SaturdayOpening.objects.filter(open_date=date(2026, 11, 7)).exists())
        self.assertTrue(SaturdayOpening.objects.filter(open_date=date(2026, 11, 14)).exists())

    def test_it_sat_02_calendar_saturday_access_control(self):
        """IT-SAT-02: カレンダー画面における土曜開所/休業アクセス制御"""
        self.client.force_login(self.client_user)

        url_unregistered = reverse('selfCare:calendar_detail', kwargs={'year': 2026, 'month': 10, 'day': 31})
        res1 = self.client.get(url_unregistered, follow=True)
        self.assertRedirects(res1, reverse('selfCare:calendar_list'))

        SaturdayOpening.objects.create(open_date=date(2026, 11, 7), registered_by=self.staff_user)
        url_registered = reverse('selfCare:calendar_detail', kwargs={'year': 2026, 'month': 11, 'day': 7})
        res2 = self.client.get(url_registered)

        home_screen = HomeScreen.objects.get(user=self.client_user, date=date(2026, 11, 7))
        self.assertRedirects(res2, reverse('selfCare:input_screen', kwargs={'home_screen_id': home_screen.id}))

    def test_it_sat_03_bulk_delete_and_transaction(self):
        """IT-SAT-03: 土曜開所日一括削除とトランザクション連携"""
        self.client.force_login(self.staff_user)
        so1 = SaturdayOpening.objects.create(open_date=date(2026, 11, 7), registered_by=self.staff_user)
        so2 = SaturdayOpening.objects.create(open_date=date(2026, 11, 14), registered_by=self.staff_user)

        session = self.client.session
        session['delete_ids'] = [so1.id, so2.id]
        session.save()

        res = self.client.post(reverse('selfCare:saturday_delete_confirm'))
        self.assertRedirects(res, reverse('selfCare:saturday_delete_complete'))
        self.assertFalse(SaturdayOpening.objects.filter(id__in=[so1.id, so2.id]).exists())


# ==============================================================================
# 3.4 データ集計および Matplotlib グラフ生成連携 (IT-GRA)
# ==============================================================================
class GraphIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="client@example.com",
            password="password123",
            user_name="利用太郎",
            user_role=1
        )
        self.client.force_login(self.user)
        self.home_screen = HomeScreen.objects.create(user=self.user, date=date(2026, 10, 31))

        InputScreen.objects.create(
            date=self.home_screen,
            user=self.user,
            sleep_time_hours=8,
            condition='〇'
        )

    def test_it_gra_01_line_chart_generation(self):
        """IT-GRA-01: 過去30日間の睡眠時間・体調折れ線グラフ生成"""
        url_sleep = reverse('selfCare:chart', kwargs={'home_screen_id': self.home_screen.id, 'chart_type': 'sleep'})
        res_sleep = self.client.get(url_sleep)
        self.assertEqual(res_sleep.status_code, 200)
        self.assertTrue(res_sleep.context['chart_image'].startswith('data:image/png;base64,'))

        url_cond = reverse('selfCare:chart', kwargs={'home_screen_id': self.home_screen.id, 'chart_type': 'condition'})
        res_cond = self.client.get(url_cond)
        self.assertEqual(res_cond.status_code, 200)
        self.assertTrue(res_cond.context['chart_image'].startswith('data:image/png;base64,'))

    def test_it_gra_02_monthly_average_sleep_bar_chart(self):
        """IT-GRA-02: 過去3ヶ月の月間平均睡眠時間集計・棒グラフ連携"""
        url_bar = reverse('selfCare:chart',
                          kwargs={'home_screen_id': self.home_screen.id, 'chart_type': 'monthly_average_sleep'})
        res_bar = self.client.get(url_bar)
        self.assertEqual(res_bar.status_code, 200)
        self.assertTrue(res_bar.context['chart_image'].startswith('data:image/png;base64,'))


# ==============================================================================
# 3.5 ユーザー一覧・管理者CRUD処理連携 (IT-USR)
# ==============================================================================
class UserManagementIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
            user_name="管理者"
        )
        self.client.force_login(self.admin)

    def test_it_usr_01_user_list_pagination_and_missing_alert(self):
        """IT-USR-01: UserListView のページネーションおよび未記載アラート連携"""
        for i in range(25):
            User.objects.create_user(
                email=f"user{i}@example.com",
                password="password123",
                user_name=f"テストユーザー{i}",
                user_role=1
            )

        res = self.client.get(reverse('selfCare:user_list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['total_pages'], 2)

        user_page_data = res.context['user_pages'][0]
        self.assertTrue(user_page_data[0]['medication_missing'])

    def test_it_usr_02_user_create_and_password_hashing(self):
        """IT-USR-02: ユーザー新規作成・編集フローとパスワードハッシュ化"""
        session = self.client.session
        session['create_data'] = {
            'email': 'newstaff@example.com',
            'user_name': '新規スタッフ',
            'password': 'raw_password123',
            'user_role': 2
        }
        session.save()

        res = self.client.get(reverse('selfCare:user_create'))
        self.assertRedirects(res, reverse('selfCare:user_create_complete'))

        new_user = User.objects.get(email='newstaff@example.com')
        self.assertNotEqual(new_user.password, 'raw_password123')
        self.assertTrue(new_user.check_password('raw_password123'))
        self.assertTrue(new_user.is_staff)