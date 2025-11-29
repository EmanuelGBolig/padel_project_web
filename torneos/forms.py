from django import forms
from .models import Torneo, Partido, PartidoGrupo, Inscripcion, Equipo


class TorneoAdminForm(forms.ModelForm):
    class Meta:
        model = Torneo
        fields = [
            'nombre',
            'division',
            'fecha_limite_inscripcion',
            'fecha_inicio',
            'cupos_totales',
            'equipos_por_grupo',
            'estado',
            'tipo_torneo',
        ]
        widgets = {
            'fecha_limite_inscripcion': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Estilo DaisyUI para todos los campos
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        estilo_select = 'select select-bordered w-full bg-base-100 text-base-content'

        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.EmailInput, forms.DateInput, forms.DateTimeInput)):
                field.widget.attrs['class'] = estilo_input
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = estilo_select
            
            # Mantener los tipos de fecha si ya existen
            if field_name == 'fecha_limite_inscripcion':
                 field.widget.attrs['type'] = 'datetime-local'
            if field_name == 'fecha_inicio':
                 field.widget.attrs['type'] = 'date'

        if self.instance.pk:
            if self.instance.fecha_limite_inscripcion:
                self.initial['fecha_limite_inscripcion'] = (
                    self.instance.fecha_limite_inscripcion.strftime('%Y-%m-%dT%H:%M')
                )
            if self.instance.fecha_inicio:
                self.initial['fecha_inicio'] = self.instance.fecha_inicio.strftime(
                    '%Y-%m-%d'
                )


class CargarResultadoGrupoForm(forms.ModelForm):
    class Meta:
        model = PartidoGrupo
        fields = ['e1_set1', 'e2_set1', 'e1_set2', 'e2_set2', 'e1_set3', 'e2_set3']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Estilo DaisyUI + Dark Mode Ready
        estilo_input = 'input input-bordered input-sm w-full text-center font-extrabold text-lg p-0 h-10 bg-base-100 text-base-content focus:border-primary'

        for field_name in self.fields:
            field = self.fields[field_name]
            field.label = ""
            field.widget.attrs.update(
                {
                    'class': estilo_input,
                    'placeholder': '-',
                    'min': '0',
                    'max': '7',
                    'type': 'number',
                }
            )

    def clean(self):
        cleaned_data = super().clean()
        e1_sets = 0
        e2_sets = 0
        e1_games = 0
        e2_games = 0
        for i in range(1, 4):
            s1 = cleaned_data.get(f'e1_set{i}')
            s2 = cleaned_data.get(f'e2_set{i}')
            if s1 is not None and s2 is not None:
                e1_games += s1
                e2_games += s2
                if s1 > s2:
                    e1_sets += 1
                elif s2 > s1:
                    e2_sets += 1

        self.instance.e1_sets_ganados = e1_sets
        self.instance.e2_sets_ganados = e2_sets
        self.instance.e1_games_ganados = e1_games
        self.instance.e2_games_ganados = e2_games

        if e1_sets > e2_sets:
            self.instance.ganador = self.instance.equipo1
        elif e2_sets > e1_sets:
            self.instance.ganador = self.instance.equipo2
        else:
            self.instance.ganador = None

        return cleaned_data


class PartidoResultadoForm(forms.ModelForm):
    set1_local = forms.IntegerField(required=False, min_value=0)
    set1_visitante = forms.IntegerField(required=False, min_value=0)
    set2_local = forms.IntegerField(required=False, min_value=0)
    set2_visitante = forms.IntegerField(required=False, min_value=0)
    set3_local = forms.IntegerField(required=False, min_value=0)
    set3_visitante = forms.IntegerField(required=False, min_value=0)

    resultado_local = forms.IntegerField(
        required=False, widget=forms.HiddenInput(), initial=0
    )
    resultado_visitante = forms.IntegerField(
        required=False, widget=forms.HiddenInput(), initial=0
    )

    class Meta:
        model = Partido
        fields = [
            'set1_local',
            'set1_visitante',
            'set2_local',
            'set2_visitante',
            'set3_local',
            'set3_visitante',
            'resultado_local',
            'resultado_visitante',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self.instance, 'sets_local') and self.instance.sets_local:
            for i, games in enumerate(self.instance.sets_local):
                if i < 3:
                    self.initial[f'set{i+1}_local'] = games
        if hasattr(self.instance, 'sets_visitante') and self.instance.sets_visitante:
            for i, games in enumerate(self.instance.sets_visitante):
                if i < 3:
                    self.initial[f'set{i+1}_visitante'] = games

        estilo_input = 'input input-bordered input-secondary input-sm w-full text-center font-extrabold text-lg p-0 h-10 bg-base-100 text-base-content focus:border-secondary'

        for field_name in self.fields:
            if 'resultado' not in field_name:
                field = self.fields[field_name]
                field.label = ""
                field.widget.attrs.update(
                    {'class': estilo_input, 'placeholder': '-', 'type': 'number'}
                )

    def clean(self):
        cleaned_data = super().clean()
        sets_local = 0
        sets_visitante = 0
        games_l = []
        games_v = []
        for i in range(1, 4):
            l = cleaned_data.get(f'set{i}_local')
            v = cleaned_data.get(f'set{i}_visitante')
            if l is not None and v is not None:
                games_l.append(l)
                games_v.append(v)
                if l > v:
                    sets_local += 1
                elif v > l:
                    sets_visitante += 1
            elif (l is not None and v is None) or (l is None and v is not None):
                self.add_error(f'set{i}_local', "Cargar ambos.")

        if sets_local > 2 or sets_visitante > 2:
            raise forms.ValidationError("Máximo 2 sets.")

        cleaned_data['resultado_local'] = sets_local
        cleaned_data['resultado_visitante'] = sets_visitante
        self.instance.sets_local = games_l
        self.instance.sets_visitante = games_v
        return cleaned_data

    def save(self, commit=True):
        """
        Asigna el ganador basado en los sets ganados y genera el string de resultado.
        """
        instance = super().save(commit=False)
        
        # Determinar ganador basado en sets ganados
        sets_local = self.cleaned_data.get('resultado_local', 0)
        sets_visitante = self.cleaned_data.get('resultado_visitante', 0)
        
        if sets_local > sets_visitante:
            instance.ganador = instance.equipo1
        elif sets_visitante > sets_local:
            instance.ganador = instance.equipo2
        else:
            instance.ganador = None
        
        # Generar string de resultado (ej: "6-4, 6-2")
        resultado_parts = []
        for i in range(len(instance.sets_local)):
            resultado_parts.append(f"{instance.sets_local[i]}-{instance.sets_visitante[i]}")
        instance.resultado = ", ".join(resultado_parts) if resultado_parts else None
        
        if commit:
            instance.save()
        
        return instance


class CargarResultadoForm(forms.ModelForm):
    class Meta:
        model = Partido
        fields = ['resultado', 'ganador']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            e1_id = self.instance.equipo1.id if self.instance.equipo1 else None
            e2_id = self.instance.equipo2.id if self.instance.equipo2 else None
            if e1_id and e2_id:
                self.fields['ganador'].queryset = self.fields[
                    'ganador'
                ].queryset.filter(id__in=[e1_id, e2_id])


class InscripcionForm(forms.ModelForm):
    class Meta:
        model = Inscripcion
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget = forms.HiddenInput()


class PartidoReplaceTeamsForm(forms.ModelForm):
    class Meta:
        model = Partido
        fields = ['equipo1', 'equipo2']
        widgets = {
            'equipo1': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'equipo2': forms.Select(attrs={'class': 'select select-bordered w-full'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.torneo:
            equipos_torneo = self.instance.torneo.equipos_inscritos.all()
            self.fields['equipo1'].queryset = equipos_torneo
            self.fields['equipo2'].queryset = equipos_torneo


class PartidoGrupoReplaceTeamsForm(forms.ModelForm):
    class Meta:
        model = PartidoGrupo
        fields = ['equipo1', 'equipo2']
        widgets = {
            'equipo1': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'equipo2': forms.Select(attrs={'class': 'select select-bordered w-full'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.grupo:
            # En grupos, idealmente filtramos por equipos del torneo, 
            # o podríamos filtrar por equipos del grupo si quisiéramos ser más estrictos,
            # pero para "reemplazar" suele ser mejor permitir cualquiera del torneo.
            equipos_torneo = self.instance.grupo.torneo.equipos_inscritos.all()
            
            # Filtrar equipos que YA han jugado partidos en CUALQUIER grupo
            # (Para evitar romper la integridad de otros grupos)
            from django.db.models import Q
            from .models import PartidoGrupo
            
            played_teams_ids = PartidoGrupo.objects.filter(
                grupo__torneo=self.instance.grupo.torneo,
                ganador__isnull=False
            ).values_list('equipo1_id', 'equipo2_id')
            
            # Flatten the list of tuples
            played_ids = set()
            for e1, e2 in played_teams_ids:
                if e1: played_ids.add(e1)
                if e2: played_ids.add(e2)
            
            # Excluir equipos que ya jugaron, PERO mantener los actuales del partido
            # (para que aparezcan seleccionados inicialmente)
            current_ids = {self.instance.equipo1_id, self.instance.equipo2_id}
            available_ids = set(equipos_torneo.values_list('id', flat=True)) - played_ids
            final_ids = available_ids | current_ids
            
            equipos_qs = equipos_torneo.filter(id__in=final_ids)
            
            self.fields['equipo1'].queryset = equipos_qs
            self.fields['equipo2'].queryset = equipos_qs

            # Validar si los equipos ya han jugado otros partidos
            from django.db.models import Q
            
            # Check Equipo 1
            if self.instance.equipo1:
                played_e1 = self.instance.grupo.partidos_grupo.filter(
                    Q(equipo1=self.instance.equipo1) | Q(equipo2=self.instance.equipo1),
                    ganador__isnull=False
                ).exclude(pk=self.instance.pk).exists()
                
                if played_e1:
                    self.fields['equipo1'].disabled = True
                    self.fields['equipo1'].help_text = f"{self.instance.equipo1} ya ha jugado partidos y no puede ser reemplazado."

            # Check Equipo 2
            if self.instance.equipo2:
                played_e2 = self.instance.grupo.partidos_grupo.filter(
                    Q(equipo1=self.instance.equipo2) | Q(equipo2=self.instance.equipo2),
                    ganador__isnull=False
                ).exclude(pk=self.instance.pk).exists()
                
                if played_e2:
                    self.fields['equipo2'].disabled = True
                    self.fields['equipo2'].help_text = f"{self.instance.equipo2} ya ha jugado partidos y no puede ser reemplazado."


class SwapGroupTeamsForm(forms.Form):
    equipo_origen = forms.ModelChoiceField(
        queryset=Equipo.objects.none(),
        label="Equipo de este Grupo",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full bg-base-100 text-base-content'})
    )
    equipo_destino = forms.ModelChoiceField(
        queryset=Equipo.objects.none(),
        label="Intercambiar con (Otro Grupo)",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full bg-base-100 text-base-content'})
    )

    def __init__(self, *args, **kwargs):
        self.grupo = kwargs.pop('grupo', None)
        super().__init__(*args, **kwargs)
        
        if self.grupo:
            from .models import PartidoGrupo
            from django.db.models import Q

            # 1. Equipos del grupo actual que NO han jugado
            played_in_group = PartidoGrupo.objects.filter(
                grupo=self.grupo,
                ganador__isnull=False
            ).values_list('equipo1_id', 'equipo2_id')
            
            played_ids_group = set()
            for e1, e2 in played_in_group:
                if e1: played_ids_group.add(e1)
                if e2: played_ids_group.add(e2)
                
            equipos_grupo = self.grupo.equipos.exclude(id__in=played_ids_group)
            self.fields['equipo_origen'].queryset = equipos_grupo

            # 2. Equipos de OTROS grupos que NO han jugado
            played_in_tournament = PartidoGrupo.objects.filter(
                grupo__torneo=self.grupo.torneo,
                ganador__isnull=False
            ).values_list('equipo1_id', 'equipo2_id')
            
            played_ids_tournament = set()
            for e1, e2 in played_in_tournament:
                if e1: played_ids_tournament.add(e1)
                if e2: played_ids_tournament.add(e2)
            
            # Equipos del torneo, excluyendo los del grupo actual y los que ya jugaron
            equipos_otros = self.grupo.torneo.equipos_inscritos.exclude(
                id__in=self.grupo.equipos.values_list('id', flat=True)
            ).exclude(id__in=played_ids_tournament)
            
            self.fields['equipo_destino'].queryset = equipos_otros


class PartidoGrupoScheduleForm(forms.ModelForm):
    class Meta:
        model = PartidoGrupo
        fields = ['fecha_hora']
        widgets = {
            'fecha_hora': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'input input-bordered w-full'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.fecha_hora:
            self.initial['fecha_hora'] = self.instance.fecha_hora.strftime('%Y-%m-%dT%H:%M')


class PartidoScheduleForm(forms.ModelForm):
    class Meta:
        model = Partido
        fields = ['fecha_hora']
        widgets = {
            'fecha_hora': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'input input-bordered w-full'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.fecha_hora:
            self.initial['fecha_hora'] = self.instance.fecha_hora.strftime('%Y-%m-%dT%H:%M')
