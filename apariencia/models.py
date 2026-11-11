import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.urls import reverse
from .specs import SLOTS, DEFAULT_COLORS
from .validators import validate_image, contrast

color_validator=RegexValidator(r'^#[0-9a-fA-F]{6}$','Usa un color hexadecimal de seis dígitos, por ejemplo #682145.')


def image_path(instance,filename):
    return f'identidad/{instance.pk}.{instance.mime.rsplit("/",1)[-1].replace("svg+xml","svg").replace("jpeg","jpg")}'


class BrandImage(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    slot=models.CharField('Uso de la imagen',max_length=20,choices=[(key,value[0]) for key,value in SLOTS.items()])
    file=models.FileField('Imagen',upload_to=image_path)
    width=models.DecimalField(max_digits=9,decimal_places=2,editable=False)
    height=models.DecimalField(max_digits=9,decimal_places=2,editable=False)
    mime=models.CharField(max_length=30,editable=False)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name='Imagen de identidad'
        verbose_name_plural='Imágenes de identidad'

    def save(self,*args,**kwargs):
        if not self._state.adding: raise ValidationError('Las imágenes guardadas son inmutables. Sube una nueva versión.')
        info=validate_image(self.file,self.slot)
        self.width,self.height,self.mime=info['width'],info['height'],info['mime']
        return super().save(*args,**kwargs)

    @property
    def public_url(self):
        return reverse('apariencia:image',kwargs={'image_id':self.pk})


class WebAppearance(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    primary=models.CharField('Color institucional',max_length=7,default=DEFAULT_COLORS['primary'],validators=[color_validator])
    action=models.CharField('Botones principales',max_length=7,default=DEFAULT_COLORS['action'],validators=[color_validator])
    background=models.CharField('Fondo de la página',max_length=7,default=DEFAULT_COLORS['background'],validators=[color_validator])
    text=models.CharField('Texto principal',max_length=7,default=DEFAULT_COLORS['text'],validators=[color_validator])
    accent=models.CharField('Color secundario y gráficas',max_length=7,default=DEFAULT_COLORS['accent'],validators=[color_validator])
    site_logo=models.ForeignKey(BrandImage,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    login_logo=models.ForeignKey(BrandImage,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    favicon=models.ForeignKey(BrandImage,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    footer=models.ForeignKey(BrandImage,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    updated_at=models.DateTimeField(auto_now=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)

    class Meta:
        verbose_name='Apariencia de la página'
        verbose_name_plural='Apariencia de la página'

    def __str__(self): return 'Colores e imágenes de la página'

    def clean(self):
        if self.pk!=1: raise ValidationError('Solo puede existir una configuración de la página.')
        for name in ('primary','action','accent'):
            value=getattr(self,name)
            if color_validator.regex.fullmatch(value or '') and contrast(value,'#ffffff')<3:
                raise ValidationError('Los colores institucional, de botones y secundario deben contrastar al menos 3:1 con las tarjetas blancas.')
        if all(color_validator.regex.fullmatch(value or '') for value in [self.text,self.background]):
            if min(contrast(self.text,self.background),contrast(self.text,'#ffffff'))<4.5:
                raise ValidationError('El texto debe contrastar al menos 4.5:1 con el fondo y con las tarjetas blancas.')


class PrintIdentity(models.Model):
    year=models.PositiveIntegerField('Año',unique=True,validators=[MinValueValidator(1000),MaxValueValidator(9999)])
    print_left=models.ForeignKey(BrandImage,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    print_right=models.ForeignKey(BrandImage,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    updated_at=models.DateTimeField(auto_now=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)

    class Meta:
        verbose_name='Imágenes del formato imprimible por año'
        verbose_name_plural='Imágenes del formato imprimible por año'
        ordering=['-year']

    def clean(self):
        if self.pk:
            previous=type(self).objects.filter(pk=self.pk).values_list('year',flat=True).first()
            if previous is not None and previous!=self.year:
                raise ValidationError('El año del perfil no se puede cambiar. Crea otro perfil para el nuevo año.')

    def __str__(self): return f'Imágenes del formato · {self.year}'
