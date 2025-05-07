from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from documento import views as viewsDoc
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', auth_views.LoginView.as_view(template_name='login/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('list/', viewsDoc.list, name='list'),
    path('oficios/<str:depto>/<int:year>/', viewsDoc.lista_oficios, name='lista_oficios'),
    path('oficios/<str:depto>/<int:year>/crear/', viewsDoc.crear_oficio, name='crear_oficio'),
    path('oficios/<str:depto>/<int:year>/<int:oficio_id>/actualizar/', viewsDoc.actualizar_pendiente, name='actualizar_pendiente'),
    path('inicio/', viewsDoc.grafica, name='inicio'),
    #path('oficios/<str:depto>/<int:year>/<int:oficio_id>/subir-archivo/', viewsDoc.subir_archivo, name='upload'),
    #path('oficios/<str:depto>/<int:year>/<int:oficio_id>/descargar/', viewsDoc.descargar_archivo, name='dowland'),
]
if settings.DEBUG:
    from django.conf.urls.static import static 
    urlpatterns += static(settings.MEDIA_URL, 
                          document_root=settings.MEDIA_ROOT)