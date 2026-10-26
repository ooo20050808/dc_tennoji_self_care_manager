""""""
from django.urls import path
from . import views
from .views import UserListView, CalendarListView
from .views import EditScreenView, EditConfirmView, EditView
from django.contrib.auth.views import LogoutView# ログアウトビューをインポート
from .views import CreateScreenView, CreateConfirmView, CreateView, CreateCompleteView
from .views import DeleteConfirmView, DeleteView, DeleteCompleteView
from .views import DetailSelectView, CommentListView
from .views import SaturdayOpeningRegisterView, SaturdayChoiceView, SaturdayOpeningCompleteView, SaturdayOpeningListView, SaturdayOpeningDeleteConfirmView, SaturdayOpeningDeleteView


#Djangoアプリケーション用のルーティング
app_name = "selfCare"
urlpatterns = [
    # ログインページ
    path("", views.user_login, name="login"),
    # ログアウトpページ
    path("logout/", LogoutView.as_view(next_page="selfCare:login"), name="logout"),
    # アクションなし（通常のユーザーリスト）
    path('users/', UserListView.as_view(), name='user_list'),
    # 利用者一覧ページ
    path('users/<str:action>/', UserListView.as_view(), name='user_list'),
    #画面選択ページ（コメント一覧か入力画面か）
    path('select/<int:home_screen_id>/', DetailSelectView.as_view(), name='detail_select'),
    #カレンダー一覧か土曜日開所登録画面かどちらに遷移するか選択するページ
    path('saturday/choice/', views.SaturdayChoiceView.as_view(), name='saturday_choice'),
    # カレンダー一覧ページ
    path('calendar/', CalendarListView.as_view(), name='calendar_list'),
    # カレンダーの日付クリック時の詳細ページ
    path('calendar/<int:year>/<int:month>/<int:day>/', views.calendar_detail_view, name='calendar_detail'),
    # 土曜開所日登録ページ
    path('saturday/register/', SaturdayOpeningRegisterView.as_view(), name='saturday_register'),
    #土曜開所日登録完了ページを追加
    path('saturday/complete/', SaturdayOpeningCompleteView.as_view(), name='saturday_complete'),
    #土曜開所日一覧表示ビュー (削除対象選択用)
    path('saturday/delete/', SaturdayOpeningListView.as_view(), name='saturday_list_delete'),
    #土曜開所日 削除確認・実行ビュー
    path('saturday/delete/confirm/', SaturdayOpeningDeleteConfirmView.as_view(), name='saturday_delete_confirm'),
    #土曜開所日 削除完了ビュー
    path('saturday/delete/complete/', SaturdayOpeningDeleteView.as_view(), name='saturday_delete_complete'),
    # スタッフ用詳細ページ
    path("staff/<int:user_id>/<str:selected_date_str>/", views.StaffDetailView.as_view(), name="staff_detail"),
    # 管理者用画面ページ
    path("admin/<int:user_id>/", views.AdminDetailView.as_view(), name="admin_detail"),
    #アクションありのパスに一意の名前 'admin_screen_action' を指定
    path("admin_screen/<int:user_id>/<str:action>/", views.AdminScreenView.as_view(), name="admin_screen_action"),
    # アクションなしのパスに 'admin_screen' を残す (user_list.htmlで使用)
    path("admin_screen/", views.AdminScreenView.as_view(), name="admin_screen"),
    # アクションありの管理者認証パス (編集/削除時の管理者の再認証)
    path("admin_auth/<int:user_id>/<str:action>/", views.AdminScreenView.as_view(), name="admin_auth_action"),
    # user_id を持たないパターン (新規作成用)
    path("admin_auth/", views.AdminScreenView.as_view(), name="admin_auth"),
    # ユーザー認証ページ（編集用）
    path("admin_screen/<int:user_id>/user_auth/edit/", views.UserAuthView.as_view(), {'action': 'edit'}, name="user_edit_auth"),
    # ユーザー編集画面ページ
    path('edit/<int:user_id>/', EditScreenView.as_view(), name='edit_screen'),
    # ユーザー編集確認ぺージ
    path('edit/<int:user_id>/confirm/', EditConfirmView.as_view(), name='edit_confirm'),
    # ユーザー情報更新ページ
    path('edit/<int:user_id>/user/', EditView.as_view(), name='edit_user'),
    # 編集完了ページ
    path('edit/complete/', views.EditCompleteView.as_view(), name='edit_complete'),
    # ユーザー新規作成画面ページ
    # user_create/admin_auth/ で認証成功後にここにリダイレクト
    path('create/screen/', CreateScreenView.as_view(), name='user_create_screen'),
    # ユーザー新規作成確認ページ
    path('create/confirm/', CreateConfirmView.as_view(), name='user_create_confirm'),
    # ユーザー新規作成処理ページ
    path('create/save/', CreateView.as_view(), name='user_create'),
    # ユーザー新規作成完了ページ
    path('create/complete/', CreateCompleteView.as_view(), name='user_create_complete'),
    # ユーザー削除認証ページ
    path("delete/<int:user_id>/user_auth/delete/", views.UserAuthView.as_view(), {'action': 'delete'}, name="user_delete_auth"),
    # ユーザー削除確認ページ
    path('delete/<int:user_id>/confirm/', DeleteConfirmView.as_view(), name='user_delete_confirm'),
    # ユーザー削除処理ページ
    path('delete/<int:user_id>/', DeleteView.as_view(), name='user_delete'),
    # ユーザー削除完了ページ
    path('delete/complete/', DeleteCompleteView.as_view(), name='user_delete_complete'),
    # 入力画面ページ
    path('input/<int:home_screen_id>/', views.InputScreenView.as_view(), name='input_screen'),
    # グラフ表示ページ
    path('input/<int:home_screen_id>/chart/<str:chart_type>/', views.ChartView.as_view(), name='chart_detail'),
    # 登録完了画面ページ (グラフも表示)
    path('complete/<int:home_screen_id>/', views.CompleteView.as_view(), name='complete_screen'),
    #コメント一覧画面ページ
    path('comments/<int:home_screen_id>/', CommentListView.as_view(), name='comment_list'),
]