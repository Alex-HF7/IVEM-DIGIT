from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from documento import views as viewsDoc
from django.contrib.auth.decorators import login_required


urlpatterns = [

    #Admin y Autenticacion
    path('admin/', admin.site.urls),
    path('', auth_views.LoginView.as_view(template_name='login/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    #Dashboard / Inicio
    path('inicio/', login_required(viewsDoc.grafica), name='inicio'),

    #Manjeo de oficios por depto y año
    path('oficios/<str:depto>/<int:year>/', login_required(viewsDoc.lista_oficios), name='lista_oficios'),
    path('oficios/<str:depto>/<int:year>/crear/', login_required(viewsDoc.crear_oficio), name='crear_oficio'),
    path('oficios/imprimir/<str:depto>/<int:year>/<int:record_id>/', login_required(viewsDoc.imprimir_oficio), name='imprimir_oficio'),
    path('oficio/<str:depto>/<int:year>/<int:id>/editar',login_required(viewsDoc.editar_oficio), name='editar_oficio'),
    path('oficios/<str:depto>/<int:year>/<int:id>/eliminar/', login_required(viewsDoc.eliminar_oficio), name='eliminar_oficio'),
    
    #Pendientes
    path('oficios/pendientes/', login_required(viewsDoc.lista_pendientes), name='lista_pendientes'),
    path('pendientes/asignar-folio/', login_required(viewsDoc.asignar_folio), name='asignar_folio'),
    
    #Archivos
    path('manejar-archivo/', login_required(viewsDoc.archivo), name="manejar_archivo"),
    
]
if settings.DEBUG:
    from django.conf.urls.static import static 
    urlpatterns += static(settings.MEDIA_URL, 
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, 
                          document_root=settings.STATIC_ROOT)