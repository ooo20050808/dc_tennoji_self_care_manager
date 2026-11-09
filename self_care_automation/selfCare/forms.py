from datetime import date, datetime, time, timedelta
import re
from django import forms
from django.core.exceptions import ValidationError
from .models import User, InputScreen, SaturdayOpening


class LoginForm(forms.Form):
	"""ログイン用フォーム"""
	email = forms.EmailField(label="メールアドレス")
	password = forms.CharField(label="パスワード", widget=forms.PasswordInput)


class AuthForm(forms.Form):
	"""管理者認証用フォーム"""
	email = forms.EmailField(label="メールアドレス")
	password = forms.CharField(label="パスワード", widget=forms.PasswordInput)


class UserOnlyAuthForm(forms.Form):
	"""ユーザー編集・削除時の本人確認用フォーム"""
	email = forms.EmailField(label="メールアドレス")


class UserEditForm(forms.ModelForm):
	"""ユーザー情報編集フォーム"""
	password = forms.CharField(label="新しいパスワード", required=False, widget=forms.PasswordInput)
	password_confirm = forms.CharField(label="新しいパスワード（確認）", required=False, widget=forms.PasswordInput)

	class Meta:
		model = User
		fields = ["email", "user_name"]

	def clean(self):
		cleaned_data = super().clean()
		password = cleaned_data.get("password")
		password_confirm = cleaned_data.get("password_confirm")

		if password and password != password_confirm:
			self.add_error("password_confirm", "パスワードが一致しません")
		return cleaned_data


class UserCreateForm(forms.ModelForm):
	"""ユーザー新規作成フォーム"""
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


def generate_time_choices(start_hour: int, end_hour: int, interval_minutes: int):
	"""指定された時間帯と間隔で HH:MM 形式の選択肢を生成します。"""
	start_time = datetime.strptime(f'{start_hour:02d}:00', '%H:%M')
	end_time = datetime.strptime(f'{end_hour:02d}:00', '%H:%M')
	choices = [('', '---------')]
	current_time = start_time
	while current_time <= end_time:
		time_str = current_time.strftime('%H:%M')
		choices.append((time_str, time_str))
		current_time += timedelta(minutes=interval_minutes)
	return choices


LEAVING_TIME_CHOICES = generate_time_choices(10, 16, 15)


class InputScreenForm(forms.ModelForm):
	"""勤怠・体調入力画面用フォーム"""
	CONDITION_CHOICES = [
		("〇", "良好（○）"),
		("△", "注意（△）"),
		("✕", "悪化（✕）")
	]

	entry_time = forms.ChoiceField(label="入室時刻", choices=LEAVING_TIME_CHOICES, required=False,
								   widget=forms.Select(attrs={'class': 'time-input'}))
	leaving_time = forms.ChoiceField(label="退出時刻", choices=LEAVING_TIME_CHOICES, required=False,
									 widget=forms.Select(attrs={'class': 'time-input'}))
	staff_entry_time = forms.TimeField(label="スタッフ入室時刻", widget=forms.TimeInput(attrs={'type': 'time'}),
									   required=False)
	staff_leaving_time = forms.ChoiceField(label="スタッフ退出時刻", choices=LEAVING_TIME_CHOICES, required=False,
										   widget=forms.Select(attrs={'class': 'time-input'}))

	sleep_time_hours = forms.IntegerField(
		label="睡眠時間（時間）",
		min_value=0,
		max_value=24,
		widget=forms.NumberInput(attrs={"min": 0, "max": 24}),
		required=False,
	)
	morning_work_content = forms.CharField(label="午前作業内容", required=False, widget=forms.Textarea(
		attrs={'rows': 3, 'placeholder': '午前の作業内容を入力...'}))
	afternoon_work_content = forms.CharField(label="午後作業内容", required=False, widget=forms.Textarea(
		attrs={'rows': 3, 'placeholder': '午後の作業内容を入力...'}))

	condition = forms.ChoiceField(label="体調", choices=CONDITION_CHOICES, widget=forms.Select(), required=False)
	condition_detail_good = forms.CharField(label="体調詳細（良好）", required=False,
											widget=forms.Textarea(attrs={'class': 'condition-detail', 'rows': 4}))
	condition_detail_caution = forms.CharField(label="体調詳細（注意）", required=False,
											   widget=forms.Textarea(attrs={'class': 'condition-detail', 'rows': 4}))
	condition_detail_poor = forms.CharField(label="体調詳細（悪化）", required=False,
											widget=forms.Textarea(attrs={'class': 'condition-detail', 'rows': 4}))

	at_home = forms.BooleanField(label="在宅中", required=False, widget=forms.CheckboxInput())
	medication_morning = forms.BooleanField(label="服薬（朝）", required=False, widget=forms.CheckboxInput())
	medication_noon = forms.BooleanField(label="服薬（昼）", required=False, widget=forms.CheckboxInput())
	medication_night = forms.BooleanField(label="服薬（夜）", required=False, widget=forms.CheckboxInput())

	user_comment = forms.CharField(label="利用者コメント", required=False, widget=forms.Textarea(attrs={'rows': 3}))
	staff_comment = forms.CharField(label="スタッフコメント", required=False, widget=forms.Textarea(attrs={'rows': 3}))

	class Meta:
		model = InputScreen
		fields = [
			"entry_time", "leaving_time", "staff_entry_time", "staff_leaving_time",
			"sleep_time_hours", "morning_work_content", "afternoon_work_content",
			"condition", "condition_detail_good", "condition_detail_caution", "condition_detail_poor",
			"at_home", "medication_morning", "medication_noon", "medication_night",
			"user_comment", "staff_comment",
		]

	def __init__(self, *args, user=None, **kwargs):
		self.user = kwargs.pop('user', None)
		super().__init__(*args, **kwargs)

	def _convert_time_string(self, time_str):
		"""文字列の時刻を datetime.time オブジェクトに変換します。"""
		if not time_str:
			return None
		if isinstance(time_str, time):
			return time_str
		try:
			return datetime.strptime(time_str, '%H:%M').time()
		except ValueError:
			raise forms.ValidationError('無効な時刻形式です。')

	def clean_entry_time(self):
		return self._convert_time_string(self.cleaned_data.get('entry_time'))

	def clean_leaving_time(self):
		return self._convert_time_string(self.cleaned_data.get('leaving_time'))

	def clean_sleep_time_hours(self):
		data = self.data.get('sleep_time_hours')
		if not data and data != '0':
			return None
		sleep_time = self.cleaned_data.get('sleep_time_hours')
		if sleep_time is not None and not (0 <= sleep_time <= 24):
			raise forms.ValidationError("睡眠時間（時間）は0から24までの値を入力してください。")
		return sleep_time

	def clean(self):
		cleaned_data = super().clean()
		at_home = cleaned_data.get('at_home')
		entry_time = cleaned_data.get('entry_time')
		leaving_time = cleaned_data.get('leaving_time')
		staff_entry_time = cleaned_data.get('staff_entry_time')
		staff_leaving_time_str = self.cleaned_data.get('staff_leaving_time')
		staff_leaving_time = self._convert_time_string(staff_leaving_time_str)
		if staff_leaving_time:
			cleaned_data['staff_leaving_time'] = staff_leaving_time

		# 在宅時のスタッフ入退室バリデーション
		if at_home:
			user_role = getattr(self.user, 'user_role', None) if self.user else None
			if user_role and user_role != 1:
				if not staff_entry_time:
					self.add_error('staff_entry_time', '在宅の場合、スタッフ入室時刻は必須です。')
				if not staff_leaving_time:
					self.add_error('staff_leaving_time', '在宅の場合、スタッフ退出時刻は必須です。')
				if staff_entry_time and staff_leaving_time and staff_entry_time >= staff_leaving_time:
					self.add_error('staff_leaving_time', 'スタッフ退出時刻は入室時刻より後の時刻を入力してください。')

		# 通常出勤時の入退室バリデーション
		if not at_home:
			if not entry_time and leaving_time:
				self.add_error('entry_time', '入室時刻を入力してください。')
			elif entry_time and not leaving_time:
				self.add_error('leaving_time', '退出時刻を入力してください。')
			elif entry_time and leaving_time and entry_time >= leaving_time:
				self.add_error('leaving_time', '退出時刻は入室時刻より後の時刻を入力してください。')

		return cleaned_data


class SaturdayOpeningForm(forms.ModelForm):
	"""土曜開所日の一括登録用フォーム"""
	date_list = forms.CharField(
		label="土曜開所日（複数入力可）",
		widget=forms.Textarea(attrs={'rows': 3}),
		help_text="YYYY-MM-DD形式で入力してください。複数ある場合はカンマや改行で区切ってください。",
		required=True
	)

	class Meta:
		model = SaturdayOpening
		fields = []

	def clean_date_list(self):
		date_string = self.cleaned_data.get('date_list')
		date_str_list = []
		for separator in [',', '\n', ' ']:
			if date_str_list:
				temp_list = []
				for item in date_str_list:
					temp_list.extend([s.strip() for s in item.split(separator) if s.strip()])
				date_str_list = temp_list
			else:
				date_str_list = [s.strip() for s in date_string.split(separator) if s.strip()]

		valid_dates = []
		errors = []
		dates_to_register = set()

		for date_str in date_str_list:
			try:
				normalized_str = self._normalize_date_string(date_str)
				selected_date = self._parse_flexible_date(normalized_str)
			except ValueError as e:
				errors.append(f"'{date_str}' は有効な日付形式ではありません。{str(e)}")
				continue

			if selected_date.weekday() != 5:
				errors.append(f"{selected_date.strftime('%Y-%m-%d')} は土曜日ではありません。")
			if selected_date < date.today():
				errors.append(f"{selected_date.strftime('%Y-%m-%d')} は過去の日付です。")
			if selected_date in dates_to_register:
				errors.append(f"{selected_date.strftime('%Y-%m-%d')} はリスト内で重複しています。")
			else:
				dates_to_register.add(selected_date)
			if SaturdayOpening.objects.filter(open_date=selected_date).exists():
				errors.append(f"{selected_date.strftime('%Y-%m-%d')} は既に登録されています。")

			valid_dates.append(selected_date)

		if errors:
			raise forms.ValidationError(errors)
		return valid_dates

	def _normalize_date_string(self, date_str):
		date_str = re.sub(r'[０-９]', lambda m: str(ord(m.group()) - ord('０')), date_str)
		return date_str.replace('／', '/').replace('・', '/').replace('－', '-')

	def _parse_flexible_date(self, date_str):
		if '/' in date_str:
			if match := re.match(r'^(\d{1,2})/(\d{1,2})$', date_str):
				return date(date.today().year, int(match.group(1)), int(match.group(2)))
			if match := re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', date_str):
				return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
		elif '-' in date_str:
			if match := re.match(r'^(\d{1,2})-(\d{1,2})$', date_str):
				return date(date.today().year, int(match.group(1)), int(match.group(2)))
			if match := re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str):
				return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
		elif re.match(r'^\d{8}$', date_str):
			return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
		return date.fromisoformat(date_str)


class SaturdayOpeningDeleteForm(forms.Form):
	"""土曜開所日削除用フォーム"""
	selected_openings = forms.CharField(label="削除対象", required=False)

	def clean_selected_openings(self):
		selected_ids = self.data.getlist('selected_openings')
		if not selected_ids:
			raise forms.ValidationError('削除する土曜開所日を選択してください。')
		return [int(id_str) for id_str in selected_ids if id_str.isdigit()]