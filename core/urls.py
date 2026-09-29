from django.urls import path

from . import views

urlpatterns = [
    # public
    path("", views.landing, name="landing"),
    path("lang/<str:lang>/", views.set_language, name="set_language"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # app
    path("app/", views.dashboard, name="dashboard"),
    path("app/summarize/", views.summarize_page, name="summarize"),
    path("app/batch/", views.batch_page, name="batch"),
    path("app/tools/", views.tools_page, name="tools"),
    path("app/history/", views.history, name="history"),
    path("app/history/export/", views.history_export, name="history_export"),
    path("app/history/<int:pk>/", views.history_detail, name="history_detail"),
    path("app/history/<int:pk>/delete/", views.history_delete, name="history_delete"),
    path("app/history/<int:pk>/favorite/", views.history_favorite, name="history_favorite"),
    path("app/history/<int:pk>/download/", views.history_download, name="history_download"),
    path("app/api-status/", views.api_status_page, name="api_status"),
    path("app/settings/", views.settings_page, name="settings"),
    path("app/users/", views.users_page, name="users"),
    path("app/users/<int:pk>/toggle-staff/", views.user_toggle_staff, name="user_toggle_staff"),

    # internal JSON endpoints used by the UI
    path("app/api/summarize/", views.api_summarize, name="api_summarize"),
    path("app/api/batch/", views.api_batch, name="api_batch"),
    path("app/api/tool/<str:tool>/", views.api_tool, name="api_tool"),
    path("app/api/extract/", views.api_extract, name="api_extract"),
    path("app/api/health/", views.api_health_json, name="api_health"),
]
