import logging
import re
from django.db import DatabaseError, transaction
from django.templatetags.static import static
from .models import WebAppearance, PrintIdentity, BrandImage
from .specs import DEFAULT_COLORS, SLOTS

logger=logging.getLogger(__name__)
WEB_SLOTS=('site_logo','login_logo','favicon','footer')
PRINT_SLOTS=('print_left','print_right')


def defaults(slots):
    return {slot:static('plantilla/img/'+SLOTS[slot][1]) for slot in slots}


def web_branding():
    result={**DEFAULT_COLORS,**defaults(WEB_SLOTS)}
    try:
        with transaction.atomic():
            config=WebAppearance.objects.select_related(*WEB_SLOTS).filter(pk=1).first()
        if config:
            result.update({key:getattr(config,key) for key in DEFAULT_COLORS if re.fullmatch(r'#[0-9a-fA-F]{6}',getattr(config,key) or '')})
            result.update({slot:getattr(config,slot).public_url for slot in WEB_SLOTS if getattr(config,slot)})
    except DatabaseError:
        # Durante despliegues o fallos de BD, conservar la apariencia original.
        pass
    return result


def print_branding(year):
    result=defaults(PRINT_SLOTS)
    try:
        with transaction.atomic():
            profile=PrintIdentity.objects.select_related(*PRINT_SLOTS).filter(year=year).first()
        if profile:
            result.update({slot:getattr(profile,slot).public_url for slot in PRINT_SLOTS if getattr(profile,slot)})
    except DatabaseError:
        pass
    return result


def cleanup(files):
    for storage,name in files:
        try: storage.delete(name)
        except Exception: logger.exception('No se pudo limpiar una imagen nueva tras un fallo')


def save_appearance(instance,uploads,reset=False,user=None,created_files=None):
    created_files=created_files if created_files is not None else []
    slots=WEB_SLOTS if isinstance(instance,WebAppearance) else PRINT_SLOTS
    try:
        with transaction.atomic():
            if reset:
                for slot in slots:setattr(instance,slot,None)
                if isinstance(instance,WebAppearance):
                    for field,value in DEFAULT_COLORS.items():setattr(instance,field,value)
            for slot,upload in uploads.items():
                if upload:
                    image=BrandImage(slot=slot,file=upload)
                    try:
                        image.save()
                    finally:
                        if image.file and image.file._committed:
                            created_files.append((image.file.storage,image.file.name))
                    setattr(instance,slot,image)
            if user is not None:instance.updated_by=user
            instance.full_clean()
            instance.save()
        return instance
    except Exception:
        cleanup(created_files)
        raise
