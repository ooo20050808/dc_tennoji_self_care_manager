from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, View, TemplateView
from django.urls import reverse_lazy # リダイレクト先として使用
from django.db import transaction # データベース操作の原子性確保
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from .forms import LoginForm, AuthForm, UserOnlyAuthForm, UserEditForm, UserCreateForm, InputScreenForm, SaturdayOpeningForm, SaturdayOpeningDeleteForm
from .models import User, HomeScreen, InputScreen, SaturdayOpening
from .models import User
import calendar
from datetime import date, timedelta, time
import pdb
import matplotlib.pyplot as plt
import japanize_matplotlib
import io
import urllib, base64
from django.db.models import F, Sum # <--- Sum を追加
from django.utils import timezone
from django.utils import timezone
from datetime import datetime


# Create your views here.


def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            #ユーザー認証
            user = authenticate(request, email=email, password=password)



            if user is not None:
                #認証成功
                login(request, user)
                #ユーザー権限に応じてリダイレクト先を変更
                #利用者を１スタッフを２管理者を３とする
                if user.user_role == 1:
                    # 利用者の場合、ログイン後、今日の日付のHomeScreenデータを取得（または作成）し、
                    # 詳細選択画面（コメント一覧/入力画面）に遷移させる
                    from datetime import date  # date を利用するために再確認
                    today = date.today()
                    try:
                        # ログインユーザーと今日の日付に対応する HomeScreen データを探す
                        home_screen_data = HomeScreen.objects.get(user=user, date=today)
                    except HomeScreen.DoesNotExist:
                        # データが存在しない場合は新規作成
                        home_screen_data = HomeScreen.objects.create(user=user, date=today)

                    # home_screen_id を渡して詳細選択画面にリダイレクト
                    return redirect("selfCare:detail_select", home_screen_id=home_screen_data.id)  # 画面選択ページに遷移
                elif user.user_role == 2:
                    return redirect('selfCare:saturday_choice')#スタッフの場合はカレンダー一覧に遷移するか土曜日開所日を選択する画面に遷移するか選択できる画面に遷移
                else:
                    return redirect("selfCare:admin_screen")#権限が管理者の場合管理者画面に遷移
            else:
                #認証失敗
                return  render(request, 'login.html', {'form': form, 'error_message': 'ユーザー名またはパスワードが間違っています。'})

    else:
        #GETリクエストだった場合
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

#利用者一覧ビュー
class UserListView(LoginRequiredMixin, View):
    def get(self, request, action=None, *args, **kwargs):
        all_users = list(User.objects.filter(user_role=1))#利用者(user_role=1)のみを取得
        # ユーザーの権限を取得
        user_role = request.user.user_role

        # 管理者の場合、利用者とスタッフを両方取得
        if user_role == 3:
            all_users = list(User.objects.filter(user_role__in=[1, 2]))  # 利用者とスタッフをまとめて取得
        else:
            all_users = list(User.objects.filter(user_role=1))  # 利用者のみを取得

        # クエリパラメータなどから「完了画面から遷移してきたか」を判定フラグとして取得
        from_complete = request.GET.get('from') == 'complete'
        if from_complete:
            # 完了画面からの遷移の場合は、アクション（編集・削除モード）を強制解除・クリアする
            action = None
            if 'target_action' in request.session:
                del request.session['target_action']
            if 'target_user_id' in request.session:
                del request.session['target_user_id']

        try:
            # URLのGETパラメータから日付を取得（例: ?date=2025-10-01）
            date_str = request.GET.get('date')
            if date_str:
                # 文字列を date オブジェクトに変換し、セッションにも保存する
                view_date = date.fromisoformat(date_str)
                request.session['selected_date_for_user_list'] = date_str
            else:
                # GETパラメータがない場合、セッションに保持されている日付があればそれを使用する
                session_date_str = request.session.get('selected_date_for_user_list')
                if session_date_str:
                    view_date = date.fromisoformat(session_date_str)
                else:
                    # どちらもなければ今日の日付を使用
                    view_date = date.today()
        except ValueError:
            # 日付形式が無効な場合は、今日の日付を使用
            view_date = date.today()

        page_size = 20  # 4行 x 5列 = 1テーブルあたり20ユーザー
        total_users = len(all_users)
        # 総ページ数を計算 (ceil(total_users / page_size))
        total_pages = (total_users + page_size - 1) // page_size

        # GETパラメータから現在のページ番号を取得（デフォルトは1）
        try:
            page_num = int(request.GET.get('page', 1))
        except ValueError:
            page_num = 1  # 無効な値の場合は1ページ目

        # ページ番号が範囲外の場合は調整
        if page_num < 1:
            page_num = 1
        elif page_num > total_pages:
            # ユーザーがいない場合 (total_pages=0) に備えて、max(1, total_pages)とすることも可能だが、
            # データがある前提でtotal_pagesに丸めます。
            page_num = max(1, total_pages)

        # ページに応じたユーザーリストを切り出し
        start_index = (page_num - 1) * page_size
        end_index = start_index + page_size
        current_page_users = all_users[start_index:end_index]  # 該当ページのユーザーのみ

        user_data = []
        # セッションから編集データを取得
        edit_data = request.session.get('edit_data', {})
        for user in all_users:

            home_screen_id = None
            entry_time_display = "未入力"
            leaving_time_display = "未入力"
            sleep_time_display = "未入力"
            condition_display = "未入力"
            #InputScreenデータの取得と服薬チェック
            medication_missing = False  # 初期値: 未記載ではない
            try:
                home_screen = HomeScreen.objects.get(user=user, date=view_date)
                home_screen_id = home_screen.id
            except HomeScreen.DoesNotExist:
                home_screen = HomeScreen.objects.create(user=user, date=view_date)
                home_screen_id = home_screen.id
            try:
                input_data = InputScreen.objects.get(user=user, date__date=view_date)  # 日付でフィルタリング
                home_screen_id = input_data.date.id

                if input_data:
                    #値を更新するために先に入退出時刻を取得
                    if input_data.staff_entry_time:
                        entry_time_display = input_data.staff_entry_time.strftime("%H:%M")
                        # スタッフ入力がなければ利用者入力の時刻を使用
                    elif input_data.entry_time:
                        entry_time_display = input_data.entry_time.strftime("%H:%M")

                        # スタッフ入力の時刻を優先
                    if input_data.staff_leaving_time:
                        leaving_time_display = input_data.staff_leaving_time.strftime("%H:%M")
                        # スタッフ入力がなければ利用者入力の時刻を使用
                    elif input_data.leaving_time:
                        leaving_time_display = input_data.leaving_time.strftime("%H:%M")
                    # 睡眠時間: sleep_time_hoursの値を取得し、小数点なしで「〇時間」形式に整形
                    # sleep_time_hoursはfloatフィールドの可能性があるため、int()で整数に変換します。
                    if input_data.sleep_time_hours is not None and input_data.sleep_time_hours > 0:
                        # 小数点はつかないという要望に基づき、整数に丸めて表示
                        sleep_time_display = f"{int(input_data.sleep_time_hours)}時間"

                    # 体調: conditionの値を取得
                    if input_data.condition:
                        condition_display = input_data.condition
                    #朝・昼・夜のいずれかがNone（未記載）の場合にTrue
                    # 朝・昼・夜のいずれかがNone（未記載）またはFalseの場合にTrue
                    medication_incomplete = (
                            input_data.medication_morning is None or input_data.medication_morning == False or
                            input_data.medication_noon is None or input_data.medication_noon == False or
                            input_data.medication_night is None or input_data.medication_night == False
                    )

                    other_data_missing = (
                            entry_time_display == "未入力" or
                            leaving_time_display == "未入力" or
                            sleep_time_display == "未入力" or
                            condition_display == "未入力"
                    )
                    if medication_incomplete or other_data_missing:
                        medication_missing = True
                    else:
                        # InputScreenデータがない場合はすべて未入力として扱う
                        medication_missing = True

            except InputScreen.DoesNotExist:
                input_data = None  # データがない場合はNone
                medication_missing = True



            monthly_average_chart = None
            overall_average_sleep_time = None
            average_sleep_time_display = ""  # 初期表示は空欄

            # ユーザーの表示名を決定。初期値は元のユーザー名
            display_name = user.user_name
            if not display_name:
                display_name = user.email

            # セッションに編集データがあり、かつ現在のユーザーの編集データであるかを確認
            if edit_data and edit_data.get('id') == user.id:
                # 編集データに'user_name'キーが存在する場合のみ、表示名を更新
                if 'user_name' in edit_data:
                    display_name = edit_data['user_name']
                # 編集データに user_name がなく、email がある場合は email を使用
                elif 'email' in edit_data:
                    display_name = edit_data['email']
            #グラフと平均睡眠時間の取得ロジック
            #グラフ画像データURI、グラフタイトル、平均睡眠時間を取得
            # 修正後: 5つの戻り値を受け取るために「_, _」を末尾に追加します
            monthly_average_chart, _, overall_average_sleep_time, _, _ = create_monthly_average_sleep_chart(
                user=user,
                end_date=view_date
            )

            # 平均睡眠時間を小数点以下第1位までの文字列として準備
            # 月の最終日かつデータがある場合のみ、値がセットされる
            if overall_average_sleep_time is not None:
                average_sleep_time_display = f"{overall_average_sleep_time}h"
            else:
                # 月の最終日ではない場合やデータがない場合はNoneのままにする
                average_sleep_time_display = None

            # 平均睡眠時間を小数点以下第1位までの文字列として準備
            # 平均睡眠時間を小数点以下第1位までの文字列として準備
            # 月の最終日かつデータがある場合のみ、値がセットされる
            user_data.append({
                "user": user,
                "input_data": input_data,
                "display_name": display_name,
                "entry_time_display": entry_time_display,
                "leaving_time_display": leaving_time_display,
                "sleep_time": sleep_time_display,
                "average_sleep_time": average_sleep_time_display,
                "condition": condition_display,
                "view_date": view_date,
                "home_screen_id": home_screen_id,
                "medication_missing": medication_missing,
                "action": action,
            })


        #リストを２０個ずつのリストに分割
        user_pages = [user_data[i:i + page_size] for i in range(0, len(user_data), page_size)]



        context = {
            "user_pages" : user_pages,
            "user_role": request.user.user_role,  ##ユーザーの権限をテンプレートに渡す
            "total_pages": total_pages,
            "page_num": page_num,
            "view_date": view_date
        }

        return render(request, "user_list.html", context)

# カレンダー一覧ビュー
class CalendarListView(LoginRequiredMixin, ListView):
    model = HomeScreen
    template_name = "calendar_list.html"
    context_object_name = "home_screens"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # URLから年と月を取得。なければ現在の年月に設定
        today = date.today()
        year = int(self.request.GET.get("year", today.year))
        month = int(self.request.GET.get("month", today.month))

        # カレンダーのヘッダーに表示する「何年何月」の情報を取得
        current_month_year = date(year, month, 1)
        context["current_month_year"] = current_month_year

        # カレンダーオブジェクトを作成
        cal = calendar.Calendar(firstweekday=6)  # 日曜日始まり
        month_days = cal.monthdatescalendar(year, month)

        # 土曜開所日のデータ取得
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        registered_saturdays = set(
            SaturdayOpening.objects.filter(
                open_date__range=[start_date, end_date]
            ).values_list('open_date', flat=True)
        )

        # month_days の各日付に、開所日フラグやHomeScreenのIDを安全に追加
        annotated_month_days = []
        for week in month_days:
            annotated_week = []
            for day in week:
                is_saturday = day.weekday() == calendar.SATURDAY
                is_open_saturday = day in registered_saturdays

                is_input_complete = False
                home_screen_id = None

                if day.month == month:  # 当月の日付のみチェック・作成
                    # 確実にHomeScreenを取得または作成し、idをテンプレートに渡せるようにする
                    home_screen, _ = HomeScreen.objects.get_or_create(user=self.request.user, date=day)
                    home_screen_id = home_screen.id

                    try:
                        input_screen = InputScreen.objects.get(date=home_screen, user=self.request.user)

                        if input_screen.at_home:
                            basic_field_complete = (
                                input_screen.sleep_time_hours is not None and
                                input_screen.condition is not None
                            )
                            medication_complete = (
                                input_screen.medication_morning is True and
                                input_screen.medication_noon is True and
                                input_screen.medication_night is True
                            )
                            work_complete = (
                                input_screen.morning_work_content is not None and
                                input_screen.morning_work_content.strip() != "" and
                                input_screen.afternoon_work_content is not None and
                                input_screen.afternoon_work_content.strip() != ""
                            )
                            comment_complete = (
                                input_screen.user_comment is not None and
                                input_screen.user_comment.strip() != "" and
                                input_screen.staff_comment is not None and
                                input_screen.staff_comment.strip() != ""
                            )
                            time_complete = (
                                input_screen.staff_entry_time is not None and
                                input_screen.staff_leaving_time is not None
                            )
                        else:
                            basic_field_complete = (
                                input_screen.sleep_time_hours is not None and
                                input_screen.condition is not None
                            )
                            medication_complete = (
                                input_screen.medication_morning is True and
                                input_screen.medication_noon is True and
                                input_screen.medication_night is True
                            )
                            work_complete = (
                                input_screen.morning_work_content is not None and
                                input_screen.morning_work_content.strip() != "" and
                                input_screen.afternoon_work_content is not None and
                                input_screen.afternoon_work_content.strip() != ""
                            )
                            comment_complete = (
                                input_screen.user_comment is not None and
                                input_screen.user_comment.strip() != "" and
                                input_screen.staff_comment is not None and
                                input_screen.staff_comment.strip() != ""
                            )
                            time_complete = (
                                input_screen.entry_time is not None and
                                input_screen.leaving_time is not None
                            )

                        completion_status = {
                            'basic': basic_field_complete,
                            'medication': medication_complete,
                            'comment': comment_complete,
                            'time': time_complete
                        }
                        is_input_complete = all(completion_status.values())

                    except InputScreen.DoesNotExist:
                        is_input_complete = False

                annotated_week.append({
                    'date': day,
                    'is_saturday': is_saturday,
                    'is_open_saturday': is_open_saturday,
                    'is_input_complete': is_input_complete,
                    'home_screen_id': home_screen_id,  # テンプレート側で利用可能にする
                })
            annotated_month_days.append(annotated_week)

        context["year"] = year
        context["month"] = month
        context["month_days"] = month_days
        context["month_days_annotated"] = annotated_month_days

        prev_month_date = date(year, month, 1) - timedelta(days=1)
        next_month_date = date(year, month, 1) + timedelta(days=32)
        context['prev_month_url'] = "?year={}&month={}".format(prev_month_date.year, prev_month_date.month)
        context['next_month_url'] = "?year={}&month={}".format(next_month_date.year, next_month_date.month)

        context["user_role"] = self.request.user.user_role
        context["user"] = self.request.user

        return context


    #ログイン中のユーザーのみのデータを取得
    def get_queryset(self):
        return HomeScreen.objects.filter(user=self.request.user)

##日付けクリック時の処理を行うビュー
def calendar_detail_view(request, year, month, day):
    #クリックされた日付を取得
    selected_date= date(year, month, day)
    user = request.user

    #日曜日の入力制限ロジックの追加
    # 選択された日が日曜日（カレンダーモジュールの weekday() で 6）であるかチェック
    is_sunday = selected_date.weekday() == calendar.SUNDAY  # 日曜日は6（月曜始まり0, 日曜始まり6）

    if is_sunday:
        # 日曜日の場合、利用者・スタッフ/管理者に関わらず入力不可としてリダイレクト
        messages.error(request, f'{selected_date.strftime("%Y年%m月%d日")} は日曜休業日のため、入力できません。')
        return redirect("selfCare:calendar_list")

    #土曜日の入力制限ロジックの追加
    #選択された日が土曜日（カレンダーモジュールの weekday() で 5）であるかチェック
    is_saturday = selected_date.weekday() == calendar.SATURDAY

    if is_saturday:
        #土曜日の場合、その日が SaturdayOpening に登録されているかチェック
        is_open_saturday = SaturdayOpening.objects.filter(open_date=selected_date).exists()

        #土曜日だが開所日として登録されていない場合、リダイレクトしてエラーメッセージを表示
        if not is_open_saturday:
            # 利用者（user_role=1）で、かつ開所日ではない土曜日の場合、データ入力不可
            if user.user_role == 1:
                messages.error(request, f'{selected_date.strftime("%Y年%m月%d日")} は土曜休業日のため、入力できません。')
                return redirect("selfCare:calendar_list")
            # スタッフ/管理者（user_role=2 or 3）で、かつ開所日ではない土曜日の場合、利用者一覧へ遷移しない
            elif user.user_role in [2, 3]:
                # スタッフ/管理者も利用者一覧画面へ遷移するのを阻止し、カレンダー一覧に戻す
                # ただし、スタッフ/管理者はカレンダーでクリックしても強制的に利用者一覧へ遷移するため、
                # ここでブロックするのが適切です。
                messages.error(request,
                               f'{selected_date.strftime("%Y年%m月%d日")} は土曜休業日のため、利用者の記録画面へは遷移できません。')
                return redirect("selfCare:calendar_list")

    #ユーザーの権限に応じてリダイレクト先を変更
    #利用者（user_role=1）
    if user.user_role == 1:
        try:
            home_screen_data = HomeScreen.objects.get(user=user, date=selected_date)
        except HomeScreen.DoesNotExist:
            home_screen_data = HomeScreen.objects.create(user=user, date=selected_date)
        return redirect("selfCare:input_screen", home_screen_id=home_screen_data.id)
    #スタッフ(user_role=2)もしくは管理者(user_role=3)
    elif user.user_role ==2 or user.user_role == 3:
        request.session['selected_date_for_user_list'] = selected_date.isoformat()
        user_list_url = reverse("selfCare:user_list")
        date_param = selected_date.isoformat()
        redirect_url = "{}?date={}".format(user_list_url, date_param)
        return redirect(redirect_url)
    return redirect("selfCare:calendar_list")

#詳細選択ビュー（コメント一覧に遷移するか入力画面に遷移するか）
class DetailSelectView(LoginRequiredMixin, View):
    def get(self, request, home_screen_id, *args, **kwargs):
        try:
            home_screen = HomeScreen.objects.get(id=home_screen_id, user=request.user)
            if request.user.user_role != 1:
                messages.error(request, "このページは利用者専用です。")
                return redirect("selfCare:calendar_list")

            context = {
                "home_screen": home_screen,
                "selected_date": home_screen.date,
            }
            return render(request, "detail_select.html", context)

        except HomeScreen.DoesNotExist:
            messages.error(request, '指定されたデータが見つかりませんでした。')
            return redirect("selfCare:calendar_list")

#スタッフ用詳細ビュー
class StaffDetailView(LoginRequiredMixin, View):
    def get(self, request, user_id, selected_date_str=None, *args, **kwargs):
        selected_user =  User.objects.get(id=user_id)

        # URLから日付を取得し、それがなければ今日の日付を使用
        if selected_date_str:
            # ISOフォーマットの文字列を date オブジェクトに変換
            selected_date = date.fromisoformat(selected_date_str)
        else:
            # 日付情報がなければ、今日の日付を使用（フォールバック）
            selected_date = date.today()

        try:
            #today ではなく selected_date を使用
            home_screen_data = HomeScreen.objects.get(user=selected_user, date=selected_date)
        except HomeScreen.DoesNotExist:
            #today ではなく selected_date を使用
            home_screen_data = HomeScreen.objects.create(user=selected_user, date=selected_date)

        return  redirect("selfCare:input_screen", home_screen_id=home_screen_data.id)

# 管理者用画面（特定のユーザーが選択された状態で管理者メニューを表示）
class AdminDetailView(LoginRequiredMixin, View):
    def get(self, request, user_id=None, *args, **kwargs):
        target_user = None
        if user_id is not None:
            try:
                target_user = User.objects.get(id=user_id)
                request.session['target_user_id'] = user_id
            except User.DoesNotExist:
                messages.error(request, '対象ユーザーが見つかりませんでした。')
                return redirect('selfCare:user_list')
        else:
            # user_id がない場合はセッションをクリア
            if 'target_user_id' in request.session:
                del request.session['target_user_id']
            if 'target_action' in request.session:
                del request.session['target_action']

        # リダイレクトせず、直接管理者画面テンプレートをレンダリングする
        context = {
            'user': request.user,
            'target_user': target_user,
            'title': '管理者メニュー'
        }
        return render(request, 'admin_screen.html', context)

#管理者認証ビュー
class AdminScreenView(LoginRequiredMixin, View):
    # URLパターンに合わせて action を受け取るように修正
    def get(self, request, user_id=None, action=None, *args, **kwargs):
        #admin_auth_action URLでのアクセスの場合の処理
        # user_id と action が両方あり、リダイレクト先から戻ってきたと判断できる場合
        if user_id is not None and action in ['edit', 'delete']:
            try:
                target_user = User.objects.get(id=user_id)
                request.session['target_user_id'] = user_id
                request.session['target_action'] = action

                # 認証フォームをレンダリングしてループを停止する
                form = AuthForm()
                context = {
                    'target_user': target_user,
                    'action': action,
                    'form': form,
                    'title': '管理者認証'  # 適切なタイトルを設定
                }
                return render(request, 'admin_auth.html', context)
            except User.DoesNotExist:
                messages.error(request, '指定されたユーザーが見つかりませんでした。')
                return redirect('selfCare:user_list')

        #admin_screen_action URLでのアクセスの場合の処理
        # user_id があり、action が 'edit' または 'delete' の場合
        if user_id is not None:
            try:
                target_user = User.objects.get(id=user_id)
                request.session['target_user_id'] = user_id

                if action in ['edit', 'delete']:
                    request.session['target_action'] = action
                    # アクションが指定されたら、直ちにアクション付き認証画面にリダイレクト
                    return redirect("selfCare:admin_auth_action", user_id=user_id, action=action)

                # action が指定されていない場合
                else:
                    # action 選択画面 (admin_screen.html) をレンダリング
                    context = {
                        'target_user': target_user,
                        'action': action,
                    }
                    # セッションに以前のアクションが残っている場合は削除
                    if 'target_action' in request.session:
                        del request.session['target_action']

                    return render(request, 'admin_screen.html', context)
            except User.DoesNotExist:
                messages.error(request, '指定されたユーザーが見つかりませんでした。')
                return redirect('selfCare:user_list')

        #admin_auth URLでのアクセスの場合の処理 (user_idがNone)
        # 新規作成のための管理者認証の場合
        if user_id is None and request.path == '/admin_auth/':
            # セッションから target_user_id と target_action を削除 (新規作成のため)
            if 'target_user_id' in request.session:
                del request.session['target_user_id']
            if 'target_action' in request.session:
                del request.session['target_action']

            form = AuthForm()
            return render(request, 'admin_auth.html', {'form': form, 'title': '管理者認証'})

        # admin_screen URLでのアクセスでuser_idがない場合（管理者ログイン直後）
        if user_id is None:
            # セッションに残っている可能性のある target_user_id と target_action を削除
            if 'target_user_id' in request.session:
                del request.session['target_user_id']
            if 'target_action' in request.session:
                del request.session['target_action']

            # 管理者メイン画面をレンダリング
            context = {
                'user': request.user,
                'title': '管理者メニュー'
            }
            return render(request, 'admin_screen.html', context)
        # 上記のどのパターンにも当てはまらない場合（安全のため）
        return redirect('selfCare:admin_screen')

    def post(self, request, user_id=None, action=None, *args, **kwargs):
        # セッションから編集対象のユーザーIDとアクションを取得
        session_user_id = request.session.get('target_user_id')
        target_action = request.session.get('target_action') # ← action をセッションから取得
        form = AuthForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            # ユーザー認証
            user = authenticate(request, email=email, password=password)  # 修正箇所
            # ... 管理者認証ロジック ...

            if user is not None and user.is_authenticated and user.user_role == 3:
                if session_user_id:
                    # アクションに応じてリダイレクト先を振り分ける
                    if target_action == 'delete':
                        return redirect("selfCare:user_delete_auth", user_id=session_user_id) # 削除認証へ
                    else:
                        # 'edit' または action がない場合は編集認証へ
                        return redirect("selfCare:user_edit_auth", user_id=session_user_id) # 編集認証へ
                else:
                    return redirect("selfCare:user_create_screen")
            else:
                return render(request, 'admin_auth.html',{'form': form, 'error_message': '管理者としての認証に失敗しました。'})

        return render(request, 'admin_auth.html', {'form': form, 'error_message': '入力に誤りがあります。'})

#編集対象者認証ビュー
class UserAuthView(LoginRequiredMixin, View):
    def get(self, request, user_id, action=None, *args, **kwargs):
        form = UserOnlyAuthForm()
        # テンプレートに渡す対象ユーザーの情報を取得
        try:
            target_user = User.objects.get(id=user_id)
            if action == 'delete':
                title = f"{target_user.user_name}さんの削除認証"
            else:
                # 'edit' または None の場合
                title = f"{target_user.user_name}さんの編集認証"
        except User.DoesNotExist:
            messages.error(request, '対象ユーザーが見つかりませんでした。')
            return redirect('selfCare:user_list')
        context = {
            'form': form,
            'target_user': target_user,
            'action': action,  # POSTメソッドでも使用するため
            'title': title,  # GETメソッドで作成した title
        }
        return render(request, 'user_auth.html', context)

    def post(self, request, user_id, action=None, *args, **kwargs):
        # action_value の取得をフォームの隠しフィールドから、またはURLパラメータから取得
        action_value = request.POST.get('action', action)
        form = UserOnlyAuthForm(request.POST)

        # フォームが無効の場合にも title が必要
        if form.is_valid():
            email = form.cleaned_data.get("email")

            try:
                # 編集対象ユーザーの認証情報を検証

                target_user = User.objects.get(id=user_id)

                if target_user.email == email:
                    # 認証成功。actionの値に基づいてリダイレクト先を決定
                    if action_value == 'delete':
                        return redirect("selfCare:user_delete_confirm", user_id=user_id)  # 削除確認画面へ
                    else:
                        return redirect("selfCare:edit_screen", user_id=user_id)  # 編集画面へ
                else:
                    # 認証失敗時の処理
                    title = f"{target_user.user_name}さんの編集認証"
                    messages.error(request, 'メールアドレスが間違っています。')
                    context = {
                        'form': form,
                        'error_message': 'メールアドレスが間違っています。',
                        'action': action_value,
                        'target_user': target_user,
                        'title': title
                    }
                    return render(request, 'user_auth.html', context)
            except User.DoesNotExist:
                messages.error(request, '対象ユーザーが見つかりませんでした。')
                return redirect('selfCare:user_list')
        # フォームが無効だった場合や認証失敗時の処理を堅牢に
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, '対象ユーザーが見つかりませんでした。')
            return redirect('selfCare:user_list')

        if action_value == 'delete':
            title = f"{target_user.user_name}さんの削除認証"
        else:
            title = f"{target_user.user_name}さんの編集認証"

        context = {
            'form': form,
            'error_message': '入力に誤りがあります。',  # フォームエラー時のメッセージ
            'action': action_value,
            'target_user': target_user,
            'title': title,
        }
        return render(request, 'user_auth.html', context)

#編集画面ビュー
class EditScreenView(LoginRequiredMixin, View):
    def get(self, request, user_id, *args, **kwargs):
        # 管理者(user_role=3)であるか確認
        if request.user.user_role != 3:
            messages.error(request, "この操作を行う権限がありません。")
            return redirect("selfCare:user_list")
        try:
            target_user = User.objects.get(id=user_id)

            # 【追加】セッションに一時保存された編集データがあれば取得してフォームに反映する
            edit_data = request.session.get("edit_data")
            if edit_data and edit_data.get("id") == int(user_id):
                form = UserEditForm(initial={
                    "email": edit_data.get("email"),
                    "user_name": edit_data.get("user_name"),
                })
            else:
                form = UserEditForm(instance=target_user)

            context = {
                "form": form,
                "target_user": target_user,
            }
            return render(request, "edit_screen.html", context)
        except User.DoesNotExist:
            messages.error(target_user, "対象ユーザーが見つかりませんでした。")  # 修正 or そのまま
            return redirect("selfCare:user_list")

    def post(self, request, user_id, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, "この操作を行う権限がありません。")
            return redirect("selfCare:user_list")

        try:

            target_user = User.objects.get(id=user_id)
            form = UserEditForm(request.POST, instance=target_user)
            if form.is_valid():
                #セッションに編集内容を一時保存
                edit_data = {
                    "id": user_id,
                    "email": form.cleaned_data.get("email"),
                    "user_name": form.cleaned_data.get("user_name"),
                }
                #パスワードが入力されていれば追加
                password = form.cleaned_data.get("password")
                if password:
                    edit_data["password"] = password
                request.session["edit_data"] = edit_data
                #確認画面へリダイレクト
                return redirect("selfCare:edit_confirm",  user_id=user_id)
            else:
                context = {
                    "form": form,
                    "target_user": target_user,
                }
                return render(request, 'edit_screen.html', context)
        except User.DoesNotExist:
            messages.error(request, '対象ユーザーが見つかりませんでした。')
            return redirect('selfCare:user_list')


#編集確認画面ビュー
class EditConfirmView(LoginRequiredMixin, View):
    def get(self, request, user_id, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, "この操作を行う権限がありません。")
            return redirect("selfCare:user_list")

        edit_data = request.session.get("edit_data")
        if not edit_data:
            messages.error(request, "編集データが存在しませんでした")
            return redirect("selfCare:edit_screen", user_id=user_id)
        try:
            target_user = User.objects.get(id=user_id)
            context = {
                "target_user": target_user,
                "edit_data": edit_data,
            }
            return render(request, "edit_confirm.html", context)
        except User.DoesNotExist:
            messages.error(request, '対象ユーザーが見つかりませんでした。')
            return redirect('selfCare:user_list')

    def post(self, request, user_id, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, 'この操作を行う権限がありません。')
            return redirect('selfCare:user_list')
        # 'action'という名前のボタンが押されたかどうかを確認
        action = request.POST.get("action")

        if action == "confirm":
            # ユーザー情報の更新処理へリダイレクト
            return redirect('selfCare:edit_user', user_id=user_id)
        elif action == 'back':
            # 編集画面に戻る
            return redirect('selfCare:edit_screen', user_id=user_id)


# 編集処理ビュー
class EditView(LoginRequiredMixin, View):
    def get(self, request, user_id, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, 'この操作を行う権限がありません。')
            return redirect('selfCare:user_list')

        edit_data = request.session.get("edit_data")
        if not edit_data:
            messages.error(request, '編集データが見つかりませんでした。')
            return redirect('selfCare:user_list')
        try:
            target_user = User.objects.get(id=user_id)

            # データ更新
            target_user.email = edit_data["email"]
            target_user.user_name = edit_data["user_name"]

            # パスワードが入力されていれば更新
            if "password" in edit_data and edit_data["password"]:
                target_user.password = make_password(edit_data['password'])
            target_user.save()

            # セッションから編集データおよびターゲット情報を削除
            if "edit_data" in request.session:
                del request.session["edit_data"]
            if "target_action" in request.session:
                del request.session["target_action"]
            if "target_user_id" in request.session:
                del request.session["target_user_id"]

            messages.success(request, "user情報が正常に編集されました")
            return redirect('selfCare:edit_complete')
        except User.DoesNotExist:
            messages.error(request, '対象ユーザーが見つかりませんでした。')
            return redirect('selfCare:user_list')

#編集完了ビュー
class EditCompleteView(LoginRequiredMixin, TemplateView):
    template_name = "edit_complete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        messages.success(self.request, "ユーザー情報が正常に更新されました。")
        return context

#新規作成画面ビュー
class CreateScreenView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, 'この操作を行う権限がありません。')
            return redirect('selfCare:user_list')

        # セッションに一時保存された作成データがあれば取得
        create_data = request.session.get("create_data")
        initial = {}
        if create_data:
            initial = {
                "email": create_data.get("email"),
                "user_name": create_data.get("user_name"),
                "user_role": create_data.get("user_role"),
                "password": create_data.get("password"),
                "password_confirm": create_data.get("password"),  # 確認用パスワードにも引き継ぐ
            }

        form = UserCreateForm(initial=initial)
        context = {
            "form": form,
        }
        return render(request, "create.html", context)

    def post(self, request, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, 'この操作を行う権限がありません。')
            return redirect('selfCare:user_list')

        form = UserCreateForm(request.POST)
        if form.is_valid():
            # セッションに新規作成内容を一時保存
            create_data = {
                "email": form.cleaned_data.get("email"),
                "user_name": form.cleaned_data.get("user_name"),
                "password": form.cleaned_data.get("password"),
                "user_role": form.cleaned_data.get("user_role"),
            }
            request.session["create_data"] = create_data
            # 確認画面へリダイレクト
            return redirect("selfCare:user_create_confirm")
        else:
            context = {
                "form": form,
            }
            # フォームが無効な場合は、エラーメッセージとともに再表示
            return render(request, "create.html", context)

#user新規作成内容確認ビュー
class CreateConfirmView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, 'この操作を行う権限がありません。')
            return redirect('selfCare:user_list')
        create_data = request.session.get("create_data")
        if not create_data:
            messages.error(request, "作成データが存在しません。")
            return redirect("selfCare:user_create_screen")
        context = {
            "create_data": create_data,
        }
        return render(request, "create_confirm.html", context)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "confirm":
            return redirect("selfCare:user_create")
        elif action == "back":
            return redirect("selfCare:user_create_screen")

#user新規作成ビュー
class CreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, 'この操作を行う権限がありません。')
            return redirect('selfCare:user_list')
        create_data = request.session.get("create_data")
        if not create_data:
            messages.error(request, "作成データが見つかりませんでした。")
            return redirect('selfCare:user_list')
        try:
            #パスワードをハッシュ化
            hashed_password = make_password(create_data["password"])
            #is_staffフラグを設定
            # user_roleがスタッフ権限の場合にis_staffをTrueにする
            is_staff_flag = create_data["user_role"] == 2
            #ユーザーを作成
            User.objects.create(
                username=create_data["email"],
                email=create_data["email"],
                user_name=create_data["user_name"],
                password=hashed_password,
                user_role=create_data["user_role"],
                is_staff = is_staff_flag  # is_staffを設定
            )
            #セッションから作成データを削除
            if "create_data" in request.session:
                del request.session["create_data"]
            messages.success(request, "ユーザーが正常に作成されました。")
            return redirect('selfCare:user_create_complete')
        except Exception as e:
            messages.error(request, f'ユーザーの作成中にエラーが発生しました: {e}')
            return redirect('selfCare:user_list')

# ユーザー新規作成完了ビュー
class CreateCompleteView(LoginRequiredMixin, TemplateView):
    template_name = "create_complete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        messages.success(self.request, "ユーザー情報が正常に更新されました。")
        return context

#ユーザー削除確認ビュー
class DeleteConfirmView(LoginRequiredMixin, View):
    def get(self, request, user_id, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, 'この操作を行う権限がありません。')
            return redirect('selfCare:user_list')
        try:
            target_user = User.objects.get(id=user_id)
            context = {
                "target_user": target_user,
            }
            return render(request, "delete_confirm.html", context)
        except User.DoesNotExist:
            messages.error(request, '対象ユーザーが見つかりませんでした。')
            return redirect('selfCare:user_list')

    def post(self, request, user_id, *args, **kwargs):
        action = request.POST.get("action")
        if action == "confirm":
            return redirect("selfCare:user_delete", user_id=user_id)
        elif action == "back":
            return redirect("selfCare:user_list")

# ユーザー削除ビュー
class DeleteView(LoginRequiredMixin, View):
    def get(self, request, user_id, *args, **kwargs):
        if request.user.user_role != 3:
            messages.error(request, 'This operation is not permitted.') # 権限エラーメッセージ
            return redirect('selfCare:user_list')
        try:
            target_user = User.objects.get(id=user_id)
            target_user.delete()

            # セッションからターゲット情報を削除
            if "target_action" in request.session:
                del request.session["target_action"]
            if "target_user_id" in request.session:
                del request.session["target_user_id"]

            messages.success(request, 'ユーザーが正常に削除されました。')
            return redirect('selfCare:user_delete_complete')
        except User.DoesNotExist:
            messages.error(request, '対象ユーザーが見つかりませんでした。')
            return redirect('selfCare:user_list')

# ユーザー削除完了ビュー
class DeleteCompleteView(LoginRequiredMixin, TemplateView):
    template_name = "delete_complete.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

#過去１ヶ月の睡眠時間・体調のデータを取得しグラフをPNG画像データとして返す関数
# 過去１ヶ月の睡眠時間・体調のデータを取得しグラフをPNG画像データとして返す関数
def create_chart_image(user, home_screen, data_field, title, y_label, condition_map=None, is_staff=False,
                       completion_date=None):
    import matplotlib
    matplotlib.use('Agg')  # GUIを使わないバックエンドを強制
    import matplotlib.pyplot as plt

    # 既存のプロットを完全にクリアしてメモリリークや循環参照を防ぐ
    plt.close('all')

    # 登録完了日が指定されていればそれを使用
    if completion_date:
        end_date = completion_date
        start_date = end_date - timedelta(days=30)
    else:
        end_date = home_screen.date
        start_date = end_date - timedelta(days=30)

    # 1. 過去31日間の全ての日付のリストを生成
    all_dates = [start_date + timedelta(days=i) for i in range(31)]

    # 2. データベースからプリミティブな値（辞書形式）でデータを取得し、モデルインスタンスの巻き込みを防止する
    raw_data = list(
        InputScreen.objects.filter(
            user=user,
            date__date__range=[start_date, end_date]
        ).values('date__date', data_field)
    )

    # データを日付をキーとする辞書に変換
    data_map = {item['date__date']: item[data_field] for item in raw_data if item['date__date'] is not None}

    # 3. 表示用のリストを作成
    dates_labels = []
    values = []

    for current_date in all_dates:
        dates_labels.append(current_date.strftime("%m/%d"))
        value = data_map.get(current_date, None)
        values.append(value)

    # 全てのデータが None の場合はグラフを描画しない
    if all(v is None for v in values):
        return None

    # 体調の場合、文字列を数値にマッピング
    if condition_map:
        values = [condition_map.get(v, None) if v is not None else None for v in values]

    # フィギュアとアックスを明示的に作成（オブジェクト指向スタイルで循環参照を回避）
    fig, ax = plt.subplots(figsize=(8, 10) if is_staff else (15, 9))

    if data_field == "sleep_time_hours":
        valid_indices = []
        valid_values = []
        for i, value in enumerate(values):
            if value is not None:
                valid_indices.append(i)
                valid_values.append(value)

        if completion_date:
            actual_days = (end_date - start_date).days
            ax.set_xlim(0, actual_days)
        else:
            ax.set_xlim(0, 30)

        if valid_values:
            linewidth_val = 2 if is_staff else 5
            ax.plot(valid_indices, valid_values, marker="o", linestyle="-", color="lightblue", markersize=10,
                    linewidth=linewidth_val)
        else:
            ax.text(0.5, 0.5, 'データがありません', ha='center', va='center', fontsize=16, transform=ax.transAxes)

        ax.set_ylim(0, 20)
        ax.set_yticks(range(0, 21, 5))
    else:
        ax.plot(dates_labels, values, marker="o", linestyle="", markersize=10, color="tomato")
        ax.set_yticks([1, 2, 3])
        ax.set_yticklabels(["✕（悪化）", "△（注意）", "〇（良好）"])
        ax.set_ylim(0.5, 3.5)

    title_fontsize = 20 if is_staff else 30
    label_fontsize = 20 if is_staff else 25
    tick_fontsize = 20 if is_staff else 40

    ax.set_title(title, fontsize=title_fontsize, pad=20)
    ax.set_xlabel("日付", fontsize=label_fontsize, labelpad=10)

    if data_field == "sleep_time_hours":
        ax.set_ylabel("睡眠時間", fontsize=label_fontsize, labelpad=10)
    else:
        ax.set_ylabel("体調", fontsize=label_fontsize, labelpad=10)

    tick_interval = 4
    ax.set_xticks(range(0, len(dates_labels), tick_interval))
    ax.set_xticklabels(dates_labels[::tick_interval], rotation=45, ha="right", fontsize=tick_fontsize)
    ax.tick_params(axis='y', labelsize=tick_fontsize)

    ax.grid(axis='y', linestyle='--')
    fig.tight_layout()
    fig.subplots_adjust(left=0.15)

    # グラフをPNGとしてメモリ上に保存し、Base64エンコードして返す
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)  # 明示的にフィギュアを閉じてメモリと参照を解放
    buffer.seek(0)
    png_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
    buffer.close()

    return 'data:image/png;base64,{}'.format(png_image)

# 新しく追加: 棒グラフをPNG画像データとして返す関数
def create_bar_chart_image(labels, data, title, y_label, color="skyblue", is_staff=False):
    """
    棒グラフを生成し、Base64エンコードされたPNG画像URIを返す。

    :param labels: 横軸のラベルのリスト (例: ['2025年10月', '2025年11月'])
    :param data: 棒グラフの値のリスト (例: [7.5, 6.8])
    :param title: グラフのタイトル
    :param y_label: 縦軸のラベル
    :param color: 棒の色
    :return: Base64エンコードされたPNG画像URI文字列、またはデータがない場合は None
    """
    if not data or all(d is None for d in data):
        return None

    plt.switch_backend("agg")
    # スタッフの場合はグラフ幅を狭める
    if is_staff:
        plt.figure(figsize=(10, 6))
    else:
        plt.figure(figsize=(16, 6))

    # 棒グラフの描画
    # x軸の位置をインデックスで指定し、ラベルをxticksで設定
    x_pos = range(len(labels))
    plt.bar(x_pos, data, color=color)

    # 棒の上に値を表示 (例: 7.5h)
    for i, v in enumerate(data):
        if v is not None:
            # y座標 v, x座標 i
            plt.text(i, v + 0.1, f'{v}h', ha='center', va='bottom', fontsize=11)

    # x軸のラベルを設定
    plt.xticks(x_pos, labels, rotation=0)

    plt.title(title, fontsize=14, pad=20)
    plt.xlabel("測定期間")
    plt.ylabel(y_label, fontsize=10, labelpad=10)

    # 縦軸の範囲を設定 (最小値は0、最大値はデータの最大値+α)
    max_val = max([d for d in data if d is not None] + [0]) # データがない場合は0
    plt.ylim(0, max_val * 1.2 or 10) # データの最大値の1.2倍、または最低10時間まで

    plt.grid(axis='both', linestyle='--', alpha=0.7)
    plt.tight_layout()

    #グラフをPNGとしてメモリ上に保存し、Base64エンコードして返す
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    plt.close() #グラフを閉じてメモリを解放
    png_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
    buffer.close()
    return 'data:image/png;base64,{}'.format(png_image)

# 特定の月の平均睡眠時間を計算する関数
def calculate_monthly_average_sleep(user, target_date):
    #月の最終日ではない場合は計算しない
    last_day_of_month = calendar.monthrange(target_date.year, target_date.month)[1]
    if target_date.day != last_day_of_month:
        return None  # 月の最終日ではない場合は None を返す

    # 月の開始日と終了日を計算
    start_of_month = date(target_date.year, target_date.month, 1)
    end_of_month = date(target_date.year, target_date.month, last_day_of_month)

    # 該当月の InputScreen データを取得
    monthly_data = InputScreen.objects.filter(
        user=user,
        date__date__range=[start_of_month, end_of_month],
        sleep_time_hours__isnull=False # 睡眠時間が入力されているもののみを対象
    )

    # データがない場合は None を返す
    if not monthly_data.exists():
        return None

    # 平均睡眠時間を計算
    # F() 式を使用して、クエリセットの合計値を計算
    total_sleep_time = monthly_data.aggregate(total_sleep=Sum('sleep_time_hours'))['total_sleep']
    count = monthly_data.count()

    if count > 0:
        # 平均を計算し、小数点以下第1位に丸める
        average_sleep = round(total_sleep_time / count, 1)
        return average_sleep
    else:
        return None


# 過去３ヶ月の平均睡眠時間を棒グラフで表示する関数
# 特定の月の平均睡眠時間とグラフ描画用のデータを取得する関数
def create_monthly_average_sleep_chart(user, end_date):
    # 1. 過去3ヶ月分の平均睡眠時間を計算
    dates_labels = []  # 横軸のラベル（月名）
    values = []  # 縦軸の値（平均値）

    # 今日が月の最終日かどうかをチェック
    today_last_day = calendar.monthrange(end_date.year, end_date.month)[1]
    if end_date.day != today_last_day:
        # 月の最終日ではない場合は空のデータを返す
        return None, "", None, [], []

    # 過去3ヶ月分のデータを取得（現在の月と2ヶ月前まで）
    for i in range(2, -1, -1):  # 0: 当月, 1: 1ヶ月前, 2: 2ヶ月前
        target_date = end_date

        # iヶ月前の日付を計算
        if i == 1:
            # 1ヶ月前
            if target_date.month == 1:
                target_date = date(target_date.year - 1, 12, 1)
            else:
                target_date = date(target_date.year, target_date.month - 1, 1)
        elif i == 2:
            # 2ヶ月前
            if target_date.month <= 2:
                target_date = date(target_date.year - 1, target_date.month + 10, 1)
            else:
                target_date = date(target_date.year, target_date.month - 2, 1)

        # 各月の最終日を取得して平均睡眠時間を計算
        last_day_of_month = calendar.monthrange(target_date.year, target_date.month)[1]
        month_end_date = date(target_date.year, target_date.month, last_day_of_month)

        monthly_average = calculate_monthly_average_sleep(user, month_end_date)

        if monthly_average is not None:
            dates_labels.append(target_date.strftime("%Y年%m月"))
            values.append(monthly_average)

    # グラフタイトルを3ヶ月分に変更
    chart_title = "過去3ヶ月の平均睡眠時間"

    # 全体の平均睡眠時間（最新の月の値を使用）
    overall_average_sleep_time = values[-1] if values else None

    # グラフ画像（None）、グラフタイトル、平均睡眠時間、ラベル、値を返す
    return None, chart_title, overall_average_sleep_time, dates_labels, values

#グラフ表示ビュー
class ChartView(LoginRequiredMixin, View):
    def get(self, request, home_screen_id, chart_type, *args, **kwargs):
        try:
            home_screen = HomeScreen.objects.get(id=home_screen_id)
            user_for_chart = home_screen.user

            # 体調を数値とマッピング
            CONDITION_MAP = {
                "✕": 1, #悪化
                "△": 2, #注意
                "〇": 3 #良好
            }

            chart_image = None
            title = ""
            y_label = ""

            # ログインユーザーの権限を確認（スタッフの場合のみグラフ幅を狭める）
            is_staff = request.user.user_role == 2

            if chart_type == "sleep":
                # 睡眠時間グラフの作成
                chart_image = create_chart_image(
                    user=user_for_chart,
                    home_screen=home_screen,
                    data_field="sleep_time_hours",
                    title="過去３０日間の睡眠時間の推移",
                    y_label="睡眠時間 (時間)",
                    is_staff=is_staff
                )
                title = "睡眠時間グラフ"

            elif chart_type == "condition":
                # 体調グラフの生成
                chart_image = create_chart_image(
                    user=user_for_chart,
                    home_screen=home_screen,
                    data_field="condition",
                    title="過去30日間の体調の推移",
                    y_label="体調",
                    condition_map=CONDITION_MAP,
                    is_staff=is_staff
                )
                title = "体調グラフ"



            elif chart_type == "monthly_average_sleep":

                # 平均睡眠時間のグラフを生成

                chart_image, chart_title, _, dates_labels, values = create_monthly_average_sleep_chart(

                    user=user_for_chart,

                    end_date=home_screen.date

                )

                # create_monthly_average_sleep_chartでタイトルは設定されているため、そのまま使用

                title = chart_title if chart_title else "月間平均睡眠時間グラフ"
                if values:  # 平均データが存在する場合のみグラフを生成

                    chart_image = create_bar_chart_image(
                        labels=dates_labels,
                        data=values,
                        title=chart_title,  # chart_title を使用
                        y_label="平均睡眠時間（時間）",
                        color="teal",  # 棒グラフの色を少し変えてみました
                        is_staff=is_staff
                    )

            else:
                messages.error(request, '無効なグラフタイプが指定されました。')
                return redirect("selfCare:calendar_list")

            if chart_image is None:
                # ...
                return redirect("selfCare:calendar_list")



            context = {
                "chart_image": chart_image,
                "title": title,
                "selected_date": home_screen.date,

            }
            # 新しいテンプレート 'chart_detail.html' にレンダリング
            return render(request, "chart_detail.html", context)

        except HomeScreen.DoesNotExist:
            messages.error(request, '指定されたホーム画面データが見つかりませんでした。')
            return redirect("selfCare:calendar_list")

#入力画面ビュー
class InputScreenView(LoginRequiredMixin, View):
    def get(self, request, home_screen_id, *args, **kwargs):
        try:
            home_screen = HomeScreen.objects.get(id=home_screen_id)
            selected_date = home_screen.date

            target_user = home_screen.user

            input_screen_data, created = InputScreen.objects.get_or_create(
                user=target_user,
                date=home_screen  # dateフィールドはHomeScreenを参照しているため
            )

            initial_data = {}
            # データベースの at_home の値をフォームの初期値として設定
            if input_screen_data.at_home is not None:
                initial_data['at_home'] = input_screen_data.at_home

            # フォームをインスタンスとinitialデータで初期化
            form = InputScreenForm(
                instance=input_screen_data,
                initial=initial_data,
                user=request.user
            )

            # ログインユーザーの権限を取得
            user_role = request.user.user_role

            leaving_time_display = input_screen_data.leaving_time

            # TimeField のデータを HH:MM 形式にフォーマット (利用者入力)
            entry_time_display = ""
            #まずスタッフ入力の時刻をチェックし、存在すれば表示用として使用する
            if input_screen_data.staff_entry_time:
                entry_time_display = input_screen_data.staff_entry_time.strftime("%H:%M")

            #修正: スタッフ時刻がない場合のみ、利用者入力の時刻を参照する
            elif input_screen_data.entry_time:
                entry_time_display = input_screen_data.entry_time.strftime("%H:%M")



            leaving_time_display = ""
            #まずスタッフ入力の時刻をチェックし、存在すれば表示用として使用する
            if input_screen_data.staff_leaving_time:
                leaving_time_display = input_screen_data.staff_leaving_time.strftime("%H:%M")
            #スタッフ時刻がない場合のみ、利用者入力の時刻を参照する
            elif input_screen_data.leaving_time:
                leaving_time_display = input_screen_data.leaving_time.strftime("%H:%M")

            # スタッフ用入退出時刻の表示用変数 (スタッフ入力)
            staff_entry_time_display = ""
            if input_screen_data.staff_entry_time:
                staff_entry_time_display = input_screen_data.staff_entry_time.strftime("%H:%M")

            staff_leaving_time_display = ""
            if input_screen_data.staff_leaving_time:
                staff_leaving_time_display = input_screen_data.staff_leaving_time.strftime("%H:%M")



            # スタッフ用退出時刻の選択肢を生成 (10:00〜16:00 の15分刻み)
            time_choices = []
            for h in range(10, 17):  # 10時から16時まで
                for m in range(0, 60, 15):  # 0分, 15分, 30分, 45分
                    if h == 16 and m > 0:  # 16:15以降は含めない
                        continue
                    time_str = f"{h:02d}:{m:02d}"
                    time_choices.append(time_str)

            # staff_comment が None または空文字列の場合は「未入力」とする
            staff_comment_data = input_screen_data.staff_comment if input_screen_data.staff_comment else "未入力"

            # これが利用者が一度保存した在宅ステータスの真偽値
            at_home_status = input_screen_data.at_home

            # フォームフィールドの編集権限制御
            all_fields = form.fields.items()

            #フォームフィールドの編集権限制御
            all_fields = form.fields.items()

            for name, field in all_fields:
                if user_role == 1:  # 利用者の場合
                    # スタッフコメント、スタッフ入退出時刻は編集不可
                    if name == 'staff_comment' or name in ['staff_entry_time', 'staff_leaving_time']:
                        field.widget.attrs['disabled'] = 'disabled'
                        field.required = False

                    # 利用者入力フィールド（睡眠、体調、服薬、コメント、入退出時刻、at_home）は編集可能にする
                    else:
                        # disabled 属性が残存していれば、確実に削除する
                        if 'disabled' in field.widget.attrs:
                            del field.widget.attrs['disabled']
                        # readonly 属性が残存していれば、確実に削除する (念のため)
                        if 'readonly' in field.widget.attrs:
                            del field.widget.attrs['readonly']
                        field.required = False

                elif user_role == 2:  # スタッフの場合
                    # 在宅ステータスはスタッフからは変更不可
                    if name == 'at_home':
                        # 表示上も編集不可にする
                        field.widget.attrs['disabled'] = 'disabled'
                        field.required = False
                    # スタッフコメントは常に編集可能
                    elif name == 'staff_comment':
                        if 'disabled' in field.widget.attrs:
                            del field.widget.attrs['disabled']
                        if 'readonly' in field.widget.attrs:
                            del field.widget.attrs['readonly']
                        continue
                    elif name in ['entry_hour', 'entry_minute', 'leaving_time']:
                        field.widget.attrs['disabled'] = 'disabled'
                        field.required = False
                    elif name in ['sleep_time_hours', 'condition', 'medication_morning', 'medication_noon',
                                  'medication_night']:
                        field.widget.attrs['disabled'] = 'disabled'
                        field.required = False
                    if name in ['sleep_time_hours', 'condition']:
                        field.widget.attrs['readonly'] = 'readonly'
                    # または、テンプレートで `disabled` を維持し、hidden input で値を送信する戦略を選ぶ
                    # ただし、テンプレートで hidden input を追加する方がシンプルで強力です

                    # 在宅 (at_home_status == True) の場合
                    elif at_home_status:
                        # 利用者入力*の入室・退出時刻は編集不可 (非表示のためdisabledにする)
                        if name in ['entry_hour', 'entry_minute', 'leaving_time', 'user_comment']:
                            field.widget.attrs['disabled'] = 'disabled'
                        # *スタッフ入力*の入室・退出時刻は編集可能にする
                        elif name in ['staff_entry_time', 'staff_leaving_time',]:
                            # disabled、readonly属性が存在すれば、確実に削除
                            if 'disabled' in field.widget.attrs:
                                del field.widget.attrs['disabled']
                            if 'readonly' in field.widget.attrs:
                                del field.widget.attrs['readonly']
                            field.widget.attrs['disabled'] = False  # 明示的に無効を解除
                        if name in ['sleep_time_hours', 'condition']:
                            field.widget.attrs['readonly'] = 'readonly'
                        elif name in ['sleep_time_hours', 'condition', 'medication_morning', 'medication_noon',
                                      'medication_night']:
                            field.widget.attrs['disabled'] = 'disabled'
                            field.required = False

                        # その他（利用者入力フィールド、利用者コメント）は編集不可
                        else:
                            field.widget.attrs['disabled'] = 'disabled'
                            field.required = False

                    # スタッフかつ非在宅 (at_home_status == False または None) の場合
                    else:
                        # at_home, staff_comment, staff_entry_time, staff_leaving_time 以外の全てを編集不可
                        if name not in ['at_home', 'staff_comment', 'staff_entry_time', 'staff_leaving_time']:
                            field.widget.attrs['disabled'] = 'disabled'
                            field.required = False

            # ユーザーコメントはスタッフからは常に編集不可
            if user_role == 2:
                if 'user_comment' in form.fields:
                    form.fields['user_comment'].widget.attrs['disabled'] = 'disabled'
                    form.fields['user_comment'].required = False

            # モーダル表示制御用セッション管理
            # モーダル内容の最新状態を保持するセッション管理
            session_key = f'condition_modal_data_{home_screen_id}'

            # 利用者の場合、最新のモーダル内容をセッションから取得
            if request.user.user_role == 1:
                session_modal_data = request.session.get(session_key, {})

                # セッションに最新のモーダルデータがあれば、データベース値より優先
                if session_modal_data:
                    if session_modal_data.get('condition_detail_good') is not None:
                        input_screen_data.condition_detail_good = session_modal_data['condition_detail_good']
                    if session_modal_data.get('condition_detail_caution') is not None:
                        input_screen_data.condition_detail_caution = session_modal_data['condition_detail_caution']
                    if session_modal_data.get('condition_detail_poor') is not None:
                        input_screen_data.condition_detail_poor = session_modal_data['condition_detail_poor']

            # テンプレートで form.leaving_time_staff.value を使うため不要
            context = {
                'form': form,
                'selected_date': selected_date,
                'home_screen_id': home_screen_id,
                'home_screen': home_screen,
                "target_user_name": target_user.user_name,
                "entry_time_display": entry_time_display,
                "leaving_time_display": leaving_time_display,
                "staff_entry_time_display": staff_entry_time_display,
                "staff_leaving_time_display": staff_leaving_time_display,
                "staff_leaving_time_choices": time_choices,
                "staff_comment_data": staff_comment_data,
                "at_home_status": at_home_status,
                "user_role": user_role,
                "condition_detail_good": input_screen_data.condition_detail_good,
                "condition_detail_caution": input_screen_data.condition_detail_caution,
                "condition_detail_poor": input_screen_data.condition_detail_poor,
                "morning_work_content": input_screen_data.morning_work_content,
                "afternoon_work_content": input_screen_data.afternoon_work_content,
            }
            return render(request, 'input_screen.html', context)

        except HomeScreen.DoesNotExist:
            messages.error(request, '指定されたホーム画面データが見つかりませんでした。')
            return redirect("selfCare:calendar_list")

    # POST メソッド (データの保存処理)
        # POST メソッド (データの保存処理)
    def post(self, request, home_screen_id, *args, **kwargs):
        try:
            home_screen = HomeScreen.objects.get(id=home_screen_id)
            target_user = home_screen.user
        except HomeScreen.DoesNotExist:
            messages.error(request, '指定されたホーム画面データが見つかりませんでした。')
            return redirect("selfCare:calendar_list")

        input_screen_instance = InputScreen.objects.filter(date=home_screen, user=target_user).first()
        if not input_screen_instance:
            input_screen_instance = InputScreen(date=home_screen, user=target_user)

        user_role = request.user.user_role

        # 常に Django の標準フォームバリデーション（InputScreenForm.clean()）を通す
        form = InputScreenForm(request.POST, instance=input_screen_instance, user=request.user)

        if form.is_valid():
            # 正常保存処理
            if user_role == 1:
                selected_condition = form.cleaned_data.get('condition')
                session_modal_data = {}
                if selected_condition == '〇':
                    session_modal_data = {'condition_detail_good': form.cleaned_data.get('condition_detail_good'),
                                          'condition_detail_caution': '', 'condition_detail_poor': ''}
                    form.instance.condition_detail_caution = ''
                    form.instance.condition_detail_poor = ''
                elif selected_condition == '△':
                    session_modal_data = {'condition_detail_good': '',
                                          'condition_detail_caution': form.cleaned_data.get(
                                              'condition_detail_caution'),
                                          'condition_detail_poor': ''}
                    form.instance.condition_detail_good = ''
                    form.instance.condition_detail_poor = ''
                elif selected_condition == '✕':
                    session_modal_data = {'condition_detail_good': '', 'condition_detail_caution': '',
                                          'condition_detail_poor': form.cleaned_data.get('condition_detail_poor')}
                    form.instance.condition_detail_good = ''
                    form.instance.condition_detail_caution = ''
                request.session[f'condition_modal_data_{home_screen_id}'] = session_modal_data

                if input_screen_instance:
                    form.instance.staff_comment = input_screen_instance.staff_comment

            elif user_role == 2:
                if input_screen_instance:
                    form.instance.at_home = input_screen_instance.at_home
                    form.instance.medication_morning = input_screen_instance.medication_morning
                    form.instance.medication_noon = input_screen_instance.medication_noon
                    form.instance.medication_night = input_screen_instance.medication_night
                    form.instance.sleep_time_hours = input_screen_instance.sleep_time_hours
                    form.instance.condition = input_screen_instance.condition
                    form.instance.condition_detail_good = input_screen_instance.condition_detail_good
                    form.instance.condition_detail_caution = input_screen_instance.condition_detail_caution
                    form.instance.condition_detail_poor = input_screen_instance.condition_detail_poor
                    form.instance.entry_time = input_screen_instance.entry_time
                    form.instance.morning_work_content = input_screen_instance.morning_work_content
                    form.instance.afternoon_work_content = input_screen_instance.afternoon_work_content

            form.save()
            messages.success(request, f'{home_screen.date.strftime("%Y年%m月d日")} の記録を保存しました。')
            return redirect(reverse("selfCare:complete_screen", kwargs={'home_screen_id': home_screen_id}))

        else:
            # フォームが無効だった場合の再表示
            if user_role == 1:
                if 'staff_comment' in form.fields:
                    form.fields['staff_comment'].widget.attrs['readonly'] = 'readonly'
            elif user_role == 2:
                if 'user_comment' in form.fields:
                    form.fields['user_comment'].widget.attrs['disabled'] = 'disabled'

            current_at_home_status = 'at_home' in request.POST

            # フォームのエラーが確実にバインドされた状態のインスタンスをコンテキストに含める
            context = {
                'form': form,
                'at_home_status': current_at_home_status,
                'home_screen_id': home_screen_id,
                'selected_date': home_screen.date,
                'home_screen': home_screen,
                'target_user_name': target_user.user_name,
            }
            messages.error(request, '入力内容にエラーがあります。ご確認ください。')
            return render(request, "input_screen.html", context)

# 登録完了画面ビュー
class CompleteView(LoginRequiredMixin, View):
    def get(self, request, home_screen_id, *args, **kwargs):
        try:
            home_screen = HomeScreen.objects.get(id=home_screen_id)
            user_role = request.user.user_role  # ログインユーザーの権限を取得

            # グラフ生成は利用者（user_role=1）の場合のみ行う
            sleep_chart_image = None
            condition_chart_image = None

            # 利用者権限の場合、グラフを生成（有効化）
            if user_role == 1:
                CONDITION_MAP = {
                    "✕": 1,  # 悪化
                    "△": 2,  # 注意
                    "〇": 3  # 良好
                }

                chart_target_user = request.user
                completion_date = date.today()

                # 睡眠時間グラフの作成
                sleep_chart_image = create_chart_image(
                    user=chart_target_user,
                    home_screen=home_screen,
                    data_field="sleep_time_hours",
                    title="過去３０日間の睡眠時間の推移",
                    y_label="睡眠時間 (時間)",
                    completion_date=completion_date
                )

                # 体調グラフの生成
                condition_chart_image = create_chart_image(
                    user=chart_target_user,
                    home_screen=home_screen,
                    data_field="condition",
                    title="過去30日間の体調の推移",
                    y_label="体調",
                    condition_map=CONDITION_MAP,
                    completion_date=completion_date
                )

            context = {
                "home_screen_id": home_screen.id,  # モデル自体の代わりにIDを渡す
                "selected_date": home_screen.date,
                "user_role": user_role,  # 権限をテンプレートに渡す
                "sleep_chart_image": sleep_chart_image,
                "condition_chart_image": condition_chart_image,
            }
            # 新しいテンプレート 'complete_screen.html' にレンダリング
            return render(request, "complete_screen.html", context)

        except HomeScreen.DoesNotExist:
            messages.error(request, '指定されたホーム画面データが見つかりませんでした。')
            return redirect("selfCare:calendar_list")

#コメント一覧ビュー
class CommentListView(LoginRequiredMixin, View):
    def get(self, request, home_screen_id, *args, **kwargs):
        try:
            home_screen = HomeScreen.objects.get(id=home_screen_id)
            end_date = timezone.now().date()
            target_user = home_screen.user

            start_date = end_date - timedelta(days=29)#今日含めて３０日間

            #該当ユーザーのInputScreenデータを取得（日付範囲内）
            comment_data = InputScreen.objects.filter(
                user=target_user,
                date__date__range=[start_date, end_date]
            ).exclude(
                # コメントが両方とも空文字またはNULLの場合を除外
                user_comment__exact='',
                staff_comment__exact='',
            ).exclude(
                user_comment__isnull=True,
                staff_comment__isnull=True,
            ).order_by("date__date") # 新しい日付順にソート
            context = {
                "home_screen": home_screen,
                "selected_date": end_date,
                "comment_data": comment_data,
                "target_user": target_user,
            }
            # 新しいテンプレート 'comment_list.html' を作成してください
            return render(request, "comment_list.html", context)

        except HomeScreen.DoesNotExist:
            messages.error(request, '指定されたデータが見つかりませんでした。')
            return redirect("selfCare:calendar_list")


# 権限チェック関数 (ヘルパーとして定義することも可能ですが、ここでは各Viewに実装します)
def check_staff_permission(user):
    """ユーザーがスタッフ権限（is_staffまたはis_superuser）を持っているか確認する"""
    # ログイン済みチェックはLoginRequiredMixinで行われるため、ここではスタッフ権限のみをチェックします。
    return user.is_staff or user.is_superuser


# 土曜開所日設定の最初の選択画面
class SaturdayChoiceView(LoginRequiredMixin, TemplateView):
    template_name = 'saturday_choice.html'

    def dispatch(self, request, *args, **kwargs):
        # 権限チェックをif文で実行
        if not check_staff_permission(request.user):
            # スタッフ権限がない場合、メッセージを表示してカレンダー一覧にリダイレクト
            messages.error(request, '土曜開所日の設定にはスタッフ権限が必要です。')
            return redirect('selfCare:calendar_list')  # 権限がない場合はカレンダー一覧に遷移
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 既存のURL名が 'selfCare:calendar_list' であると仮定
        context['calendar_list_url'] = reverse('selfCare:calendar_list')
        context['register_url'] = reverse('selfCare:saturday_register')
        return context


# 土曜開所日登録画面と処理
class SaturdayOpeningRegisterView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        # 権限チェックをif文で実行
        if not check_staff_permission(request.user):
            # スタッフ権限がない場合、メッセージを表示してカレンダー一覧にリダイレクト
            messages.error(request, '土曜開所日の設定にはスタッフ権限が必要です。')
            return redirect('selfCare:calendar_list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = SaturdayOpeningForm()
        context = {
            'form': form
        }
        return render(request, 'saturday_register.html', context)

    def post(self, request, *args, **kwargs):
        form = SaturdayOpeningForm(request.POST)

        if form.is_valid():
            # フォームからバリデーション済みの日付リストを取得
            # clean_date_list メソッドが date オブジェクトのリストを返します
            dates_to_register = form.cleaned_data['date_list']
            registered_count = 0

            # 取得した日付リストをループして、それぞれをデータベースに保存
            for selected_date in dates_to_register:
                # SaturdayOpening インスタンスを作成し、スタッフを設定
                SaturdayOpening.objects.create(
                    open_date=selected_date,
                    registered_by=request.user
                )
                registered_count += 1

            messages.success(request, f"計 {registered_count} 件の土曜開所日を登録しました。")

            # 登録後にカレンダーリストに遷移
            return redirect('selfCare:saturday_complete')

        context = {
            'form': form
        }
        return render(request, 'saturday_register.html', context)


# 土曜開所日登録完了画面
class SaturdayOpeningCompleteView(LoginRequiredMixin, TemplateView):
    """
    土曜開所日の登録が完了したことを示すビュー。
    """
    template_name = 'saturday_complete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 完了メッセージや次のアクションへのリンクなどをコンテキストに追加
        context['message'] = "土曜開所日の登録が完了しました。"
        return context

# 土曜開所日一覧表示ビュー (削除対象選択用)
class SaturdayOpeningListView(LoginRequiredMixin, View):
    """
    登録済みの土曜開所日を一覧表示し、削除対象をチェックボックスで選択する。
    """
    template_name = 'saturday_list_delete.html' # 新しいテンプレート
    form_class = SaturdayOpeningDeleteForm # 後述のフォーム
    success_url = reverse_lazy('selfCare:saturday_delete_confirm') # 確認画面へのURLを仮定

    def dispatch(self, request, *args, **kwargs):
        # 権限チェック
        if not check_staff_permission(request.user):
            messages.error(request, '土曜開所日の削除にはスタッフ権限が必要です。')
            return redirect('selfCare:calendar_list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # 権限チェックはdispatchで行っているためここでは不要

        # 登録済みの土曜開所日を日付の新しい順に取得
        saturday_openings = SaturdayOpening.objects.all().order_by('-open_date')

        # フォームのインスタンスを作成
        form = self.form_class()

        context = {
            'saturday_openings': saturday_openings,
            'form': form,  # テンプレートでフォームのエラー表示などに使用
            'delete_url': self.success_url  # フォームの action に指定
        }

        # テンプレートをレンダリングして応答
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # フォームにPOSTデータをバインド
        form = self.form_class(data=request.POST)

        # フォームの検証
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_form_kwargs(self):
        # POSTの場合は、フォームで選択されたIDを受け取る
        kwargs = {'initial': None}
        if self.request.method == 'POST':
            kwargs.update({'data': self.request.POST})
        return kwargs

    def form_valid(self, form):
        # 選択されたIDをセッションに保存し、確認画面へリダイレクト
        selected_ids = form.cleaned_data.get('selected_openings')
        if not selected_ids:
            messages.error(self.request, '削除する土曜開所日を選択してください。')
            return self.form_invalid(form) # フォームの再表示

        self.request.session['delete_ids'] = selected_ids
        # 選択されたIDをセッションに保存（確認画面で使用）
        return redirect(self.success_url) # success_url へリダイレクト

    def form_invalid(self, form):
        # エラーメッセージをセットして再表示するために、get()と同じコンテキストを準備してレンダリング
        saturday_openings = SaturdayOpening.objects.all().order_by('-open_date')
        context = {
            'saturday_openings': saturday_openings,
            'form': form,  # エラー情報を含むフォーム
            'delete_url': self.success_url
        }
        messages.error(self.request, '削除対象の選択に問題があります。ご確認ください。')  # エラーメッセージも表示
        return render(self.request, self.template_name, context)


# 土曜開所日 削除確認・実行ビュー
class SaturdayOpeningDeleteConfirmView(LoginRequiredMixin, View):
    """
    削除対象の日付を表示し、確認後にデータベースから削除を実行する。
    """
    def dispatch(self, request, *args, **kwargs):
        # 権限チェック
        if not check_staff_permission(request.user):
            messages.error(request, '土曜開所日の削除にはスタッフ権限が必要です。')
            return redirect('selfCare:calendar_list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # セッションから削除対象のIDを取得
        delete_ids = request.session.get('delete_ids', [])

        if not delete_ids:
            # IDがない場合は一覧画面に戻す
            messages.error(request, '削除対象の日付が選択されていません。')
            return redirect('selfCare:saturday_list_delete')

        # 選択されたIDに対応するSaturdayOpeningオブジェクトを取得
        dates_to_delete = SaturdayOpening.objects.filter(id__in=delete_ids).order_by('open_date')

        context = {
            'dates_to_delete': dates_to_delete,
            'delete_count': len(dates_to_delete)
        }
        return render(request, 'saturday_delete_confirm.html', context) # 新しいテンプレート

    def post(self, request, *args, **kwargs):
        # セッションから削除対象のIDを取得
        delete_ids = request.session.pop('delete_ids', None) # 削除と同時にセッションから除去

        if not delete_ids:
            messages.error(request, '削除対象のデータが見つかりませんでした。再度選択してください。')
            return redirect('selfCare:saturday_list_delete')

        # 削除実行
        try:
            with transaction.atomic():
                # 選択されたIDに対応するSaturdayOpeningオブジェクトを取得し、削除
                delete_target_query = SaturdayOpening.objects.filter(id__in=delete_ids)
                deleted_count, _ = delete_target_query.delete()

                messages.success(request, f"計 {deleted_count} 件の土曜開所日を削除しました。")
                return redirect('selfCare:saturday_delete_complete') # 完了画面に遷移

        except Exception as e:
            messages.error(request, f"土曜開所日の削除中にエラーが発生しました: {e}")
            return redirect('selfCare:saturday_list_delete') # エラー時は一覧に戻す

class SaturdayOpeningDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "saturday_list_delete_complete.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context