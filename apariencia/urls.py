from django.urls import path
from . import views
app_name='apariencia'
urlpatterns=[path('tema.css',views.theme,name='theme'),path('imagen/<uuid:image_id>/',views.image,name='image')]
