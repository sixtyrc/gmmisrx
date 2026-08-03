from django.urls import path
from . import views

urlpatterns = [
    path('', views.filter_files, name='filter_files'),
    path('download/<str:file_id>/', views.download_file, name='download_file'),
]
