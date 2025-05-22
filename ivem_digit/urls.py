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
    #path('oficios/subir/', viewsDoc.cargar_archivo, name='subir'),
    path('manejar-archivo/', viewsDoc.archivo, name="manejar_archivo"),
    path('inicio/', viewsDoc.grafica, name='inicio'),
    path('oficios/pendientes/', viewsDoc.lista_pendientes, name='lista_pendientes'),
    path('pendientes/asignar-folio/', viewsDoc.asignar_folio, name='asignar_folio'),
    path('oficios/imprimir/<str:depto>/<int:year>/<int:record_id>/', viewsDoc.imprimir_oficio, name='imprimir_oficio'),
    path('oficio/<str:depto>/<int:year>/<int:id>/editar', viewsDoc.editar_oficio, name='editar_oficio'),
    path('oficios/<str:depto>/<int:year>/<int:id>/eliminar/', viewsDoc.eliminar_oficio, name='eliminar_oficio'),
]
if settings.DEBUG:
    from django.conf.urls.static import static 
    urlpatterns += static(settings.MEDIA_URL, 
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, 
                          document_root=settings.STATIC_ROOT)