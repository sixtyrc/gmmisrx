from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "padron"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("ejecutar/", views.ejecutar_ahora, name="ejecutar_ahora"),
    path("cronicos/", views.cronicos, name="cronicos"),
    path("cronicos/abm/", views.cronicos_abm, name="cronicos_abm"),
    path("cronicos/buscar/monodroga/", views.cronicos_buscar_monodroga, name="cronicos_buscar_monodroga"),
    path("cronicos/buscar/producto/", views.cronicos_buscar_producto, name="cronicos_buscar_producto"),
    path("cronicos/buscar/patologia/", views.cronicos_buscar_patologia, name="cronicos_buscar_patologia"),
    path("cronicos/vademecum/actualizar/", views.cronicos_vademecum_actualizar, name="cronicos_vademecum_actualizar"),
    path("cronicos/rollback/", views.cronicos_rollback, name="cronicos_rollback"),
    path("consumos/", views.consumos, name="consumos"),
    path("login/", auth_views.LoginView.as_view(template_name="padron/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="padron:login"), name="logout"),
]
