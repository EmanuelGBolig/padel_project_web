from django import forms
from .models import Equipo
from accounts.models import CustomUser
from dal import autocomplete
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div
from django.db.models import Q


class EquipoCreateForm(forms.ModelForm):
    # Usamos ModelMultipleChoiceField pero restringido a 1 para mejorar la UX
    jugador2 = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.all(),
        label="Selecciona tu compañero (Busca por nombre o apellido)",
        widget=autocomplete.ModelSelect2Multiple(
            url='equipos:jugador_autocomplete',
            attrs={
                'data-placeholder': 'Escribe el nombre o apellido...',
                'data-maximum-selection-length': 1,  # Restringir a 1 selección
                'class': 'w-full',
                'style': 'width: 100%;',
            },
        ),
    )
    
    categoria = forms.ChoiceField(
        choices=Equipo.Categoria.choices,
        label="Categoría del Equipo",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full'})
    )

    class Meta:
        model = Equipo
        fields = ['jugador2', 'categoria']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.user = user

            # 1. Jugadores que ya están en un equipo
            usuarios_con_equipo_ids = set(
                Equipo.objects.values_list('jugador1_id', flat=True)
            ).union(set(Equipo.objects.values_list('jugador2_id', flat=True)))

            # 2. Filtramos el queryset para el campo jugador2:
            self.fields['jugador2'].queryset = (
                CustomUser.objects.filter(division=user.division, tipo_usuario='PLAYER')
                .exclude(id=user.id)
                .exclude(id__in=usuarios_con_equipo_ids)
                .order_by('apellido', 'nombre')
            )

    def clean(self):
        cleaned_data = super().clean()
        jugador2_list = cleaned_data.get('jugador2')
        user = getattr(self, 'user', None)

        if not user:
            raise forms.ValidationError("Error inesperado: Usuario no encontrado.")

        # Lógica para extraer el único jugador de la lista
        jugador2 = None
        if jugador2_list:
            if len(jugador2_list) > 1:
                 raise forms.ValidationError("Solo puedes seleccionar un compañero.")
            jugador2 = jugador2_list[0]
            # Reasignamos el valor limpio como un objeto único, no una lista
            cleaned_data['jugador2'] = jugador2
        
        if jugador2 and jugador2.id == user.id:
            raise forms.ValidationError(
                "No puedes seleccionarte a ti mismo como compañero."
            )

        return cleaned_data
