from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from gestion_tables.models import ConfiguracionTable
from .roles import OPERATIONAL_GROUPS, TECHNICAL_GROUP


class OperatorUserForm(UserCreationForm):
    groups = forms.ModelMultipleChoiceField(label='Perfiles de acceso', queryset=Group.objects.none(),
        widget=forms.CheckboxSelectMultiple, help_text='Selecciona los departamentos o tareas que necesita esta cuenta.')

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email')
        labels = {'first_name': 'Nombre', 'last_name': 'Apellidos', 'email': 'Correo electrónico (opcional)'}

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        if actor.is_superuser:
            self.fields['groups'].queryset = Group.objects.filter(name__in=(*OPERATIONAL_GROUPS, TECHNICAL_GROUP)).order_by('name')
        else:
            # Un gestor de altas puede crear operadores; no delegar facultades de
            # gestión ni grupos que alguien haya dotado de permisos adicionales.
            self.fields['groups'].queryset = Group.objects.filter(
                name__in=('UCG', 'Delegacion'), permissions__isnull=True).order_by('name')
            self.fields['groups'].help_text = 'Puedes asignar acceso por departamento. Los perfiles de gestión los asigna el responsable técnico.'
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'form-control'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'

    def clean(self):
        cleaned = super().clean()
        if any(name in self.data for name in ('is_staff', 'is_superuser', 'user_permissions', 'is_active')):
            raise forms.ValidationError('No se pueden modificar privilegios técnicos desde estos campos.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        selected = self.cleaned_data['groups']
        user.is_active = True
        user.is_superuser = False
        user.is_staff = self.actor.is_superuser and selected.filter(name=TECHNICAL_GROUP).exists()
        if commit:
            user.save()
            user.groups.set(selected)
        return user


class AnnualFolderForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionTable
        fields = ('anno', 'descripcion')
        labels = {'anno': 'Año de las carpetas', 'descripcion': 'Descripción (opcional)'}
        widgets = {
            'anno': forms.NumberInput(attrs={'class': 'form-control', 'min': 1000, 'max': 9999}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 255}),
        }
