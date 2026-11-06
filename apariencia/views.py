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
--bs-btn-hover-bg:{mix(action,.15)};--bs-btn-hover-border-color:{mix(action,.15)};--bs-btn-hover-color:{on_color(action)};
--bs-btn-active-bg:{mix(action,.2)};--bs-btn-active-border-color:{mix(action,.2)};--bs-btn-active-color:{on_color(action)};
--bs-btn-disabled-bg:{action};--bs-btn-disabled-border-color:{action};--bs-btn-disabled-color:{on_color(action)};}}
.btn-outline-primary{{--bs-btn-color:{action};--bs-btn-border-color:{action};--bs-btn-hover-bg:{action};--bs-btn-hover-border-color:{action};--bs-btn-hover-color:{on_color(action)};}}
.custom-navbar .nav-link,.custom-navbar .navbar-brand,.modal-header,.login-brand-panel,
.login-brand-copy > p,.login-brand-copy ul,.login-brand-footer,.account-label small{{color:var(--ivem-on-primary)!important;}}
.account-avatar{{background:var(--ivem-on-primary);color:{primary};}}
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
