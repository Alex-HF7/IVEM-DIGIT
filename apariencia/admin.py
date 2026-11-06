import base64
import logging
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.shortcuts import render, redirect
from django.utils.html import format_html
from .models import WebAppearance, PrintIdentity
from .forms import WebAppearanceForm, PrintIdentityForm
from .services import save_appearance, cleanup, web_branding, print_branding
from .specs import SLOTS, DEFAULT_COLORS
from .validators import on_color, validate_image

logger=logging.getLogger(__name__)


class AppearanceAdmin(admin.ModelAdmin):
    change_form_template='admin/apariencia/change_form.html'
    readonly_fields=('updated_at','updated_by','current_images')

    def has_delete_permission(self,request,obj=None):return False

    @admin.display(description='Imágenes actuales')
    def current_images(self,obj):
        from .services import defaults
        urls=defaults(self.form.slots) if obj is None else (web_branding() if isinstance(obj,WebAppearance) else print_branding(obj.year))
        from django.utils.html import format_html_join
        return format_html_join('', '<div class="appearance-current"><p>{}</p><img src="{}" alt="{}"></div>',
            ((SLOTS[slot][0],urls[slot],SLOTS[slot][0]) for slot in self.form.slots))

    def save_model(self,request,obj,form,change):
        save_appearance(obj,obj._pending_images,obj._restore_defaults,request.user,request._appearance_files)

    def changeform_view(self,request,object_id=None,form_url='',extra_context=None):
        request._appearance_files=[]
        try:
            if request.method=='POST' and '_preview' in request.POST:
                obj=self.get_object(request,object_id) if object_id else None
                if not (self.has_change_permission(request,obj) if obj else self.has_add_permission(request)):
                    raise PermissionDenied
                form=self.get_form(request,obj)(request.POST,request.FILES,instance=obj)
                if form.is_valid():
                    instance=form.save(commit=False)
                    is_web=isinstance(instance,WebAppearance)
                    urls=web_branding() if is_web else print_branding(instance.year)
                    if form.cleaned_data.get('restore_defaults'):
                        from .services import defaults
                        urls.update(defaults(self.form.slots))
                    for slot in self.form.slots:
                        upload=form.cleaned_data.get(slot+'_upload')
                        if upload:
                            info=validate_image(upload,slot)
                            urls[slot]='data:'+info['mime']+';base64,'+base64.b64encode(upload.read()).decode()
                            upload.seek(0)
                    colors={key:getattr(instance,key) for key in DEFAULT_COLORS} if is_web else {}
                    if is_web and form.cleaned_data.get('restore_defaults'):colors=DEFAULT_COLORS.copy()
                    print_preview_html=''
                    if not is_web:
                        from django.template.loader import render_to_string
                        from datetime import date
                        print_preview_html=render_to_string('documento/formato_oficio.html',{
                            'print_preview':True,'print_branding':urls,
                            'data':{'fecha_recibido':date(instance.year,1,1),'fecha_oficio':date(instance.year,1,1),
                                    'enviado_por':'Ejemplo de remitente','area':'Área de ejemplo','asunto':'Vista previa del formato: se conservan sus espacios originales.',
                                    'procedencia':'Dependencia de ejemplo','referencia':'Ejemplo','asunto_opciones':'Conocimiento','folio':'000','nota':'Datos ficticios de vista previa.'},
                        })
                    return render(request,'admin/apariencia/preview.html',{
                        **self.admin_site.each_context(request),'title':'Vista previa de identidad',
                        'web':is_web,'images':[(SLOTS[slot][0],urls[slot]) for slot in self.form.slots],
                        'print_branding':urls,'colors':colors,'print_preview_html':print_preview_html,
                        'on_action':on_color(colors['action']) if is_web else '',
                    })
            return super().changeform_view(request,object_id,form_url,extra_context)
        except DatabaseError:
            cleanup(request._appearance_files)
            logger.exception('No se pudo guardar la configuración de apariencia')
            self.message_user(request,'No se pudieron guardar los cambios. La configuración anterior se conserva.',messages.ERROR)
            return redirect(request.path)
        except Exception:
            cleanup(request._appearance_files)
            raise

    class Media:
        css={'all':('apariencia/admin.css',)}


@admin.register(WebAppearance)
class WebAppearanceAdmin(AppearanceAdmin):
    form=WebAppearanceForm
    fieldsets=(
        ('Colores de la página',{'fields':tuple(DEFAULT_COLORS)}),
        ('Imágenes de la página',{'fields':('current_images','site_logo_upload','login_logo_upload','favicon_upload','footer_upload')}),
        ('Restaurar',{'fields':('restore_defaults',)}),
        ('Último cambio',{'fields':('updated_at','updated_by')}),
    )
    def has_add_permission(self,request):
        return super().has_add_permission(request) and not WebAppearance.objects.exists()


@admin.register(PrintIdentity)
class PrintIdentityAdmin(AppearanceAdmin):
    form=PrintIdentityForm
    list_display=('year','updated_at','updated_by')
    fieldsets=(
        ('Año del formato',{'fields':('year',)}),
        ('Solo imágenes: el diseño de impresión es fijo',{'fields':('current_images','print_left_upload','print_right_upload'),
         'description':'Se conservan papel carta, márgenes, posiciones, tipografía, sello y ambas copias. Cada logo mantiene 40 px de alto y 120 px de ancho máximo.'}),
        ('Restaurar',{'fields':('restore_defaults',)}),
        ('Último cambio',{'fields':('updated_at','updated_by')}),
    )
    def get_readonly_fields(self,request,obj=None):
        return self.readonly_fields+(('year',) if obj else ())
