from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('padron/', include('padron.urls')),
    # Padron es la pantalla principal del panel; la herramienta legacy (solo
    # admin) vive en su propia ruta, ya no se cuelga de la raiz del sitio.
    path('', RedirectView.as_view(pattern_name='padron:dashboard', permanent=False)),
    path('legacy/', include('processor.urls')),
]
