import base64
import calendar
from datetime import date, datetime, time, timedelta
import io
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import japanize_matplotlib

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, TemplateView, View

from .forms import (
	AuthForm, InputScreenForm, LoginForm, SaturdayOpeningDeleteForm,
	SaturdayOpeningForm, UserCreateForm, UserEditForm, UserOnlyAuthForm
)
from .models import HomeScreen, InputScreen, SaturdayOpening, User


def check_staff_permission(user):
	"""ユーザーがスタッフ権限（is_staffまたはis_superuser）を持っているか確認する"""
	return user.is_staff or user.is_superuser


def user_login(request):
	"""ユーザーログイン処理ビュー"""
	if request.method == 'POST':
		form = LoginForm(request.POST)
		if form.is_valid():
			user = authenticate(
				request,
				email=form.cleaned_data.get('email'),
				password=form.cleaned_data.get('password')
			)
			if user is not None:
				login(request, user)
				if user.user_role == User.CLIENT:
					today = date.today()
					home_screen = HomeScreen.objects.filter(user=user, date=today).first() \
								  or HomeScreen.objects.filter(user=user).order_by('-date').first() \
								  or HomeScreen.objects.create(user=user, date=today)
					return redirect("selfCare:detail_select", home_screen_id=home_screen.id)
				elif user.user_role == User.STAFF:
					return redirect('selfCare:saturday_choice')
				else:
					return redirect("selfCare:admin_screen")
			else:
				return render(request, 'login.html',
							  {'form': form, 'error_message': 'ユーザー名またはパスワードが間違っています。'})
	else:
		form = LoginForm()
	return render(request, 'login.html', {'form': form})


class UserListView(LoginRequiredMixin, ListView):
	"""利用者一覧表示ビュー（ページネーション・ステータス判定付き）"""

	def get(self, request, action=None, *args, **kwargs):
		user_role = request.user.user_role
		all_users = User.objects.filter(user_role__in=[1, 2]) if user_role == 3 else User.objects.filter(user_role=1)
		all_users = list(all_users)

		if request.GET.get('from') == 'complete' or not action:
			request.session.pop('target_action', None)
			request.session.pop('target_user_id', None)

		try:
			date_str = request.GET.get('date')
			if date_str:
				view_date = date.fromisoformat(date_str)
				request.session['selected_date_for_user_list'] = date_str
			else:
				session_date_str = request.session.get('selected_date_for_user_list')
				view_date = date.fromisoformat(session_date_str) if session_date_str else date.today()
		except ValueError:
			view_date = date.today()

		page_size = 20
		total_pages = (len(all_users) + page_size - 1) // page_size
		try:
			page_num = max(1, min(int(request.GET.get('page', 1)), total_pages or 1))
		except ValueError:
			page_num = 1

		current_page_users = all_users[(page_num - 1) * page_size: page_num * page_size]
		edit_data = request.session.get('edit_data', {})
		user_data = []

		for user in current_page_users:
			home_screen, _ = HomeScreen.objects.get_or_create(user=user, date=view_date)
			input_data = InputScreen.objects.filter(user=user, date__date=view_date).first()

			entry_time_display, leaving_time_display = "未入力", "未入力"
			sleep_time_display, condition_display = "未入力", "未入力"
			medication_missing = True

			if input_data:
				if input_data.staff_entry_time:
					entry_time_display = input_data.staff_entry_time.strftime("%H:%M")
				elif input_data.entry_time:
					entry_time_display = input_data.entry_time.strftime("%H:%M")

				if input_data.staff_leaving_time:
					leaving_time_display = input_data.staff_leaving_time.strftime("%H:%M")
				elif input_data.leaving_time:
					leaving_time_display = input_data.leaving_time.strftime("%H:%M")

				if input_data.sleep_time_hours and input_data.sleep_time_hours > 0:
					sleep_time_display = f"{int(input_data.sleep_time_hours)}時間"
				if input_data.condition:
					condition_display = input_data.condition

				med_incomplete = not all([
					input_data.medication_morning,
					input_data.medication_noon,
					input_data.medication_night
				])
				other_missing = any(v == "未入力" for v in
									[entry_time_display, leaving_time_display, sleep_time_display, condition_display])
				medication_missing = med_incomplete or other_missing

			display_name = user.user_name or user.email
			if edit_data and edit_data.get('id') == user.id:
				display_name = edit_data.get('user_name') or edit_data.get('email', display_name)

			_, _, overall_avg_sleep, _, _ = create_monthly_average_sleep_chart(user=user, end_date=view_date)
			avg_sleep_display = f"{overall_avg_sleep}h" if overall_avg_sleep is not None else None

			user_data.append({
				"user": user,
				"input_data": input_data,
				"display_name": display_name,
				"entry_time_display": entry_time_display,
				"leaving_time_display": leaving_time_display,
				"sleep_time": sleep_time_display,
				"average_sleep_time": avg_sleep_display,
				"condition": condition_display,
				"view_date": view_date,
				"home_screen_id": home_screen.id,
				"medication_missing": medication_missing,
				"action": action,
			})

		user_pages = [user_data[i:i + page_size] for i in range(0, len(user_data), page_size)]
		context = {
			"user_pages": user_pages,
			"user_role": request.user.user_role,
			"total_pages": total_pages,
			"page_num": page_num,
			"view_date": view_date
		}
		return render(request, "user_list.html", context)


class CalendarListView(LoginRequiredMixin, ListView):
	"""カレンダー一覧表示ビュー"""
	model = HomeScreen
	template_name = "calendar_list.html"
	context_object_name = "home_screens"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		today = date.today()
		year = int(self.request.GET.get("year", today.year))
		month = int(self.request.GET.get("month", today.month))

		self.request.session['calendar_year'] = year
		self.request.session['calendar_month'] = month
		context["current_month_year"] = date(year, month, 1)

		cal = calendar.Calendar(firstweekday=6)
		month_days = cal.monthdatescalendar(year, month)

		start_date = date(year, month, 1)
		end_date = date(year + 1, 1, 1) - timedelta(days=1) if month == 12 else date(year, month + 1, 1) - timedelta(
			days=1)

		registered_saturdays = set(
			SaturdayOpening.objects.filter(open_date__range=[start_date, end_date]).values_list('open_date', flat=True)
		)

		annotated_month_days = []
		for week in month_days:
			annotated_week = []
			for day in week:
				is_saturday = day.weekday() == calendar.SATURDAY
				is_open_saturday = day in registered_saturdays
				home_screen_id = None

				if day.month == month:
					home_screen, _ = HomeScreen.objects.get_or_create(user=self.request.user, date=day)
					home_screen_id = home_screen.id

				annotated_week.append({
					'date': day,
					'is_saturday': is_saturday,
					'is_open_saturday': is_open_saturday,
					'is_input_complete': False,
					'home_screen_id': home_screen_id,
				})
			annotated_month_days.append(annotated_week)

		prev_month_date = start_date - timedelta(days=1)
		next_month_date = end_date + timedelta(days=1)

		context.update({
			"year": year,
			"month": month,
			"month_days_annotated": annotated_month_days,
			'prev_month_url': f"?year={prev_month_date.year}&month={prev_month_date.month}",
			'next_month_url': f"?year={next_month_date.year}&month={next_month_date.month}",
			"user_role": self.request.user.user_role,
			"user": self.request.user
		})
		return context

	def get_queryset(self):
		return HomeScreen.objects.filter(user=self.request.user)


def calendar_detail_view(request, year, month, day):
	"""カレンダーの日付クリック時の遷移制御ビュー"""
	request.session['calendar_year'] = year
	request.session['calendar_month'] = month
	selected_date = date(year, month, day)
	user = request.user

	if selected_date.weekday() == calendar.SUNDAY:
		messages.error(request, f'{selected_date.strftime("%Y年%m月%d日")} は日曜休業日のため、入力できません。')
		return redirect("selfCare:calendar_list")

	if selected_date.weekday() == calendar.SATURDAY:
		if not SaturdayOpening.objects.filter(open_date=selected_date).exists():
			messages.error(request, f'{selected_date.strftime("%Y年%m月%d日")} は土曜休業日のため、利用できません。')
			return redirect("selfCare:calendar_list")

	if user.user_role == User.CLIENT:
		home_screen, _ = HomeScreen.objects.get_or_create(user=user, date=selected_date)
		return redirect("selfCare:input_screen", home_screen_id=home_screen.id)
	elif user.user_role in [User.STAFF, User.ADMIN]:
		request.session['selected_date_for_user_list'] = selected_date.isoformat()
		return redirect(f"{reverse('selfCare:user_list')}?date={selected_date.isoformat()}")
	return redirect("selfCare:calendar_list")


class DetailSelectView(LoginRequiredMixin, View):
	"""コメント一覧か入力画面かを選択するビュー"""

	def get(self, request, home_screen_id, *args, **kwargs):
		home_screen = get_object_or_404(HomeScreen, id=home_screen_id, user=request.user)
		if request.user.user_role != User.CLIENT:
			messages.error(request, "このページは利用者専用です。")
			return redirect("selfCare:calendar_list")
		return render(request, "detail_select.html", {"home_screen": home_screen, "selected_date": home_screen.date})


class StaffDetailView(LoginRequiredMixin, View):
	"""スタッフ用詳細リダイレクトビュー"""

	def get(self, request, user_id, selected_date_str=None, *args, **kwargs):
		selected_user = get_object_or_404(User, id=user_id)
		selected_date = date.fromisoformat(selected_date_str) if selected_date_str else date.today()
		home_screen, _ = HomeScreen.objects.get_or_create(user=selected_user, date=selected_date)
		return redirect("selfCare:input_screen", home_screen_id=home_screen.id)


class AdminDetailView(LoginRequiredMixin, View):
	"""管理者メニュービュー"""

	def get(self, request, user_id=None, *args, **kwargs):
		target_user = None
		if user_id is not None:
			target_user = get_object_or_404(User, id=user_id)
			request.session['target_user_id'] = user_id
		else:
			request.session.pop('target_user_id', None)
			request.session.pop('target_action', None)
		return render(request, 'admin_screen.html',
					  {'user': request.user, 'target_user': target_user, 'title': '管理者メニュー'})


class AdminScreenView(LoginRequiredMixin, View):
	"""管理者認証画面ビュー"""

	def get(self, request, user_id=None, action=None, *args, **kwargs):
		if user_id and action in ['edit', 'delete']:
			target_user = get_object_or_404(User, id=user_id)
			request.session['target_user_id'] = user_id
			request.session['target_action'] = action
			return render(request, 'admin_auth.html',
						  {'target_user': target_user, 'action': action, 'form': AuthForm(), 'title': '管理者認証'})

		if user_id:
			target_user = get_object_or_404(User, id=user_id)
			request.session['target_user_id'] = user_id
			if action in ['edit', 'delete']:
				request.session['target_action'] = action
				return redirect("selfCare:admin_auth_action", user_id=user_id, action=action)
			return render(request, 'admin_screen.html', {'target_user': target_user, 'action': action})

		if user_id is None and 'manager_auth' in request.path:
			request.session.pop('target_user_id', None)
			request.session.pop('target_action', None)
			return render(request, 'admin_auth.html', {'form': AuthForm(), 'title': '管理者認証'})

		request.session.pop('target_user_id', None)
		request.session.pop('target_action', None)
		return render(request, 'admin_screen.html', {'user': request.user, 'title': '管理者メニュー'})

	def post(self, request, user_id=None, action=None, *args, **kwargs):
		session_user_id = request.session.get('target_user_id')
		target_action = request.session.get('target_action')
		form = AuthForm(request.POST)

		if form.is_valid():
			user = authenticate(request, email=form.cleaned_data.get('email'),
								password=form.cleaned_data.get('password'))
			if user and user.is_authenticated and user.user_role == User.ADMIN:
				if session_user_id:
					return redirect(
						"selfCare:user_delete_auth" if target_action == 'delete' else "selfCare:user_edit_auth",
						user_id=session_user_id)
				return redirect("selfCare:user_create_screen")
			return render(request, 'admin_auth.html',
						  {'form': form, 'error_message': '管理者としての認証に失敗しました。'})
		return render(request, 'admin_auth.html', {'form': form, 'error_message': '入力に誤りがあります。'})


class UserAuthView(LoginRequiredMixin, View):
	"""編集・削除対象のユーザー認証ビュー"""

	def get(self, request, user_id, action=None, *args, **kwargs):
		target_user = get_object_or_404(User, id=user_id)
		title = f"{target_user.user_name}さんの削除認証" if action == 'delete' else f"{target_user.user_name}さんの編集認証"
		return render(request, 'user_auth.html',
					  {'form': UserOnlyAuthForm(), 'target_user': target_user, 'action': action, 'title': title})

	def post(self, request, user_id, action=None, *args, **kwargs):
		action_value = request.POST.get('action', action)
		form = UserOnlyAuthForm(request.POST)
		target_user = get_object_or_404(User, id=user_id)

		if form.is_valid() and target_user.email == form.cleaned_data.get("email"):
			return redirect("selfCare:user_delete_confirm" if action_value == 'delete' else "selfCare:edit_screen",
							user_id=user_id)

		title = f"{target_user.user_name}さんの削除認証" if action_value == 'delete' else f"{target_user.user_name}さんの編集認証"
		return render(request, 'user_auth.html',
					  {'form': form, 'error_message': 'メールアドレスが間違っています。', 'action': action_value,
					   'target_user': target_user, 'title': title})


class EditScreenView(LoginRequiredMixin, View):
	"""ユーザー編集画面ビュー"""

	def get(self, request, user_id, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			messages.error(request, "権限がありません。")
			return redirect("selfCare:user_list")
		target_user = get_object_or_404(User, id=user_id)
		edit_data = request.session.get("edit_data")
		form = UserEditForm(initial=edit_data) if edit_data and edit_data.get("id") == int(user_id) else UserEditForm(
			instance=target_user)
		return render(request, "edit_screen.html", {"form": form, "target_user": target_user})

	def post(self, request, user_id, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			return redirect("selfCare:user_list")
		target_user = get_object_or_404(User, id=user_id)
		form = UserEditForm(request.POST, instance=target_user)
		if form.is_valid():
			edit_data = {
				"id": user_id,
				"email": form.cleaned_data.get("email"),
				"user_name": form.cleaned_data.get("user_name"),
			}
			if password := form.cleaned_data.get("password"):
				edit_data["password"] = password
			request.session["edit_data"] = edit_data
			return redirect("selfCare:edit_confirm", user_id=user_id)
		return render(request, 'edit_screen.html', {"form": form, "target_user": target_user})


class EditConfirmView(LoginRequiredMixin, View):
	"""ユーザー編集確認画面ビュー"""

	def get(self, request, user_id, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			return redirect("selfCare:user_list")
		edit_data = request.session.get("edit_data")
		if not edit_data:
			return redirect("selfCare:edit_screen", user_id=user_id)
		target_user = get_object_or_404(User, id=user_id)
		return render(request, "edit_confirm.html", {"target_user": target_user, "edit_data": edit_data})

	def post(self, request, user_id, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			return redirect('selfCare:user_list')
		return redirect('selfCare:edit_user' if request.POST.get("action") == "confirm" else 'selfCare:edit_screen',
						user_id=user_id)


class EditView(LoginRequiredMixin, View):
	"""ユーザー情報更新処理ビュー"""

	def get(self, request, user_id, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			return redirect('selfCare:user_list')
		edit_data = request.session.get("edit_data")
		if not edit_data:
			return redirect('selfCare:user_list')

		target_user = get_object_or_404(User, id=user_id)
		target_user.email = edit_data["email"]
		target_user.user_name = edit_data["user_name"]
		if "password" in edit_data and edit_data["password"]:
			target_user.password = make_password(edit_data['password'])
		target_user.save()

		request.session.pop("edit_data", None)
		request.session.pop("target_action", None)
		request.session.pop("target_user_id", None)
		messages.success(request, "ユーザー情報が正常に編集されました")
		return redirect('selfCare:edit_complete')


class EditCompleteView(LoginRequiredMixin, TemplateView):
	template_name = "edit_complete.html"


class CreateScreenView(LoginRequiredMixin, View):
	"""ユーザー新規作成画面ビュー"""

	def get(self, request, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			return redirect('selfCare:user_list')
		create_data = request.session.get("create_data", {})
		form = UserCreateForm(initial=create_data)
		return render(request, "create.html", {"form": form})

	def post(self, request, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			return redirect('selfCare:user_list')
		form = UserCreateForm(request.POST)
		if form.is_valid():
			request.session["create_data"] = {
				"email": form.cleaned_data.get("email"),
				"user_name": form.cleaned_data.get("user_name"),
				"password": form.cleaned_data.get("password"),
				"user_role": form.cleaned_data.get("user_role"),
			}
			return redirect("selfCare:user_create_confirm")
		return render(request, "create.html", {"form": form})


class CreateConfirmView(LoginRequiredMixin, View):
	def get(self, request, *args, **kwargs):
		if request.user.user_role != User.ADMIN or not (create_data := request.session.get("create_data")):
			return redirect('selfCare:user_list')
		return render(request, "create_confirm.html", {"create_data": create_data})

	def post(self, request, *args, **kwargs):
		return redirect(
			"selfCare:user_create" if request.POST.get("action") == "confirm" else "selfCare:user_create_screen")


class CreateView(LoginRequiredMixin, View):
	def get(self, request, *args, **kwargs):
		if request.user.user_role != User.ADMIN or not (create_data := request.session.get("create_data")):
			return redirect('selfCare:user_list')

		User.objects.create(
			username=create_data["email"],
			email=create_data["email"],
			user_name=create_data["user_name"],
			password=make_password(create_data["password"]),
			user_role=create_data["user_role"],
			is_staff=(create_data["user_role"] == User.STAFF)
		)
		request.session.pop("create_data", None)
		request.session.pop("target_action", None)
		request.session.pop("target_user_id", None)
		return redirect('selfCare:user_create_complete')


class CreateCompleteView(LoginRequiredMixin, TemplateView):
	template_name = "create_complete.html"


class DeleteConfirmView(LoginRequiredMixin, View):
	def get(self, request, user_id, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			return redirect('selfCare:user_list')
		return render(request, "delete_confirm.html", {"target_user": get_object_or_404(User, id=user_id)})

	def post(self, request, user_id, *args, **kwargs):
		return redirect("selfCare:user_delete", user_id=user_id) if request.POST.get(
			"action") == "confirm" else redirect('selfCare:user_list')


class DeleteView(LoginRequiredMixin, View):
	def get(self, request, user_id, *args, **kwargs):
		if request.user.user_role != User.ADMIN:
			return redirect('selfCare:user_list')
		get_object_or_404(User, id=user_id).delete()
		request.session.pop("target_action", None)
		request.session.pop("target_user_id", None)
		return redirect('selfCare:user_delete_complete')


class DeleteCompleteView(LoginRequiredMixin, TemplateView):
	template_name = "delete_complete.html"


# グラフ作成用のヘルパー関数群
def create_chart_image(user, home_screen, data_field, title, y_label, condition_map=None, is_staff=False,
					   completion_date=None):
	plt.close('all')
	end_date = completion_date or home_screen.date
	start_date = end_date - timedelta(days=30)
	all_dates = [start_date + timedelta(days=i) for i in range(31)]

	raw_data = list(InputScreen.objects.filter(user=user, date__date__range=[start_date, end_date]).values('date__date',
																										   data_field))
	data_map = {item['date__date']: item[data_field] for item in raw_data if item['date__date'] is not None}

	dates_labels = [d.strftime("%m/%d") for d in all_dates]
	values = [data_map.get(d, None) for d in all_dates]

	if all(v is None for v in values):
		return None

	if condition_map:
		values = [condition_map.get(v) if v is not None else None for v in values]

	fig, ax = plt.subplots(figsize=(8, 10) if is_staff else (15, 9))
	if data_field == "sleep_time_hours":
		valid_idx = [i for i, v in enumerate(values) if v is not None]
		valid_val = [v for v in values if v is not None]
		ax.set_xlim(0, (end_date - start_date).days if completion_date else 30)
		if valid_val:
			ax.plot(valid_idx, valid_val, marker="o", color="lightblue", markersize=10, linewidth=2 if is_staff else 5)
		ax.set_ylim(0, 20)
		ax.set_yticks(range(0, 21, 5))
	else:
		ax.plot(dates_labels, values, marker="o", linestyle="", markersize=10, color="tomato")
		ax.set_yticks([1, 2, 3])
		ax.set_yticklabels(["✕（悪化）", "△（注意）", "〇（良好）"])
		ax.set_ylim(0.5, 3.5)

	ax.set_title(title, fontsize=20 if is_staff else 30, pad=20)
	ax.set_xlabel("日付", fontsize=20 if is_staff else 25)
	ax.set_ylabel("睡眠時間" if data_field == "sleep_time_hours" else "体調", fontsize=20 if is_staff else 25)

	ax.set_xticks(range(0, len(dates_labels), 4))
	ax.set_xticklabels(dates_labels[::4], rotation=45, ha="right", fontsize=20 if is_staff else 40)
	ax.grid(axis='y', linestyle='--')
	fig.tight_layout()

	buffer = io.BytesIO()
	fig.savefig(buffer, format="png")
	plt.close(fig)
	buffer.seek(0)
	img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
	buffer.close()
	return f'data:image/png;base64,{img_str}'


def create_bar_chart_image(labels, data, title, y_label, color="skyblue", is_staff=False):
	if not data or all(d is None for d in data):
		return None
	plt.close('all')
	plt.figure(figsize=(10, 6) if is_staff else (16, 6))
	x_pos = range(len(labels))
	plt.bar(x_pos, data, color=color)
	for i, v in enumerate(data):
		if v is not None:
			plt.text(i, v + 0.1, f'{v}h', ha='center', va='bottom', fontsize=11)
	plt.xticks(x_pos, labels)
	plt.title(title, fontsize=14, pad=20)
	plt.ylim(0, max([d for d in data if d is not None] + [0]) * 1.2 or 10)
	plt.grid(axis='both', linestyle='--', alpha=0.7)
	plt.tight_layout()

	buffer = io.BytesIO()
	plt.savefig(buffer, format="png")
	plt.close()
	buffer.seek(0)
	img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
	buffer.close()
	return f'data:image/png;base64,{img_str}'


def calculate_monthly_average_sleep(user, target_date):
	last_day = calendar.monthrange(target_date.year, target_date.month)[1]
	if target_date.day != last_day:
		return None
	start_m = date(target_date.year, target_date.month, 1)
	end_m = date(target_date.year, target_date.month, last_day)
	monthly_data = InputScreen.objects.filter(user=user, date__date__range=[start_m, end_m],
											  sleep_time_hours__isnull=False)
	if not monthly_data.exists():
		return None
	total = monthly_data.aggregate(total_sleep=Sum('sleep_time_hours'))['total_sleep']
	count = monthly_data.count()
	return round(total / count, 1) if count > 0 else None


def create_monthly_average_sleep_chart(user, end_date):
	last_day = calendar.monthrange(end_date.year, end_date.month)[1]
	if end_date.day != last_day:
		return None, "", None, [], []

	dates_labels, values = [], []
	for i in range(2, -1, -1):
		target = end_date
		if i == 1:
			target = date(target.year - 1, 12, 1) if target.month == 1 else date(target.year, target.month - 1, 1)
		elif i == 2:
			target = date(target.year - 1, target.month + 10, 1) if target.month <= 2 else date(target.year,
																								target.month - 2, 1)

		m_last = calendar.monthrange(target.year, target.month)[1]
		avg = calculate_monthly_average_sleep(user, date(target.year, target.month, m_last))
		if avg is not None:
			dates_labels.append(target.strftime("%Y年%m月"))
			values.append(avg)

	return None, "過去3ヶ月の平均睡眠時間", values[-1] if values else None, dates_labels, values


class ChartView(LoginRequiredMixin, View):
	def get(self, request, home_screen_id, chart_type, *args, **kwargs):
		home_screen = get_object_or_404(HomeScreen, id=home_screen_id)
		user_for_chart = home_screen.user
		is_staff = request.user.user_role == User.STAFF
		chart_image, title = None, ""

		if chart_type == "sleep":
			chart_image = create_chart_image(user_for_chart, home_screen, "sleep_time_hours",
											 "過去３０日間の睡眠時間の推移", "睡眠時間 (時間)", is_staff=is_staff)
			title = "睡眠時間グラフ"
		elif chart_type == "condition":
			chart_image = create_chart_image(user_for_chart, home_screen, "condition", "過去30日間の体調の推移", "体調",
											 {"✕": 1, "△": 2, "〇": 3}, is_staff=is_staff)
			title = "体調グラフ"
		elif chart_type == "monthly_average_sleep":
			_, chart_title, _, dates_labels, values = create_monthly_average_sleep_chart(user_for_chart,
																						 home_screen.date)
			if values:
				chart_image = create_bar_chart_image(dates_labels, values, chart_title, "平均睡眠時間（時間）",
													 color="teal", is_staff=is_staff)
			title = chart_title or "月間平均睡眠時間グラフ"
		else:
			messages.error(request, '無効なグラフタイプです。')
			return redirect("selfCare:calendar_list")

		if not chart_image:
			return redirect("selfCare:calendar_list")

		return render(request, "chart_detail.html",
					  {"chart_image": chart_image, "title": title, "selected_date": home_screen.date})


class InputScreenView(LoginRequiredMixin, View):
	"""勤怠・体調入力画面ビュー"""

	def get(self, request, home_screen_id, *args, **kwargs):
		home_screen = get_object_or_404(HomeScreen, id=home_screen_id)
		target_user = home_screen.user
		input_data, _ = InputScreen.objects.get_or_create(user=target_user, date=home_screen)

		form = InputScreenForm(instance=input_data, initial={'at_home': input_data.at_home}, user=request.user)
		user_role = request.user.user_role

		# 権限に応じたフィールド制御
		for name, field in form.fields.items():
			if user_role == User.CLIENT:
				if name in ['staff_comment', 'staff_entry_time', 'staff_leaving_time']:
					field.widget.attrs['disabled'] = 'disabled'
					field.required = False
			elif user_role == User.STAFF:
				if name == 'at_home':
					field.widget.attrs['disabled'] = 'disabled'
				elif name != 'staff_comment' and name not in ['staff_entry_time', 'staff_leaving_time']:
					field.widget.attrs['disabled'] = 'disabled'

		context = {
			'form': form,
			'selected_date': home_screen.date,
			'home_screen_id': home_screen_id,
			'home_screen': home_screen,
			"target_user_name": target_user.user_name,
			"user_role": user_role,
			"at_home_status": input_data.at_home,
		}
		return render(request, 'input_screen.html', context)

	def post(self, request, home_screen_id, *args, **kwargs):
		home_screen = get_object_or_404(HomeScreen, id=home_screen_id)
		input_instance, _ = InputScreen.objects.get_or_create(date=home_screen, user=home_screen.user)
		form = InputScreenForm(request.POST, instance=input_instance, user=request.user)

		if form.is_valid():
			if request.user.user_role == User.CLIENT:
				form.instance.at_home = form.cleaned_data.get('at_home', False)
				cond = form.cleaned_data.get('condition')

				modal_data = {
					'condition_detail_good': form.cleaned_data.get('condition_detail_good') if cond == '〇' else '',
					'condition_detail_caution': form.cleaned_data.get(
						'condition_detail_caution') if cond == '△' else '',
					'condition_detail_poor': form.cleaned_data.get('condition_detail_poor') if cond == '✕' else '',
				}
				request.session[f'condition_modal_data_{home_screen_id}'] = modal_data
				form.instance.condition_detail_good = modal_data['condition_detail_good']
				form.instance.condition_detail_caution = modal_data['condition_detail_caution']
				form.instance.condition_detail_poor = modal_data['condition_detail_poor']

			form.save()
			messages.success(request, f'{home_screen.date.strftime("%Y年%m月%d日")} の記録を保存しました。')
			return redirect(reverse("selfCare:complete_screen", kwargs={'home_screen_id': home_screen_id}))

		return render(request, "input_screen.html",
					  {'form': form, 'home_screen_id': home_screen_id, 'home_screen': home_screen})


class CompleteView(LoginRequiredMixin, View):
	"""登録完了画面ビュー"""

	def get(self, request, home_screen_id, *args, **kwargs):
		home_screen = get_object_or_404(HomeScreen, id=home_screen_id)
		user_role = request.user.user_role
		sleep_img, cond_img = None, None

		if user_role == User.CLIENT:
			sleep_img = create_chart_image(request.user, home_screen, "sleep_time_hours", "過去３０日間の睡眠時間の推移",
										   "睡眠時間 (時間)", completion_date=date.today())
			cond_img = create_chart_image(request.user, home_screen, "condition", "過去30日間の体調の推移", "体調",
										  {"✕": 1, "△": 2, "〇": 3}, completion_date=date.today())

		return render(request, "complete_screen.html", {
			"home_screen_id": home_screen.id,
			"selected_date": home_screen.date,
			"user_role": user_role,
			"sleep_chart_image": sleep_img,
			"condition_chart_image": cond_img,
		})


class CommentListView(LoginRequiredMixin, View):
	"""コメント一覧表示ビュー"""

	def get(self, request, home_screen_id, *args, **kwargs):
		home_screen = get_object_or_404(HomeScreen, id=home_screen_id)
		target_user = home_screen.user
		today = timezone.now().date()
		year = int(request.GET.get('year', today.year))
		month = int(request.GET.get('month', today.month))

		start_date = date(year, month, 1)
		end_date = date(year, month, calendar.monthrange(year, month)[1])

		registered_saturdays = set(
			SaturdayOpening.objects.filter(open_date__range=[start_date, end_date]).values_list('open_date', flat=True)
		)

		raw_comments = InputScreen.objects.filter(
			user=target_user,
			date__date__range=[start_date, end_date]
		).exclude(user_comment__exact='', staff_comment__exact='').order_by("date__date")

		comment_data = []
		for item in raw_comments:
			item_date = item.date.date
			if item_date.weekday() == calendar.SUNDAY:
				continue
			if item_date.weekday() == calendar.SATURDAY and item_date not in registered_saturdays:
				continue
			comment_data.append(item)

		return render(request, "comment_list.html", {
			"home_screen": home_screen,
			"selected_date": start_date,
			"comment_data": comment_data,
			"target_user": target_user,
			"current_year": year,
			"current_month": month,
		})


class SaturdayChoiceView(LoginRequiredMixin, TemplateView):
	template_name = 'saturday_choice.html'

	def dispatch(self, request, *args, **kwargs):
		if not check_staff_permission(request.user):
			messages.error(request, '権限がありません。')
			return redirect('selfCare:calendar_list')
		return super().dispatch(request, *args, **kwargs)


class SaturdayOpeningRegisterView(LoginRequiredMixin, View):
	def dispatch(self, request, *args, **kwargs):
		if not check_staff_permission(request.user):
			return redirect('selfCare:calendar_list')
		return super().dispatch(request, *args, **kwargs)

	def get(self, request, *args, **kwargs):
		return render(request, 'saturday_register.html', {'form': SaturdayOpeningForm()})

	def post(self, request, *args, **kwargs):
		form = SaturdayOpeningForm(request.POST)
		if form.is_valid():
			dates = form.cleaned_data['date_list']
			for d in dates:
				SaturdayOpening.objects.create(open_date=d, registered_by=request.user)
			messages.success(request, f"計 {len(dates)} 件の土曜開所日を登録しました。")
			return redirect('selfCare:saturday_complete')
		return render(request, 'saturday_register.html', {'form': form})


class SaturdayOpeningCompleteView(LoginRequiredMixin, TemplateView):
	template_name = 'saturday_complete.html'


class SaturdayOpeningListView(LoginRequiredMixin, View):
	def dispatch(self, request, *args, **kwargs):
		if not check_staff_permission(request.user):
			return redirect('selfCare:calendar_list')
		return super().dispatch(request, *args, **kwargs)

	def get(self, request, *args, **kwargs):
		return render(request, 'saturday_list_delete.html', {
			'saturday_openings': SaturdayOpening.objects.all().order_by('-open_date'),
			'form': SaturdayOpeningDeleteForm(),
			'delete_url': reverse_lazy('selfCare:saturday_delete_confirm')
		})

	def post(self, request, *args, **kwargs):
		form = SaturdayOpeningDeleteForm(data=request.POST)
		if form.is_valid():
			request.session['delete_ids'] = form.cleaned_data.get('selected_openings')
			return redirect('selfCare:saturday_delete_confirm')
		return render(request, 'saturday_list_delete.html',
					  {'saturday_openings': SaturdayOpening.objects.all(), 'form': form})


class SaturdayOpeningDeleteConfirmView(LoginRequiredMixin, View):
	def dispatch(self, request, *args, **kwargs):
		if not check_staff_permission(request.user):
			return redirect('selfCare:calendar_list')
		return super().dispatch(request, *args, **kwargs)

	def get(self, request, *args, **kwargs):
		delete_ids = request.session.get('delete_ids', [])
		if not delete_ids:
			return redirect('selfCare:saturday_list_delete')
		dates_to_delete = SaturdayOpening.objects.filter(id__in=delete_ids).order_by('open_date')
		return render(request, 'saturday_delete_confirm.html',
					  {'dates_to_delete': dates_to_delete, 'delete_count': len(dates_to_delete)})

	def post(self, request, *args, **kwargs):
		delete_ids = request.session.pop('delete_ids', None)
		if not delete_ids:
			return redirect('selfCare:saturday_list_delete')
		try:
			with transaction.atomic():
				count, _ = SaturdayOpening.objects.filter(id__in=delete_ids).delete()
				messages.success(request, f"計 {count} 件の土曜開所日を削除しました。")
				return redirect('selfCare:saturday_delete_complete')
		except Exception as e:
			messages.error(request, f"エラーが発生しました: {e}")
			return redirect('selfCare:saturday_list_delete')


class SaturdayOpeningDeleteView(LoginRequiredMixin, TemplateView):
	template_name = "saturday_list_delete_complete.html"