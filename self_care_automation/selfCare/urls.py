from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views
from .views import (
    UserListView, CalendarListView, EditScreenView, EditConfirmView, EditView,
    CreateScreenView, CreateConfirmView, CreateView, CreateCompleteView,
    DeleteConfirmView, DeleteView, DeleteCompleteView, DetailSelectView, CommentListView,
    SaturdayOpeningRegisterView, SaturdayChoiceView, SaturdayOpeningCompleteView,
    SaturdayOpeningListView, SaturdayOpeningDeleteConfirmView, SaturdayOpeningDeleteView
)

app_name = "selfCare"

urlpatterns = [
    # 認証関連
    path("", views.user_login, name="login"),
    path("logout/", LogoutView.as_view(next_page="selfCare:login"), name="logout"),

    # ユーザー一覧・管理
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<str:action>/', UserListView.as_view(), name='user_list'),

    # カレンダー・日付詳細
    path('select/<int:home_screen_id>/', DetailSelectView.as_view(), name='detail_select'),
    path('calendar/', CalendarListView.as_view(), name='calendar_list'),
    path('calendar/<int:year>/<int:month>/<int:day>/', views.calendar_detail_view, name='calendar_detail'),

    # 土曜開所日管理
    path('saturday/choice/', SaturdayChoiceView.as_view(), name='saturday_choice'),
    path('saturday/register/', SaturdayOpeningRegisterView.as_view(), name='saturday_register'),
    path('saturday/complete/', SaturdayOpeningCompleteView.as_view(), name='saturday_complete'),
    path('saturday/delete/', SaturdayOpeningListView.as_view(), name='saturday_list_delete'),
    path('saturday/delete/confirm/', SaturdayOpeningDeleteConfirmView.as_view(), name='saturday_delete_confirm'),
    path('saturday/delete/complete/', SaturdayOpeningDeleteView.as_view(), name='saturday_delete_complete'),

    # スタッフ・管理者用詳細
    path("staff/<int:user_id>/<str:selected_date_str>/", views.StaffDetailView.as_view(), name="staff_detail"),
    path("manager/<int:user_id>/", views.AdminDetailView.as_view(), name="admin_detail"),
    path("manager_screen/<int:user_id>/<str:action>/", views.AdminScreenView.as_view(), name="admin_screen_action"),
    path("manager_screen/", views.AdminScreenView.as_view(), name="admin_screen"),
    path("manager_auth/<int:user_id>/<str:action>/", views.AdminScreenView.as_view(), name="admin_auth_action"),
    path("manager_auth/", views.AdminScreenView.as_view(), name="admin_auth"),
    path("manager_screen/<int:user_id>/user_auth/edit/", views.UserAuthView.as_view(), {'action': 'edit'}, name="user_edit_auth"),

    # ユーザー編集フロー
    path('edit/<int:user_id>/', EditScreenView.as_view(), name='edit_screen'),
    path('edit/<int:user_id>/confirm/', EditConfirmView.as_view(), name='edit_confirm'),
    path('edit/<int:user_id>/user/', EditView.as_view(), name='edit_user'),
    path('edit/complete/', views.EditCompleteView.as_view(), name='edit_complete'),

    # ユーザー新規作成フロー
    path('create/screen/', CreateScreenView.as_view(), name='user_create_screen'),
    path('create/confirm/', CreateConfirmView.as_view(), name='user_create_confirm'),
    path('create/save/', CreateView.as_view(), name='user_create'),
    path('create/complete/', CreateCompleteView.as_view(), name='user_create_complete'),

    # ユーザー削除フロー
    path("delete/<int:user_id>/user_auth/delete/", views.UserAuthView.as_view(), {'action': 'delete'}, name="user_delete_auth"),
    path('delete/<int:user_id>/confirm/', DeleteConfirmView.as_view(), name='delete_confirm'),
    path('delete/<int:user_id>/', DeleteView.as_view(), name='user_delete'),
    path('delete/complete/', DeleteCompleteView.as_view(), name='delete_complete'),

    # 勤怠入力・グラフ・コメント
    path('input/<int:home_screen_id>/', views.InputScreenView.as_view(), name='input_screen'),
    path('input/<int:home_screen_id>/chart/<str:chart_type>/', views.ChartView.as_view(), name='chart_detail'),
    path('complete/<int:home_screen_id>/', views.CompleteView.as_view(), name='complete_screen'),
    path('comments/<int:home_screen_id>/', CommentListView.as_view(), name='comment_list'),
]