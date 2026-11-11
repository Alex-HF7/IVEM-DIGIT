from django import forms
from django.core.exceptions import ValidationError
from gestion_tables.models import ConfiguracionTable
from .models import WebAppearance, PrintIdentity
from .specs import DEFAULT_COLORS, SLOTS, image_help
from .validators import validate_image
from .services import WEB_SLOTS, PRINT_SLOTS, save_appearance


def image_field(slot):
    return forms.FileField(label=SLOTS[slot][0],required=False,help_text=image_help(slot),
                           widget=forms.FileInput(attrs={'accept':'.svg,.png,.jpg,.jpeg'}))


class ImageForm(forms.ModelForm):
    restore_defaults=forms.BooleanField(label='Restaurar los valores e imágenes originales',required=False,
        help_text='No elimina imágenes guardadas ni modifica oficios o archivos PDF adjuntos.')
    slots=()

    def clean(self):
        cleaned=super().clean()
        if cleaned.get('restore_defaults') and any(cleaned.get(slot+'_upload') for slot in self.slots):
            raise ValidationError('Elige restaurar los originales o subir imágenes nuevas, no ambas opciones a la vez.')
        for slot in self.slots:
            upload=cleaned.get(slot+'_upload')
            if upload:
                try:validate_image(upload,slot)
                except ValidationError as error:self.add_error(slot+'_upload',error)
        return cleaned

    def save(self,commit=True):
        instance=super().save(commit=False)
        instance._pending_images={slot:self.cleaned_data.get(slot+'_upload') for slot in self.slots}
        instance._restore_defaults=self.cleaned_data.get('restore_defaults',False)
        if commit:save_appearance(instance,instance._pending_images,instance._restore_defaults)
        return instance


class WebAppearanceForm(ImageForm):
    slots=WEB_SLOTS
    site_logo_upload=image_field('site_logo')
    login_logo_upload=image_field('login_logo')
    favicon_upload=image_field('favicon')
    footer_upload=image_field('footer')

    class Meta:
        model=WebAppearance
        fields=list(DEFAULT_COLORS)
        widgets={field:forms.TextInput(attrs={'type':'color'}) for field in DEFAULT_COLORS}


class PrintIdentityForm(ImageForm):
    slots=PRINT_SLOTS
    print_left_upload=image_field('print_left')
    print_right_upload=image_field('print_right')

    class Meta:
        model=PrintIdentity
        fields=['year']

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if 'year' in self.fields:
            years=set(ConfiguracionTable.objects.values_list('anno',flat=True))
            from documento.access import available_tables, parse_table
            years.update(parse_table(table)[1] for table in available_tables({'ucg','delegacion'}))
            if self.instance.year:years.add(self.instance.year)
            self.fields['year']=forms.TypedChoiceField(label='Año del formato',coerce=int,
                choices=[('','Selecciona un año')]+[(year,str(year)) for year in sorted(years,reverse=True)],
                help_text='Crea primero el año en Configuración de tablas. Estas imágenes solo se usarán para imprimir oficios de ese año.')
