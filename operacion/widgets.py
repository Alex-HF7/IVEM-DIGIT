from django.forms import CheckboxSelectMultiple
from .presentation import ROLE_PRESENTATION


class AccessProfilesWidget(CheckboxSelectMultiple):
    template_name = 'operacion/widgets/access_profiles.html'

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        group = getattr(value, 'instance', None)
        if group:
            title, description, category = ROLE_PRESENTATION.get(group.name, (str(label), '', 'advanced'))
            option.update(label=title, description=description, category=category)
        return option

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        options = [option for _, choices, _ in context['widget']['optgroups'] for option in choices]
        context['has_advanced'] = any(option.get('category') == 'advanced' for option in options)
        context['advanced_selected'] = any(option.get('category') == 'advanced' and option['selected'] for option in options)
        return context
