from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "padron"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("ejecutar/", views.ejecutar_ahora, name="ejecutar_ahora"),
    path("login/", auth_views.LoginView.as_view(template_name="padron/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="padron:login"), name="logout"),
]
