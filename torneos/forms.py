from django import forms
from .models import (
    Torneo, Partido, PartidoGrupo, Inscripcion, Equipo, Grupo,
    Americano, JugadorAmericano, ResolucionPartido, FormatoPersonalizado,
)


class FormatoPersonalizadoForm(forms.ModelForm):
    """Crear/editar un formato de torneo guardable (semi-automático)."""
    sizes_texto = forms.CharField(
        label="Tamaño de cada zona",
        help_text="Parejas por zona, separadas por coma. Ej: 3,3,3,3,2 (5 zonas).",
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full bg-base-100 text-base-content',
            'placeholder': '3,3,3,3,2',
        }),
    )

    class Meta:
        model = FormatoPersonalizado
        fields = ['nombre', 'clasifican_por_grupo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'input input-bordered w-full bg-base-100 text-base-content',
                'placeholder': 'Ej: Liga 16 (5 zonas)',
            }),
            'clasifican_por_grupo': forms.Select(
                choices=[(1, '1 (solo el primero)'), (2, '2 (primero y segundo)')],
                attrs={'class': 'select select-bordered w-full bg-base-100 text-base-content'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.sizes:
            self.initial['sizes_texto'] = ','.join(str(s) for s in self.instance.sizes)

    def clean_sizes_texto(self):
        crudo = (self.cleaned_data.get('sizes_texto') or '').strip()
        partes = [p.strip() for p in crudo.replace(' ', ',').split(',') if p.strip()]
        sizes = []
        for p in partes:
            if not p.isdigit():
                raise forms.ValidationError("Usá solo números separados por coma. Ej: 3,3,3,3,2")
            n = int(p)
            if n < 2:
                raise forms.ValidationError("Cada zona necesita al menos 2 parejas.")
            sizes.append(n)
        if len(sizes) < 2:
            raise forms.ValidationError("El formato necesita al menos 2 zonas.")
        if len(sizes) > 26:
            raise forms.ValidationError("Máximo 26 zonas.")
        self._sizes = sizes
        return crudo

    def clean(self):
        cleaned = super().clean()
        import json
        crudo = (self.data.get('cruces_json') or '').strip()
        self._cruces = []
        if not crudo or crudo in ('[]', 'null'):
            return cleaned
        try:
            cruces = json.loads(crudo)
        except Exception:
            raise forms.ValidationError("No se pudieron leer los cruces de la fase final.")

        sizes = getattr(self, '_sizes', None) or []
        try:
            clasif = int(cleaned.get('clasifican_por_grupo') or 2)
        except (TypeError, ValueError):
            clasif = 2
        letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        validos = {f"{k + 1}{letras[i]}" for i in range(len(sizes)) for k in range(clasif)}
        total = len(validos)

        def next_pow2(x):
            p = 1
            while p < x:
                p *= 2
            return p

        # El cuadro siempre tiene nextPow2(total)/2 posiciones (potencia de 2). Cada
        # posición es un partido (a vs b) o un bye (sólo a, pasa directo).
        pos_esperadas = next_pow2(total) // 2 if total >= 2 else 0

        usados, pares = [], []
        for par in cruces:
            if not isinstance(par, (list, tuple)) or not (1 <= len(par) <= 2):
                raise forms.ValidationError("Hay un cruce mal formado.")
            a = str(par[0]).strip().upper()
            b = str(par[1]).strip().upper() if len(par) > 1 else ''
            if not a:
                raise forms.ValidationError("Cada posición del cuadro necesita al menos un clasificado.")
            for x in ([a] + ([b] if b else [])):
                if x not in validos:
                    raise forms.ValidationError(f"“{x}” no es un clasificado válido para este formato.")
                if x in usados:
                    raise forms.ValidationError(f"“{x}” aparece en más de un cruce.")
                usados.append(x)
            pares.append([a, b])

        num_pos = len(pares)
        if num_pos and (num_pos & (num_pos - 1)) != 0:
            raise forms.ValidationError("La cantidad de posiciones del cuadro debe ser potencia de 2.")
        if pares and num_pos != pos_esperadas:
            raise forms.ValidationError(
                f"Para {total} clasificados el cuadro tiene {pos_esperadas} posiciones; "
                f"definiste {num_pos}."
            )
        if pares and len(usados) != total:
            raise forms.ValidationError(
                f"Tenés que ubicar a TODOS los clasificados exactamente una vez ({total})."
            )
        self._cruces = pares
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.sizes = getattr(self, '_sizes', obj.sizes)
        obj.cruces_manuales = getattr(self, '_cruces', [])
        if commit:
            obj.save()
        return obj


class TorneoAdminForm(forms.ModelForm):
    class Meta:
        model = Torneo
        fields = [
            'nombre',
            'division',
            'fecha_limite_inscripcion',
            'fecha_inicio',
            'cupos_totales',
            'formato_personalizado',
            'equipos_por_grupo',
            'forzar_grupos_de_3',
            'formato_grupos_4',
            'tipo_torneo',
            'categoria',
            'cover_image',
            'ciudad',
            'sede_nombre',
            'sede_direccion',
            'premio',
            'reglamento',
            'foto_campeones',
        ]
        widgets = {
            'fecha_limite_inscripcion': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        # El user se pasa desde la vista (get_form_kwargs) para prefijar datos
        # de la organización (TP-17.4) y validar permisos.
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        es_creacion = self.instance.pk is None

        # Formato personalizado: ofrecer solo los de la organización del usuario.
        if 'formato_personalizado' in self.fields:
            self.fields['formato_personalizado'].label = "Formato personalizado"
            self.fields['formato_personalizado'].required = False
            self.fields['formato_personalizado'].empty_label = "Automático (según cupos)"
            self.fields['formato_personalizado'].help_text = (
                "Opcional: usá una estructura de zonas guardada."
            )
            org = getattr(self.user, 'organizacion', None) if self.user else None
            qs = self.fields['formato_personalizado'].queryset
            self.fields['formato_personalizado'].queryset = (
                qs.filter(organizacion=org) if org else qs.none()
            )

        # TP-17.1: la foto de campeones no se pide al CREAR (todavía no hay ganador);
        # solo aparece al editar/gestionar un torneo ya existente.
        if es_creacion and 'foto_campeones' in self.fields:
            del self.fields['foto_campeones']

        # TP-17.4: al crear, prefijar sede/ciudad/dirección desde la organización
        # del organizador, para no reescribirlas en cada torneo.
        if es_creacion and self.user is not None:
            org = getattr(self.user, 'organizacion', None)
            if org is not None:
                self.initial.setdefault('sede_nombre', org.nombre)
                self.initial.setdefault('sede_direccion', org.direccion)
                self.initial.setdefault('ciudad', org.ciudad)

        # Opción "Libre" para división
        self.fields['division'].empty_label = "Libre / General"
        self.fields['division'].required = False
        self.fields['division'].help_text = ""

        # Estilo DaisyUI para todos los campos
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        estilo_select = 'select select-bordered w-full bg-base-100 text-base-content'

        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.EmailInput, forms.DateInput, forms.DateTimeInput)):
                field.widget.attrs['class'] = estilo_input
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = estilo_select
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'checkbox checkbox-primary'
            elif isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['class'] = 'file-input file-input-bordered file-input-primary w-full bg-base-100 text-base-content'
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'textarea textarea-bordered w-full bg-base-100 text-base-content h-28'

            # Label para categoria
            if field_name == 'categoria':
                field.label = "Categoría"
                field.help_text = ""
            
            if field_name == 'equipos_por_grupo':
                field.label = "Equipos por Zona"
            
            if field_name == 'forzar_grupos_de_3':
                field.label = "Forzar Zonas de 3"
            
            if field_name == 'formato_grupos_4':
                field.label = "Formato de Zonas de 4"
            
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

    def clean(self):
        """TP-17.5: validaciones que avisan/bloquean según el matiz del backlog.

        - Fechas: el cierre de inscripción no puede ser DESPUÉS del inicio
          (se compara a fin del día de inicio). Bloquea.
        - Cupos mínimos: con fase de grupos se necesitan al menos 4 parejas.
          Bloquea (coherente con el corte real de la generación).
        - Cupos "sin formato optimizado" NO se bloquean: la estructura real se
          arma con los inscriptos reales; el aviso vive en la vista previa.
        """
        cleaned = super().clean()
        limite = cleaned.get('fecha_limite_inscripcion')
        inicio = cleaned.get('fecha_inicio')
        if limite and inicio and limite.date() > inicio:
            self.add_error(
                'fecha_limite_inscripcion',
                "El cierre de inscripción no puede ser después del inicio.",
            )

        cupos = cleaned.get('cupos_totales')
        tipo = cleaned.get('tipo_torneo')
        if tipo == Torneo.TipoTorneo.GRUPOS and cupos is not None and cupos < 4:
            self.add_error(
                'cupos_totales',
                "Para fase de grupos necesitás al menos 4 parejas.",
            )

        return cleaned


class CargarResultadoGrupoForm(forms.ModelForm):
    # TP-18: lado ganador (W.O.) / lado que abandona (abandono). '1' = equipo1, '2' = equipo2.
    lado_ganador = forms.ChoiceField(required=False, label="Gana")
    lado_abandona = forms.ChoiceField(required=False, label="Abandonó")

    class Meta:
        model = PartidoGrupo
        fields = ['resolucion', 'e1_set1', 'e2_set1', 'e1_set2', 'e2_set2', 'e1_set3', 'e2_set3']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Opciones de lado con el nombre de cada equipo.
        choices = [
            ('1', str(self.instance.equipo1) if self.instance.equipo1_id else "Equipo 1"),
            ('2', str(self.instance.equipo2) if self.instance.equipo2_id else "Equipo 2"),
        ]
        self.fields['lado_ganador'].choices = [('', '—')] + choices
        self.fields['lado_abandona'].choices = [('', '—')] + choices

        estilo_select = 'select select-bordered select-sm w-full bg-base-100 text-base-content'
        self.fields['resolucion'].widget.attrs['class'] = estilo_select
        self.fields['resolucion'].label = "Tipo de resultado"
        self.fields['lado_ganador'].widget.attrs['class'] = estilo_select
        self.fields['lado_abandona'].widget.attrs['class'] = estilo_select

        # Estilo DaisyUI + Dark Mode Ready para los inputs de sets
        estilo_input = 'input input-bordered input-sm w-full text-center font-extrabold text-lg p-0 h-10 bg-base-100 text-base-content focus:border-primary'
        for field_name in ['e1_set1', 'e2_set1', 'e1_set2', 'e2_set2', 'e1_set3', 'e2_set3']:
            field = self.fields[field_name]
            field.label = ""
            field.widget.attrs.update(
                {'class': estilo_input, 'placeholder': '-', 'min': '0', 'max': '7', 'type': 'number'}
            )

    def _lado_a_equipo(self, lado):
        return self.instance.equipo1 if lado == '1' else self.instance.equipo2

    def clean(self):
        cleaned_data = super().clean()
        resolucion = cleaned_data.get('resolucion') or ResolucionPartido.NORMAL

        # --- WALKOVER: gana el presente, sin jugar. 2-0 en sets, sin games. ---
        if resolucion == ResolucionPartido.WALKOVER:
            lado = cleaned_data.get('lado_ganador')
            if lado not in ('1', '2'):
                self.add_error('lado_ganador', "Elegí qué pareja gana por W.O.")
                return cleaned_data
            # Limpiar sets cargados (no se jugó).
            for f in ['e1_set1', 'e2_set1', 'e1_set2', 'e2_set2', 'e1_set3', 'e2_set3']:
                cleaned_data[f] = None
                setattr(self.instance, f, None)
            self.instance.e1_sets_ganados = 2 if lado == '1' else 0
            self.instance.e2_sets_ganados = 2 if lado == '2' else 0
            # Games NO se tocan (no inflar desempates por un partido no jugado).
            self.instance.e1_games_ganados = 0
            self.instance.e2_games_ganados = 0
            self.instance.ganador = self._lado_a_equipo(lado)
            return cleaned_data

        # --- ABANDONO: se carga el parcial; gana la pareja que NO abandonó. ---
        if resolucion == ResolucionPartido.ABANDONO:
            lado = cleaned_data.get('lado_abandona')
            if lado not in ('1', '2'):
                self.add_error('lado_abandona', "Marcá qué pareja abandonó.")
                return cleaned_data
            e1_sets = e2_sets = e1_games = e2_games = 0
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
            # Gana el otro lado (el que no abandonó).
            self.instance.ganador = self._lado_a_equipo('2' if lado == '1' else '1')
            return cleaned_data

        # --- NORMAL: como siempre, el ganador sale de los sets. ---
        e1_sets = e2_sets = e1_games = e2_games = 0
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

    # TP-18: lado ganador (W.O.) / lado que abandona. '1' = local (equipo1), '2' = visitante (equipo2).
    lado_ganador = forms.ChoiceField(required=False, label="Gana")
    lado_abandona = forms.ChoiceField(required=False, label="Abandonó")

    class Meta:
        model = Partido
        fields = [
            'resolucion',
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

        choices = [
            ('1', str(self.instance.equipo1) if self.instance.equipo1_id else "Equipo 1"),
            ('2', str(self.instance.equipo2) if self.instance.equipo2_id else "Equipo 2"),
        ]
        self.fields['lado_ganador'].choices = [('', '—')] + choices
        self.fields['lado_abandona'].choices = [('', '—')] + choices
        estilo_select = 'select select-bordered select-sm w-full bg-base-100 text-base-content'
        self.fields['resolucion'].widget.attrs['class'] = estilo_select
        self.fields['resolucion'].label = "Tipo de resultado"
        self.fields['lado_ganador'].widget.attrs['class'] = estilo_select
        self.fields['lado_abandona'].widget.attrs['class'] = estilo_select

        estilo_input = 'input input-bordered input-secondary input-sm w-full text-center font-extrabold text-lg p-0 h-10 bg-base-100 text-base-content focus:border-secondary'

        for field_name in ['set1_local', 'set1_visitante', 'set2_local',
                           'set2_visitante', 'set3_local', 'set3_visitante']:
            field = self.fields[field_name]
            field.label = ""
            field.widget.attrs.update(
                {'class': estilo_input, 'placeholder': '-', 'type': 'number'}
            )

    def clean(self):
        cleaned_data = super().clean()
        resolucion = cleaned_data.get('resolucion') or ResolucionPartido.NORMAL

        # --- WALKOVER: gana el presente, sin sets jugados. ---
        if resolucion == ResolucionPartido.WALKOVER:
            lado = cleaned_data.get('lado_ganador')
            if lado not in ('1', '2'):
                self.add_error('lado_ganador', "Elegí qué pareja gana por W.O.")
                return cleaned_data
            self.instance.sets_local = []
            self.instance.sets_visitante = []
            cleaned_data['resultado_local'] = 1 if lado == '1' else 0
            cleaned_data['resultado_visitante'] = 1 if lado == '2' else 0
            return cleaned_data

        # Sets cargados (Normal y Abandono comparten el parseo del parcial).
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

        self.instance.sets_local = games_l
        self.instance.sets_visitante = games_v

        # --- ABANDONO: gana la pareja que NO abandonó (el parcial queda como está). ---
        if resolucion == ResolucionPartido.ABANDONO:
            lado = cleaned_data.get('lado_abandona')
            if lado not in ('1', '2'):
                self.add_error('lado_abandona', "Marcá qué pareja abandonó.")
                return cleaned_data
            # Gana el lado opuesto al que abandonó.
            cleaned_data['resultado_local'] = 1 if lado == '2' else 0
            cleaned_data['resultado_visitante'] = 1 if lado == '1' else 0
            return cleaned_data

        # --- NORMAL ---
        if sets_local > 2 or sets_visitante > 2:
            raise forms.ValidationError("Máximo 2 sets.")
        cleaned_data['resultado_local'] = sets_local
        cleaned_data['resultado_visitante'] = sets_visitante
        return cleaned_data

    def save(self, commit=True):
        """
        Asigna el ganador basado en los sets ganados y genera el string de resultado.
        """
        instance = super().save(commit=False)
        resolucion = self.cleaned_data.get('resolucion') or ResolucionPartido.NORMAL

        # Determinar ganador basado en el conteo (sets normales, o forzado en W.O./abandono)
        sets_local = self.cleaned_data.get('resultado_local', 0)
        sets_visitante = self.cleaned_data.get('resultado_visitante', 0)

        if sets_local > sets_visitante:
            instance.ganador = instance.equipo1
        elif sets_visitante > sets_local:
            instance.ganador = instance.equipo2
        else:
            instance.ganador = None

        # Generar string de resultado
        if resolucion == ResolucionPartido.WALKOVER:
            instance.resultado = "W.O."
        else:
            resultado_parts = []
            for i in range(len(instance.sets_local)):
                resultado_parts.append(f"{instance.sets_local[i]}-{instance.sets_visitante[i]}")
            base = ", ".join(resultado_parts) if resultado_parts else None
            if resolucion == ResolucionPartido.ABANDONO:
                instance.resultado = f"{base} (abandono)" if base else "Abandono"
            else:
                instance.resultado = base

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
        elif self.instance.grupo.fecha_inicio_default:
            # Si no hay fecha, sugerir la del grupo + 09:00 AM
            default_date = self.instance.grupo.fecha_inicio_default
            self.initial['fecha_hora'] = f"{default_date.strftime('%Y-%m-%d')}T09:00"


class GrupoDateForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ['fecha_inicio_default']
        widgets = {
            'fecha_inicio_default': forms.DateInput(
                attrs={'type': 'date', 'class': 'input input-bordered input-sm w-full'},
                format='%Y-%m-%d'
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_inicio_default'].label = ""


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


class TorneoReplaceTeamForm(forms.Form):
    equipo_a_reemplazar = forms.ModelChoiceField(
        queryset=Equipo.objects.none(),
        label="Equipo Actual",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full bg-base-100 text-base-content'})
    )
    nuevo_equipo = forms.ModelChoiceField(
        queryset=Equipo.objects.none(),
        label="Reemplazar por (Equipo Existente)",
        required=False,
        widget=forms.Select(attrs={'class': 'select select-bordered w-full bg-base-100 text-base-content'})
    )
    crear_dummy = forms.BooleanField(
        label="Crear Pareja Libre (Dummy)",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'checkbox checkbox-primary w-5 h-5'})
    )
    nombre_dummy = forms.CharField(
        label="Nombre del Dummy (Opcional)",
        required=False,
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full bg-base-100 text-base-content', 'placeholder': 'Ej: Pareja Libre X'})
    )

    def __init__(self, *args, **kwargs):
        self.torneo = kwargs.pop('torneo', None)
        super().__init__(*args, **kwargs)
        
        if self.torneo:
            from .models import PartidoGrupo, Partido
            
            # Equipos inscritos en el torneo
            equipos_inscritos = self.torneo.equipos_inscritos.all()
            
            # Identificar equipos que ya jugaron partidos
            played_group_matches = PartidoGrupo.objects.filter(
                grupo__torneo=self.torneo,
                ganador__isnull=False
            ).values_list('equipo1_id', 'equipo2_id')
            
            played_bracket_matches = Partido.objects.filter(
                torneo=self.torneo,
                ganador__isnull=False
            ).values_list('equipo1_id', 'equipo2_id')
            
            played_ids = set()
            for e1, e2 in played_group_matches:
                if e1: played_ids.add(e1)
                if e2: played_ids.add(e2)
            for e1, e2 in played_bracket_matches:
                if e1: played_ids.add(e1)
                if e2: played_ids.add(e2)
                
            editable_equipos = equipos_inscritos.exclude(id__in=played_ids)
            self.fields['equipo_a_reemplazar'].queryset = editable_equipos
            
            # Equipos fuera del torneo
            from equipos.models import Equipo
            equipos_fuera = Equipo.objects.exclude(id__in=equipos_inscritos.values_list('id', flat=True))
            self.fields['nuevo_equipo'].queryset = equipos_fuera

    def clean(self):
        cleaned_data = super().clean()
        nuevo_equipo = cleaned_data.get("nuevo_equipo")
        crear_dummy = cleaned_data.get("crear_dummy")
        
        if not nuevo_equipo and not crear_dummy:
            raise forms.ValidationError("Debes seleccionar un equipo existente o tildar 'Crear Pareja Libre'.")
            
        if nuevo_equipo and crear_dummy:
            raise forms.ValidationError("No puedes seleccionar un equipo existente y crear uno nuevo a la vez.")

        return cleaned_data


class AmericanoForm(forms.ModelForm):
    """Crear un Americano/Mexicano (TP-09)."""

    class Meta:
        model = Americano
        fields = ['nombre', 'tipo', 'num_canchas']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'select select-bordered w-full bg-base-100 text-base-content'
            else:
                field.widget.attrs['class'] = 'input input-bordered w-full bg-base-100 text-base-content'
        self.fields['num_canchas'].help_text = "Cada cancha juega con 4 jugadores."


class JugadorAmericanoForm(forms.ModelForm):
    """Inscripción por link (sin cuenta) a un Americano (TP-09)."""

    class Meta:
        model = JugadorAmericano
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'input input-bordered w-full bg-base-100 text-base-content',
                'placeholder': 'Tu nombre y apellido',
            }),
        }
