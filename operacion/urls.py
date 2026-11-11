from django.urls import path
from . import views
app_name = 'operacion'
urlpatterns = [path('usuarios/', views.users, name='users'), path('carpetas/', views.folders, name='folders')]
