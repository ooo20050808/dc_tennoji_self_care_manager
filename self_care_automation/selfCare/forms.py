from django import forms
from .models import User, InputScreen, SaturdayOpening
from datetime import datetime, timedelta, date
from datetime import time
from django.core.exceptions import ValidationError

#ログインフォーム
class LoginForm(forms.Form):
    email = forms.EmailField(label="メールアドレス")
    password = forms.CharField(label="パスワード", widget=forms.PasswordInput)

#認証フォーム
class AuthForm(forms.Form):
    email = forms.EmailField(label="メールアドレス")
    password = forms.CharField(label="パスワード", widget=forms.PasswordInput)

#利用者認証専用フォーム（メールアドレスのみ）
class UserOnlyAuthForm(forms.Form):
    email = forms.EmailField(label="メールアドレス")

#編集フォーム
class UserEditForm(forms.ModelForm):
    password = forms.CharField(label="新しいパスワード", required=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(label="新しいパスワード（確認）", required=False, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["email", "user_name"]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        # パスワードが入力された場合、両方が一致するか検証
        if password and password != password_confirm:
            self.add_error("password_confirm", "パスワードが一致しません")
        return cleaned_data

class UserCreateForm(forms.ModelForm):
    password = forms.CharField(label="パスワード", widget=forms.PasswordInput)
    password_confirm = forms.CharField(label="パスワード（確認）", widget=forms.PasswordInput)
    user_role = forms.IntegerField(label="ユーザー権限", min_value=1, max_value=3)
    class Meta:
        model = User
        fields = ("email", "user_name", "user_role")

    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError('パスワードが一致しません。')
        return password_confirm

# 15分刻みの時刻の選択肢を生成する関数
def generate_time_choices(start_hour, end_hour, interval_minutes):
    """
    指定された時間帯と間隔で HH:MM 形式の選択肢を生成します。
    """
    start_time = datetime.strptime(f'{start_hour:02d}:00', '%H:%M')
    end_time = datetime.strptime(f'{end_hour:02d}:00', '%H:%M')
    choices = [('', '---------')] # 最初の選択肢は空欄（未選択）
    current_time = start_time
    while current_time <= end_time:
        time_str = current_time.strftime('%H:%M')
        # (値, 表示名) のタプルを作成
        choices.append((time_str, time_str))
        current_time += timedelta(minutes=interval_minutes)
    return choices

# 退出時刻（leaving_time）の選択肢
LEAVING_TIME_CHOICES = generate_time_choices(10, 16, 15)

#入力フォーム
class InputScreenForm(forms.ModelForm):
    #体調の選択肢を定義
    CONDITION_CHOICES = [
        ("〇", "良好（○）"),
        ("△", "注意（△）"),
        ("✕", "悪化（✕）")
    ]

    #入出時刻
    entry_time = forms.ChoiceField(
		label="入室時刻",
		choices=LEAVING_TIME_CHOICES,
		required=False,
		widget=forms.Select(attrs={'class': 'time-input'})
	)

    #退出時刻１５分刻みの選択
    leaving_time = forms.ChoiceField(
        label="退出時刻",
        choices=LEAVING_TIME_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'time-input'})  # CSSクラスはそのまま利用
    )

    staff_entry_time = forms.TimeField(
        label="スタッフ入室時刻",
        widget=forms.TimeInput(attrs={'type': 'time'}),
        required=False  # 条件付き必須とするため
    )

    staff_leaving_time = forms.ChoiceField(
        label="スタッフ退出時刻",
        choices=LEAVING_TIME_CHOICES,
        required=False,  # 条件付き必須とするため
        widget=forms.Select(attrs={'class': 'time-input'})
    )

    #睡眠時間
    sleep_time_hours = forms.IntegerField(
        label="睡眠時間（時間）",
        min_value=0, #最小値を０時間に設定
        max_value=24, #最大値を２４時間に設定
        widget=forms.NumberInput(attrs={"min": 0, "max": 24}),
        required=False,
    )

    morning_work_content = forms.CharField(
        label="午前作業内容",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '午前の作業内容を入力...'})
    )

    afternoon_work_content = forms.CharField(
        label="午後作業内容",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '午後の作業内容を入力...'})
    )

    #体調（選択式）
    condition = forms.ChoiceField(
        label="体調",
        choices=CONDITION_CHOICES,
        widget=forms.Select(),
        required=False,
    )
    #体調詳細フィールド
    condition_detail_good = forms.CharField(
        label="体調詳細（良好）",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'condition-detail',
            'placeholder': '具体的な内容を入力...',
            'rows': 4,
        })
    )
    condition_detail_caution = forms.CharField(
        label="体調詳細（注意）",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'condition-detail',
            'placeholder': '具体的な症状や予兆を入力...',
            'rows': 4,
        })
    )
    condition_detail_poor = forms.CharField(
        label="体調詳細（悪化）",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'condition-detail',
            'placeholder': '具体的な症状や不調な点を入力...',
            'rows': 4,
        })
    )
    #在宅状況のチェックボックス
    at_home = forms.BooleanField(
        label = "在宅中",
        required=False,
        widget=forms.CheckboxInput()
    )

    medication_morning = forms.BooleanField(
        label="服薬（朝）",
        required=False,  # 必須ではない
        widget=forms.CheckboxInput()
    )

    medication_noon = forms.BooleanField(
        label="服薬（昼）",
        required=False,  # 必須ではない
        widget=forms.CheckboxInput()
    )

    medication_night = forms.BooleanField(
        label="服薬（夜）",
        required=False,  # 必須ではない
        widget=forms.CheckboxInput()
    )

    user_comment = forms.CharField(
        label="利用者コメント",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})  # 入力しやすいようにTextareaに変更
    )

    staff_comment = forms.CharField(
        label="スタッフコメント",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})  # 入力しやすいようにTextareaに変更
    )

    def __init__(self, *args, user=None, **kwargs):
        # Viewから渡されるユーザー情報を受け取る
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # ChoiceFieldに空の選択肢を挿入
        # models.pyで null=True が設定されているため、空文字を許容します。
        self.fields['entry_time'].choices = [('', '---------')] + list(self.fields['entry_time'].choices)
        self.fields['leaving_time'].choices = [('', '---------')] + list(self.fields['leaving_time'].choices)
        self.fields['condition'].choices = [('', '---------')] + list(self.fields['condition'].choices)
        self.user = user

    # entry_timeのバリデーション/クリーニング
    def clean_entry_time(self):
        """ChoiceField が空で送信された場合に None に 変換し、バリデーションエラーを回避する。"""
        entry_time = self.cleaned_data.get('entry_time')
        if entry_time is None or entry_time == '':
            return None
        # 文字列の時刻をdatetime.timeオブジェクトに変換
        from datetime import datetime
        try:
            return datetime.strptime(entry_time, '%H:%M').time()
        except ValueError:
            raise forms.ValidationError('無効な時刻形式です。')

    # leaving_timeのバリデーション/クリーニング
    def clean_leaving_time(self):
        leaving_time = self.cleaned_data.get('leaving_time')
        # 空文字列またはNoneの場合、None（DBのNULLに対応）を返す
        if leaving_time is None or leaving_time == '':
            return None
        # 文字列の時刻をdatetime.timeオブジェクトに変換
        from datetime import datetime
        try:
            return datetime.strptime(leaving_time, '%H:%M').time()
        except ValueError:
            raise forms.ValidationError('無効な時刻形式です。')

    #スタッフ入室時刻のバリデーション/クリーニング
    def clean_staff_entry_time(self):
        """IntegerField が空で送信された場合に None に変換し、バリデーションエラーを回避する。"""
        staff_entry_time = self.cleaned_data.get('staff_entry_time')
        if staff_entry_time is None or staff_entry_time == '':
            return None
        return staff_entry_time

    #スタッフ退出時刻のバリデーション/クリーニング
    def clean_staff_leaving_time(self):
        """IntegerField が空で送信された場合に None に変換し、バリデーションエラーを回避する。"""
        staff_leaving_time = self.cleaned_data.get('staff_leaving_time')
        if staff_leaving_time is None or staff_leaving_time == '':
            return None
        return staff_leaving_time

    def clean_sleep_time_hours(self):
        # POSTデータから値を取得
        data = self.data.get('sleep_time_hours')

        #値がない（空文字列や None）の場合は、None を返す。
        # これにより、IntegerFieldのバリデーション（数値変換エラー）を回避し、
        # DBのNULLとして保存できるようにする。
        if not data and data != 0:
            return None

        #値が存在する場合は、フォームのFieldが正常に処理した cleaned_data の値を返す
        # この値に対して、IntegerFieldの min_value=0, max_value=24 のチェックが適用される
        sleep_time = self.cleaned_data.get('sleep_time_hours')

        if sleep_time is not None:
            #範囲チェックを明示的に追加する修正 ★★★
            if sleep_time < 0 or sleep_time > 24:
                # ユーザーに分かりやすいエラーメッセージを表示
                raise forms.ValidationError("睡眠時間（時間）は0から24までの値を入力してください。")

            return sleep_time
        """
        # None ではない（つまり、数値変換に成功した）場合のみ返却し、
        # 範囲チェックを通過させる
        if sleep_time is not None:
            return sleep_time
        """
        # 変換エラーが発生した場合、このメソッドは通常実行されないが、念のため
        return None
    class Meta:
        model = InputScreen
        # フォームで扱うフィールドを全て指定
        fields = [
            "entry_time",
            "leaving_time",
            "staff_entry_time",
            "staff_leaving_time",
            "sleep_time_hours",
            "morning_work_content",
            "afternoon_work_content",
            "condition",
            "condition_detail_good",
            "condition_detail_caution",
            "condition_detail_poor",
            "at_home",
            "medication_morning",
            "medication_noon",
            "medication_night",
            "user_comment",
            "staff_comment",
        ]

    def clean(self):
        cleaned_data = super().clean()
        at_home = cleaned_data.get('at_home')
        entry_time = cleaned_data.get('entry_time')
        #睡眠時間フィールドのNULL許容と範囲チェックを確実に行うロジック ★
        # ----------------------------------------------------
        sleep_time = cleaned_data.get('sleep_time_hours')

        #POSTデータが空文字列の場合（ユーザーが何も入力しなかった場合）を検出
        raw_sleep_time = self.data.get('sleep_time_hours')

        if not raw_sleep_time and raw_sleep_time != '0':
            # cleaned_dataから値を削除し、Noneとして扱うようにする
            if 'sleep_time_hours' in cleaned_data:
                del cleaned_data['sleep_time_hours']

        elif sleep_time is not None:
            # 値が数値変換に成功した場合のみ、明示的な範囲チェックを実行
            # IntegerField の min_value=0, max_value=24 が失敗している場合に備える
            if sleep_time < 0 or sleep_time > 24:
                self.add_error(
                    'sleep_time_hours',
                    '睡眠時間（時間）は0から24までの値を入力してください。'
                )

        # 1. 退出時刻（leaving_time）の文字列を datetime.time オブジェクトに変換
        leaving_time_str = cleaned_data.get('leaving_time')
        leaving_time = None  # 変数を初期化してUnboundLocalErrorを防止
        if leaving_time_str:
            try:
                # 'HH:MM' の文字列を time オブジェクトに変換
                if isinstance(leaving_time_str, str):
                    leaving_time = datetime.strptime(leaving_time_str, '%H:%M').time()
                else:
                    leaving_time = leaving_time_str  # すでにtimeオブジェクトの場合はそのまま使用
            except ValueError:
                # 選択肢から選ばれた場合は通常発生しないが、念のため
                self.add_error('leaving_time', '退出時刻の形式が正しくありません。')

        # 2. entry_time の文字列を datetime.time オブジェクトに変換 (もしあれば)
        entry_time_str = cleaned_data.get('entry_time')
        if entry_time_str:
            pass  # clean_entry_time()に任せる
        elif 'entry_time' in self.fields and isinstance(self.fields['entry_time'].widget,
                                                        forms.TimeInput) and entry_time_str:
            # entry_time が文字列として残っている場合（通常TimeFieldでは自動変換されるが念のため）
            try:
                entry_time = datetime.strptime(entry_time_str, '%H:%M').time()
            except ValueError:
                pass
        

        # 【新規追加】スタッフ入室時刻の取得
        staff_entry_time = cleaned_data.get('staff_entry_time')

        #スタッフ入力の退出時刻にも、利用者入力と同じカスタム変換を適用
        staff_leaving_time = cleaned_data.get('staff_leaving_time')
        if staff_leaving_time and not isinstance(staff_leaving_time, time):
            try:
                staff_leaving_time = datetime.strptime(staff_leaving_time, '%H:%M').time()
                cleaned_data['staff_leaving_time'] = staff_leaving_time
            except ValueError:
                pass

        if at_home:
            # ログインユーザーの権限を取得
            user_role = getattr(self.user, 'user_role', None) if self.user else None

            # スタッフ（user_role が 2 または 3）の場合のみ、スタッフ入退出時刻の入力を必須にする
            if user_role and user_role != 1:
                # スタッフ入室時刻の必須チェック
                if not staff_entry_time:
                    self.add_error('staff_entry_time', '在宅の場合、スタッフ入室時刻は必須です。')

                # スタッフ退出時刻の必須チェック
                if not staff_leaving_time:
                    self.add_error('staff_leaving_time', '在宅の場合、スタッフ退出時刻は必須です。')

                # スタッフ入退出時刻の前後関係チェック
                if staff_entry_time and staff_leaving_time:
                    # 念のため time オブジェクトであるかチェック
                    if isinstance(staff_entry_time, time) and isinstance(staff_leaving_time, time):
                        if staff_entry_time >= staff_leaving_time:
                            self.add_error('staff_leaving_time',
                                           'スタッフ退出時刻は入室時刻より後の時刻を入力してください。')

        # 在宅チェックがない場合、入室時刻と退出時刻のバリデーションを実行
        if not at_home:
            if not entry_time and leaving_time:
                # 退出時刻のみ入力されている場合
                self.add_error('entry_time', '入室時刻を入力してください。')
            elif entry_time and not leaving_time:
                # 入室時刻のみ入力されている場合
                self.add_error('leaving_time', '退出時刻を入力してください。')
            elif entry_time and leaving_time:
                #両方の値が存在し、かつ entry_time と leaving_time が datetime.time オブジェクトであるかチェック
                if isinstance(entry_time, time) and isinstance(leaving_time, time):
                    if entry_time >= leaving_time:
                        # 入室時刻が退出時刻より後の場合
                        self.add_error('leaving_time', '退出時刻は入室時刻より後の時刻を入力してください。')
                else:
                    # 予期しない型（例: leaving_timeが文字列のまま）が残っていた場合、エラーを再度発生させるか、無視するかを選択。

                    if isinstance(leaving_time, str):
                        self.add_error('leaving_time', '退出時刻の形式が不正です。')

                    if entry_time >= leaving_time:
                        self.add_error('leaving_time', '退出時刻は入室時刻より後の時刻を入力してください。')

        return cleaned_data


# 土曜開所日選択フォーム (複数の土曜日を選択できるように修正)
class SaturdayOpeningForm(forms.ModelForm):
    date_list = forms.CharField(
        label="土曜開所日（複数入力可）",
        widget=forms.Textarea(
        attrs={'rows': 3}),
        help_text="開所する土曜日の日付を **YYYY-MM-DD** 形式で入力してください。複数ある場合はカンマ、スペース、または改行で区切ってください。",
        required=True
    )

    class Meta:
        model = SaturdayOpening
        fields = []  # ModelForm の fields には何も指定しないか、空のリストにします

    def clean_date_list(self):
        date_string = self.cleaned_data.get('date_list')

        # カンマ、空白、改行で日付文字列を分割し、リストを作成
        # 空白や空の文字列を除外
        date_str_list = []
        for separator in [',', '\n', ' ']:
            if date_str_list:
                # 既に分割されている場合は、各要素をさらに分割
                temp_list = []
                for item in date_str_list:
                    temp_list.extend([s.strip() for s in item.split(separator) if s.strip()])
                date_str_list = temp_list
            else:
                # 最初の分割
                date_str_list = [s.strip() for s in date_string.split(separator) if s.strip()]

        valid_dates = []
        errors = []

        # 登録を試みる日付のセット (重複チェック用)
        dates_to_register = set()

        for date_str in date_str_list:
            try:
                # 全角文字を半角に変換
                converted_date_str = self._normalize_date_string(date_str)

                # 様々な日付形式をパース
                selected_date = self._parse_flexible_date(converted_date_str)

            except ValueError as e:
                errors.append(f"'{date_str}' は有効な日付形式ではありません。{str(e)}")
                continue

            # 1. 曜日チェック (5=土曜日)
            if selected_date.weekday() != 5:
                errors.append(f"{selected_date.strftime('%Y-%m-%d')} は土曜日ではありません。")

            # 2. 過去の日付でないかチェック
            if selected_date < date.today():
                errors.append(f"{selected_date.strftime('%Y-%m-%d')} は過去の日付です。選択できません。")

            # 3. フォーム内での重複チェック
            if selected_date in dates_to_register:
                errors.append(f"{selected_date.strftime('%Y-%m-%d')} はリスト内で重複しています。")
            else:
                dates_to_register.add(selected_date)

            # 4. 既にデータベースに登録されていないかチェック
            if SaturdayOpening.objects.filter(open_date=selected_date).exists():
                errors.append(f"{selected_date.strftime('%Y-%m-%d')} は既に土曜開所日として登録されています。")

            valid_dates.append(selected_date)

        if errors:
            # エラーをまとめて表示
            raise forms.ValidationError(errors)

        # バリデーションに成功した日付オブジェクトのリストを返却
        # これをビューの post メソッドで利用します
        return valid_dates

    def _normalize_date_string(self, date_str):
        """全角文字を半角に変換する"""
        import re
        # 全角数字を半角に変換
        date_str = re.sub(r'[０-９]', lambda m: str(ord(m.group()) - ord('０')), date_str)
        # 全角スラッシュを半角に変換
        date_str = date_str.replace('／', '/')
        # 全角中黒を半角スラッシュに変換
        date_str = date_str.replace('・', '/')
        # 全角ハイフンを半角に変換
        date_str = date_str.replace('－', '-')
        return date_str

    def _parse_flexible_date(self, date_str):
        """様々な日付形式をパースする"""
        import re
        from datetime import datetime

        # M/D または MM/DD 形式
        if '/' in date_str:
            # 年が省略された形式（例: 10/24 や 10・24）の場合、今年の年を補完
            match_md = re.match(r'^(\d{1,2})/(\d{1,2})$', date_str)
            if match_md:
                month, day = map(int, match_md.groups())
                year = date.today().year
                return date(year, month, day)

            # 年が含まれる形式（例: 2026/10/24）の場合
            match = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', date_str)
            if match:
                year, month, day = map(int, match.groups())
                return date(year, month, day)

        # M-D または MM-DD 形式
        elif '-' in date_str:
            # 年が省略された形式（例: 10-24）の場合、今年の年を補完
            match_md = re.match(r'^(\d{1,2})-(\d{1,2})$', date_str)
            if match_md:
                month, day = map(int, match_md.groups())
                year = date.today().year
                return date(year, month, day)

            # 年が含まれる形式（例: 2026-10-24）の場合
            match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str)
            if match:
                year, month, day = map(int, match.groups())
                return date(year, month, day)

        # YYYYMMDD 形式
        elif re.match(r'^\d{8}$', date_str):
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            return date(year, month, day)

        # その他の形式は fromisoformat で試す
        else:
            return date.fromisoformat(date_str)

# 土曜開所日削除用フォーム (複数の土曜日を選択)
class SaturdayOpeningDeleteForm(forms.Form):
    """
    土曜開所日一覧から削除対象のIDを選択するためのフォーム。
    """
    # 選択された SaturdayOpening の ID を保持するための HiddenInput
    # テンプレート側で SaturdayOpening.id を値として持つチェックボックスを作成し、
    # その name 属性を 'selected_openings' にする必要があります。
    selected_openings = forms.CharField(
        label="削除対象",
        required=False,
    )

    # フィールドをオーバーライドして、ChoiceFieldではなく通常のフィールドとして動作させる
    # 実際にはビューの get_context_data で渡す一覧を基にテンプレートでチェックボックスを生成し、
    # このフォームは POST された ID を受け取るために使われます。

    def clean_selected_openings(self):
        selected_ids = self.data.getlist('selected_openings')  # POSTデータからリストとして取得

        if not selected_ids:
            # フォームとしてエラーを発生させる（エラーメッセージは View で処理）
            raise forms.ValidationError('削除する土曜開所日を選択してください。')

        # IDが有効な数字であることを確認する（オプショナル）
        valid_ids = []
        for id_str in selected_ids:
            if id_str.isdigit():
                valid_ids.append(int(id_str))
        # else: 無効なIDは無視するか、エラーとする

        # データベースに存在するかを確認する（オプショナル：確認画面で再度チェックされるため、ここでは省略可能）
        # if SaturdayOpening.objects.filter(id__in=valid_ids).count() != len(valid_ids):
        #     raise forms.ValidationError('無効なIDが含まれています。')

        return valid_ids  # 選択されたIDのリストを返却