import base64
import logging
from datetime import date
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from .forms import WebAppearanceForm, PrintIdentityForm
from .models import WebAppearance, PrintIdentity
from .services import WEB_SLOTS, PRINT_SLOTS, defaults, print_branding, save_appearance
from .specs import SLOTS
from .validators import validate_image
from django.http import HttpResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_safe
from .models import BrandImage
from .services import web_branding
from .specs import DEFAULT_COLORS
from .validators import on_color, contrast


def mix(color,black=.25):
    return '#'+''.join(f'{round(int(color[index:index+2],16)*(1-black)):02x}' for index in (1,3,5))


def css_text(brand):
    primary,action=brand['primary'],brand['action']
    ink=primary if contrast(primary,'#ffffff')>=4.5 else mix(primary,.6)
    extra=''
    if primary!=DEFAULT_COLORS['primary']:
        for shade in ['f6eaf0','f7eaf1','f7edf2','faf0f5','faf4f7','fbf0f5','f4e3eb','f1dde7','f0d9e4','f4e4ec','e8ccda','dbb5c8']:
            extra+=f'--ivem-tone-{shade}:color-mix(in srgb, {primary} 10%, white);'
        extra+=f'--ivem-focus:{primary};--ivem-deep:{mix(primary,.3)};'
    # Las URLs se generan con UUID del servidor, no con nombres o CSS del usuario.
    return f''':root{{{extra}--ivem-primary:{primary};--ivem-primary-ink:{ink};--ivem-action:{action};
--ivem-background:{brand['background']};--ivem-text:{brand['text']};--ivem-accent:{brand['accent']};
--ivem-on-primary:{on_color(primary)};--ivem-on-action:{on_color(action)};
--ivem-primary-dark:{'#4e1734' if primary==DEFAULT_COLORS['primary'] else mix(primary,.25)};
--ivem-primary-soft:{'#7b3154' if primary==DEFAULT_COLORS['primary'] else primary};
--ivem-footer-image:url("{brand['footer']}");}}
.btn-primary{{--bs-btn-bg:{action};--bs-btn-border-color:{action};--bs-btn-color:{on_color(action)};
--bs-btn-hover-bg:{mix(action,.15)};--bs-btn-hover-border-color:{mix(action,.15)};--bs-btn-hover-color:{on_color(mix(action,.15))};
--bs-btn-active-bg:{mix(action,.2)};--bs-btn-active-border-color:{mix(action,.2)};--bs-btn-active-color:{on_color(mix(action,.2))};
--bs-btn-disabled-bg:{action};--bs-btn-disabled-border-color:{action};--bs-btn-disabled-color:{on_color(action)};}}
.btn-outline-primary{{--bs-btn-color:{action};--bs-btn-border-color:{action};--bs-btn-hover-bg:{action};--bs-btn-hover-border-color:{action};--bs-btn-hover-color:{on_color(mix(action,.15))};}}
.custom-navbar .nav-link,.custom-navbar .navbar-brand,.modal-header,.login-brand-panel,
.login-brand-copy > p,.login-brand-copy ul,.login-brand-footer,.account-label small{{color:var(--ivem-on-primary)!important;}}
.account-avatar{{background:var(--ivem-on-primary);color:{primary};}}
.modal-header .btn-close{{filter:{'invert(1) grayscale(100%) brightness(200%)' if on_color(primary)=='#ffffff' else 'none'};}}
.document-file-icon,.dashboard-metric-icon,.document-eyebrow,.folio-modal legend,
#formularioPopup legend,.document-list-bottom .page-link{{color:var(--ivem-primary-ink);}}
.document-list-bottom .active > .page-link,.document-table th{{color:var(--ivem-on-primary);}}
'''


@require_safe
def theme(request):
    response=HttpResponse(css_text(web_branding()),content_type='text/css; charset=utf-8')
    response['Cache-Control']='no-cache'
    response['X-Content-Type-Options']='nosniff'
    return response


@require_safe
def image(request,image_id):
    asset=get_object_or_404(BrandImage,pk=image_id)
    try:stream=asset.file.storage.open(asset.file.name,'rb')
    except OSError:raise Http404('Imagen no disponible.')
    response=FileResponse(stream,content_type=asset.mime)
    response['X-Content-Type-Options']='nosniff'
    response['Content-Security-Policy']="sandbox; default-src 'none'; style-src 'unsafe-inline'"
    response['Cache-Control']='public, max-age=31536000, immutable'
    return response


@login_required
@require_http_methods(['GET', 'POST'])
def configure(request):
    can_web = request.user.has_perm('apariencia.change_webappearance')
    can_print = request.user.has_perm('apariencia.change_printidentity') or request.user.has_perm('apariencia.add_printidentity')
    if not (can_web or can_print):
        raise PermissionDenied
    section = request.GET.get('section', 'web' if can_web else 'print')
    if section not in {'web', 'print'}:
        raise Http404
    is_web = section == 'web'
    if not (can_web if is_web else can_print):
        raise PermissionDenied
    year_form = PrintIdentityForm() if not is_web else None
    year = None
    if not is_web:
        choices = [value for value, label in year_form.fields['year'].choices if value != '']
        raw_year = request.GET.get('year', str(choices[0]) if choices else '')
        try:
            year = int(raw_year)
        except (ValueError, TypeError):
            if raw_year:
                raise Http404
        if year is not None and year not in choices:
            raise Http404
    instance = (WebAppearance.objects.filter(pk=1).first() or WebAppearance()) if is_web else (
        PrintIdentity.objects.filter(year=year).first() or PrintIdentity(year=year))
    editable = can_web if is_web else request.user.has_perm(
        'apariencia.change_printidentity' if instance.pk else 'apariencia.add_printidentity')
    if request.method == 'POST' and not editable:
        raise PermissionDenied
    form_type = WebAppearanceForm if is_web else PrintIdentityForm
    form = form_type(request.POST if request.method == 'POST' else None,
                     request.FILES if request.method == 'POST' else None, instance=instance)
    if not is_web:
        # El año pertenece a la URL seleccionada, nunca al contenido enviado.
        form.fields['year'].disabled = True
        form.fields['year'].widget = forms.HiddenInput()
    preview = False
    preview_html = ''
    slots = WEB_SLOTS if is_web else PRINT_SLOTS
    urls = web_branding() if is_web else print_branding(year)
    colors = {key: getattr(instance, key) for key in DEFAULT_COLORS} if is_web else {}
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        preview = '_preview' in request.POST
        if preview:
            if obj._restore_defaults:
                urls.update(defaults(slots))
            for slot, upload in obj._pending_images.items():
                if upload:
                    info = validate_image(upload, slot)
                    urls[slot] = 'data:' + info['mime'] + ';base64,' + base64.b64encode(upload.read()).decode()
                    upload.seek(0)
            if is_web:
                colors = DEFAULT_COLORS.copy() if obj._restore_defaults else {key: getattr(obj, key) for key in DEFAULT_COLORS}
            else:
                preview_html = render_to_string('documento/formato_oficio.html', {
                    'print_preview': True, 'print_branding': urls,
                    'data': {'fecha_recibido': date(year, 1, 1), 'fecha_oficio': date(year, 1, 1),
                             'folio': '000', 'enviado_por': 'Remitente de ejemplo',
                             'asunto': 'Vista previa: se conservan las medidas originales.'}})
        else:
            try:
                save_appearance(obj, obj._pending_images, obj._restore_defaults, request.user)
            except DatabaseError:
                logging.getLogger(__name__).exception('No se pudo guardar la apariencia')
                form.add_error(None, 'No se pudieron guardar los cambios. Intenta de nuevo.')
            else:
                messages.success(request, 'Apariencia e identidad actualizada correctamente.')
                return redirect(request.get_full_path())
    return render(request, 'apariencia/configure.html', {
        'form': form, 'section': section, 'can_web': can_web, 'can_print': can_print,
        'editable': editable and (is_web or year is not None), 'year': year,
        'years': year_form.fields['year'].choices if year_form else [],
        'images': [(SLOTS[slot][0], urls[slot]) for slot in slots],
        'colors': colors, 'preview': preview, 'preview_html': preview_html,
        'on_action': on_color(colors['action']) if colors else '',
    })
