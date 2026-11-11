from django import forms
from .models import Oficio


class DocumentEditForm(forms.Form):
    enviado_por = forms.CharField(label='Enviado por', max_length=255)
    procedencia = forms.CharField(label='Procedencia', max_length=255)
    asunto = forms.CharField(label='Asunto', max_length=255)
    referencia = forms.CharField(label='Referencia', max_length=255, required=False)


class DocumentCreateForm(DocumentEditForm):
    fecha_recibido = forms.DateField(label='Fecha recibido', input_formats=['%Y-%m-%d'])
    fecha_oficio = forms.DateField(label='Fecha del oficio', input_formats=['%Y-%m-%d'])


class FolioForm(forms.Form):
    asunto_opciones = forms.ChoiceField(label='Tipo de asunto', choices=Oficio.ASUNTO_OPCIONES)
    area = forms.ChoiceField(label='Área IVEM', choices=[(value, value) for value in (
        'Dir. General', 'Del. Administración', 'UCG', 'Sub. Jurídica',
        'Sub. planeacion', 'Sub. Técnica', 'Sub. Comercialización',
    )] + list(Oficio.AREA_OPCIONES))
    nota = forms.CharField(label='Nota', max_length=255, required=False)


def error_message(form):
    return ' '.join(f'{form.fields[field].label}: {" ".join(errors)}' for field, errors in form.errors.items())
