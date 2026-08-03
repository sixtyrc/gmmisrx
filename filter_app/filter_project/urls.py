from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('padron/', include('padron.urls')),
    path('', include('processor.urls')),
]
