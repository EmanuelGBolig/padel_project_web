from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q, F
from random import shuffle
from collections import defaultdict
import math
from itertools import combinations
from django.http import HttpResponse

from .models import Torneo, Inscripcion, Partido, Grupo, EquipoGrupo, PartidoGrupo
from .forms import (
    TorneoAdminForm,
    CargarResultadoGrupoForm,
    CargarResultadoForm,
    InscripcionForm,
    PartidoResultadoForm,
    PartidoGrupoScheduleForm,
    PartidoScheduleForm,
    PartidoReplaceTeamsForm,
    PartidoGrupoReplaceTeamsForm,
)
from .formats import get_format
from equipos.models import Equipo

# --- Mixins de Permisos ---


class PlayerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.tipo_usuario == 'PLAYER'

    def handle_no_permission(self):
        messages.error(self.request, "Debes ser un jugador para ver esta sección.")
        return redirect('core:home')


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.tipo_usuario in ['ADMIN', 'ORGANIZER']

    def handle_no_permission(self):
        messages.error(self.request, "Acceso denegado: solo administradores u organizadores.")
        return redirect('core:home')


# --- FUNCIONES AUXILIARES ---


def generar_partidos_grupos(torneo, equipos, grupo_obj):
    """Crea un partido de 'todos contra todos' para los equipos dentro de un grupo."""
    partidos_a_crear = []
    for equipo1, equipo2 in combinations(equipos, 2):
        partidos_a_crear.append(
            PartidoGrupo(grupo=grupo_obj, equipo1=equipo1, equipo2=equipo2)
        )
    PartidoGrupo.objects.bulk_create(partidos_a_crear)


# --- VISTA DE GESTIÓN PRINCIPAL (LÓGICA CENTRALIZADA) ---


class AdminTorneoManageView(AdminRequiredMixin, DetailView):
    model = Torneo
    template_name = 'torneos/admin_torneo_manage.html'
    context_object_name = 'torneo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        torneo = self.object

        # Inscripciones
        context['inscripciones'] = (
            torneo.inscripciones.all()
            .select_related('equipo')
            .order_by('fecha_inscripcion')
        )

        # Fase de Grupos
        grupos = (
            torneo.grupos.all()
            .prefetch_related(
                'tabla__equipo', 'partidos_grupo__equipo1', 'partidos_grupo__equipo2'
            )
            .order_by('nombre')
        )
        context['grupos'] = grupos

        context['partidos_grupo_pendientes'] = PartidoGrupo.objects.filter(
            grupo__torneo=torneo, ganador__isnull=True
        ).count()

        context['todos_grupos_cargados'] = (
            context['partidos_grupo_pendientes'] == 0
        ) and grupos.exists()

        # Fase Eliminatoria
        context['fase_eliminatoria_existente'] = torneo.partidos.exists()
        context['partidos_eliminacion'] = torneo.partidos.all().order_by(
            'ronda', 'orden_partido'
        )

        if context['partidos_eliminacion'].exists():
            from django.db.models import Max
            max_ronda = context['partidos_eliminacion'].aggregate(Max('ronda'))['ronda__max']
            context['total_rondas'] = max_ronda if max_ronda else 0
        else:
            context['total_rondas'] = 0

        return context

    def post(self, request, *args, **kwargs):
        torneo = self.get_object()
        action = request.POST.get('action')

        if action == 'iniciar_torneo':
            return self.iniciar_torneo_logica(request, torneo)
        
        elif action == 'agregar_dummy':
            # Crear o buscar equipo dummy (o crear uno nuevo siempre)
            # Para evitar flood de dummies, intentaremos usar uno si existe y no está en este torneo,
            # pero lo más simple es crear uno nuevo exclusivo para este torneo o permitir múltiples.
            # Dado que 'nombre' es unique, necesitamos nombres únicos.
            count_dummies = Equipo.objects.filter(es_dummy=True).count()
            nombre_dummy = f"Pareja Libre {count_dummies + 1}"
            
            # Crear el equipo dummy
            equipo_dummy = Equipo.objects.create(
                nombre=nombre_dummy,
                es_dummy=True,
                division=torneo.division, # Asignar división del torneo para consistencia
                categoria=torneo.categoria or Equipo.Categoria.MIXTO
            )
            
            # Inscribirlo
            Inscripcion.objects.create(torneo=torneo, equipo=equipo_dummy)
            messages.success(request, f"Se agregó '{nombre_dummy}' al torneo.")
            return redirect('torneos:admin_manage', pk=torneo.pk)

        elif action == 'generar_octavos':
            return self.generar_octavos_logica(request, torneo)
        
        elif action == 'reset_bracket':
            # Eliminar todos los partidos de eliminación
            torneo.partidos.all().delete()
            messages.success(request, "Bracket eliminado. Puedes generar uno nuevo.")
            return redirect('torneos:admin_manage', pk=torneo.pk)

        elif action == 'finalizar_torneo':
            torneo.estado = Torneo.Estado.FINALIZADO
            torneo.save()
            messages.success(request, "Torneo finalizado.")
            return redirect('torneos:admin_manage', pk=torneo.pk)

        return redirect('torneos:admin_manage', pk=torneo.pk)

    # --- LÓGICA DE NEGOCIO INTERNA ---

    def iniciar_torneo_logica(self, request, torneo):
        if torneo.estado != Torneo.Estado.ABIERTO:
            return redirect('torneos:admin_manage', pk=torneo.pk)

        inscripciones = torneo.inscripciones.all()
        count = inscripciones.count()

        # Limpiar grupos anteriores si existen (para evitar duplicados al reiniciar)
        if torneo.grupos.exists():
            torneo.grupos.all().delete()

        if count < 4:
            messages.error(request, f"Se necesitan al menos 4 equipos. Hay {count}.")
            return redirect('torneos:admin_manage', pk=torneo.pk)

        equipos = [i.equipo for i in inscripciones]
        shuffle(equipos)

        # --- LÓGICA DE FORMATOS PERSONALIZADOS ---
        custom_format = get_format(count)
        
        if custom_format:
            # Usar formato definido
            num_grupos = custom_format.groups
            teams_per_group_config = custom_format.teams_per_group
            letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            # Validar si teams_per_group es int o list
            if isinstance(teams_per_group_config, int):
                sizes = [teams_per_group_config] * num_grupos
            else:
                sizes = teams_per_group_config
                
            # Validar que la suma de sizes coincida con count
            if sum(sizes) != count:
                # Fallback o error si la configuración está mal
                messages.error(request, f"Error en formato: {sum(sizes)} plazas definidas para {count} equipos.")
                return redirect('torneos:admin_manage', pk=torneo.pk)

            current_team_idx = 0
            for i in range(num_grupos):
                group_size = sizes[i]
                grupo = Grupo.objects.create(torneo=torneo, nombre=f"Zona {letras[i]}")
                
                equipos_del_grupo = []
                for _ in range(group_size):
                    if current_team_idx < len(equipos):
                        equipos_del_grupo.append(equipos[current_team_idx])
                        current_team_idx += 1
                
                for idx, eq in enumerate(equipos_del_grupo, start=1):
                    EquipoGrupo.objects.create(grupo=grupo, equipo=eq, numero=idx)

                generar_partidos_grupos(torneo, equipos_del_grupo, grupo)
                
            messages.success(request, f"Torneo iniciado con formato especial: {count} parejas.")

        else:
            # --- LÓGICA POR DEFECTO ---
            # --- LÓGICA POR DEFECTO ---
            
            # NUEVO: Lógica Forzar grupos de 3
            if torneo.forzar_grupos_de_3:
                teams_per_group = 3
                num_equipos = len(equipos)
                
                # Calcular número de grupos necesarios
                # Si tenemos 6 equipos: 6/3 = 2 grupos (perfecto)
                # Si tenemos 7 equipos: 7/3 = 2 grupos y sobra 1 -> Error o Dummy?
                # Si tenemos 8 equipos: 8/3 = 2 grupos y sobran 2 -> Error o Dummy?
                
                # La lógica deseada es forzar grupos de 3. Si no es divisible, NO se puede iniciar
                # a menos que se hayan agregado dummies previamente.
                if num_equipos % 3 != 0:
                    faltantes = 3 - (num_equipos % 3)
                    messages.error(
                        request, 
                        f"Para forzar grupos de 3, el número de equipos ({num_equipos}) debe ser divisible por 3. "
                        f"Faltan {faltantes} equipos (o 'Parejas Libres') para completar los grupos."
                    )
                    return redirect('torneos:admin_manage', pk=torneo.pk)
                
                num_grupos = num_equipos // 3
                equipos_por_grupo = 3
                
            else:
                # Usar el tamaño de grupo configurado en el torneo (Lógica Legacy)
                equipos_por_grupo = torneo.equipos_por_grupo
                num_grupos = (count + equipos_por_grupo - 1) // equipos_por_grupo

            letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

            for i in range(num_grupos):
                grupo = Grupo.objects.create(torneo=torneo, nombre=f"Grupo {letras[i]}")
                equipos_del_grupo = []
                for _ in range(equipos_por_grupo):
                    if equipos:
                        equipos_del_grupo.append(equipos.pop())

                for idx, eq in enumerate(equipos_del_grupo, start=1):
                    EquipoGrupo.objects.create(grupo=grupo, equipo=eq, numero=idx)

                generar_partidos_grupos(torneo, equipos_del_grupo, grupo)
            
            messages.success(
                request, f"Fase de Grupos generada: {num_grupos} grupos creados."
            )

        torneo.estado = Torneo.Estado.EN_JUEGO
        torneo.save()
        return redirect('torneos:admin_manage', pk=torneo.pk)

    def generar_octavos_logica(self, request, torneo):
        inscripciones = torneo.inscripciones.all()
        count = inscripciones.count()
        custom_format = get_format(count)

        if custom_format:
            # --- LÓGICA DE BRACKET PERSONALIZADO ---
            
            # 1. Mapear grupos por letra (Zona A -> 'A')
            grupos_map = {}
            grupos = torneo.grupos.all()
            for g in grupos:
                # Asumimos formato "Zona A" o "Grupo A"
                letra = g.nombre.split(' ')[-1]
                grupos_map[letra] = g

            # NUEVO: Soporte para estructura explícita (Brackets asimétricos)
            if custom_format.bracket_structure:
                # Diccionario para guardar referencias a los partidos creados por su ID interno
                # Key: ID interno (int), Value: Objeto Partido
                created_matches = {}
                
                # Ordenar por ronda para crear en orden
                matches_def = sorted(custom_format.bracket_structure, key=lambda x: x['round'])
                
                for m_def in matches_def:
                    ronda_num = m_def['round']
                    match_id = m_def['id']
                    
                    # Resolver Equipo 1
                    e1 = None
                    t1_def = m_def.get('t1')
                    if t1_def:
                        if isinstance(t1_def, tuple): # ('A', 1)
                            g_letra, g_pos = t1_def
                            if g_letra in grupos_map:
                                tabla = grupos_map[g_letra].tabla.all()
                                if len(tabla) >= g_pos:
                                    e1 = tabla[g_pos-1].equipo
                        # Si es int, es un ID de partido previo, pero aquí solo asignamos equipos iniciales.
                        # Los ganadores de partidos previos se asignan vía 'siguiente_partido' en el paso de enlace.

                    # Resolver Equipo 2
                    e2 = None
                    t2_def = m_def.get('t2')
                    if t2_def:
                        if isinstance(t2_def, tuple):
                            g_letra, g_pos = t2_def
                            if g_letra in grupos_map:
                                tabla = grupos_map[g_letra].tabla.all()
                                if len(tabla) >= g_pos:
                                    e2 = tabla[g_pos-1].equipo

                    # Crear Partido
                    p = Partido.objects.create(
                        torneo=torneo,
                        ronda=ronda_num,
                        orden_partido=match_id, # Usamos el ID interno como orden por simplicidad
                        equipo1=e1,
                        equipo2=e2,
                    )
                    created_matches[match_id] = p
                
                # Enlazar partidos (siguiente_partido)
                for m_def in matches_def:
                    match_id = m_def['id']
                    next_id = m_def.get('next')
                    
                    if next_id and next_id in created_matches:
                        current_match = created_matches[match_id]
                        next_match = created_matches[next_id]
                        current_match.siguiente_partido = next_match
                        current_match.save()

                messages.success(request, f"Bracket complejo generado para {count} parejas.")
                return redirect('torneos:admin_manage', pk=torneo.pk)

            # LÓGICA LEGACY (Simétrica basada en crossings)
            # 2. Determinar ronda inicial
            if custom_format.bracket_type == 'semis':
                bracket_size = 4
                num_rondas = 2
            elif custom_format.bracket_type == 'quarters':
                bracket_size = 8
                num_rondas = 3
            elif custom_format.bracket_type == 'octavos':
                bracket_size = 16
                num_rondas = 4
            else:
                bracket_size = 4 # Default fallback
                num_rondas = 2

            ronda_inicio = 1
            partidos_por_ronda = {ronda_inicio: []}

            # 3. Generar partidos de la primera ronda según cruces
            for i, (cruce1, cruce2) in enumerate(custom_format.crossings):
                g1_letra, g1_pos = cruce1
                g2_letra, g2_pos = cruce2
                
                e1 = None
                if g1_letra in grupos_map:
                    tabla = grupos_map[g1_letra].tabla.all() # Ordenada por mérito
                    if len(tabla) >= g1_pos:
                        e1 = tabla[g1_pos-1].equipo
                
                e2 = None
                if g2_letra in grupos_map:
                    tabla = grupos_map[g2_letra].tabla.all()
                    if len(tabla) >= g2_pos:
                        e2 = tabla[g2_pos-1].equipo

                p = Partido.objects.create(
                    torneo=torneo,
                    ronda=ronda_inicio,
                    orden_partido=i + 1,
                    equipo1=e1,
                    equipo2=e2,
                )
                partidos_por_ronda[ronda_inicio].append(p)

            # 4. Generar rondas siguientes (vacías)
            for ronda_num in range(2, num_rondas + 1):
                cant_partidos = bracket_size // (2 ** ronda_num)
                partidos_por_ronda[ronda_num] = []
                
                for i in range(cant_partidos):
                    p = Partido.objects.create(
                        torneo=torneo,
                        ronda=ronda_num,
                        orden_partido=i + 1,
                    )
                    partidos_por_ronda[ronda_num].append(p)

            # 5. Enlazar partidos
            for ronda_num in range(1, num_rondas):
                partidos_actuales = partidos_por_ronda[ronda_num]
                partidos_siguientes = partidos_por_ronda.get(ronda_num + 1, [])
                
                for i, partido in enumerate(partidos_actuales):
                    if partidos_siguientes:
                        partido.siguiente_partido = partidos_siguientes[i // 2]
                        partido.save()

            messages.success(request, f"Bracket personalizado generado para {count} parejas.")
            return redirect('torneos:admin_manage', pk=torneo.pk)

        # --- LÓGICA GENÉRICA (FALLBACK) ---
        
        # 1. Obtener clasificados (1ro y 2do de cada grupo)
        primeros = []
        segundos = []
        grupos = torneo.grupos.all().order_by('nombre')

        for grupo in grupos:
            tabla = grupo.tabla.all()  # Ya viene ordenada por mérito (PG, DS, DG)
            # Clasifican los primeros 2 de cada grupo
            if len(tabla) >= 1:
                primeros.append(tabla[0].equipo)
            if len(tabla) >= 2:
                segundos.append(tabla[1].equipo)

        # Emparejamiento cruzado:
        # Rotamos la lista de segundos para que el 1ro del Grupo A no juegue con el 2do del Grupo A
        # Ejemplo con 3 grupos:
        # Primeros: [A1, B1, C1]
        # Segundos: [A2, B2, C2] -> Rotado: [B2, C2, A2]
        # Resultado: A1 vs B2, B1 vs C2, C1 vs A2
        if segundos:
            segundos = segundos[1:] + segundos[:1]

        clasificados = []
        # Intercalar: [A1, B2, B1, C2, C1, A2]
        # Usamos zip_longest por si hay diferente cantidad (aunque no debería en grupos balanceados)
        from itertools import zip_longest
        for p, s in zip_longest(primeros, segundos):
            if p: clasificados.append(p)
            if s: clasificados.append(s)

        num_equipos = len(clasificados)

        if num_equipos < 4:
            messages.error(
                request,
                f"Solo hay {num_equipos} clasificados. Se necesitan al menos 4.",
            )
            return redirect('torneos:admin_manage', pk=torneo.pk)

        # 2. Calcular tamaño del bracket (Potencia de 2)
        import math
        bracket_size = 2 ** math.ceil(math.log2(num_equipos))
        num_byes = bracket_size - num_equipos
        slots = clasificados + [None] * num_byes

        # 3. Calcular número de rondas
        # bracket_size = 4 -> 2 rondas (Semifinal=1, Final=2)
        # bracket_size = 8 -> 3 rondas (Cuartos=1, Semifinal=2, Final=3)
        # bracket_size = 16 -> 4 rondas (Octavos=1, Cuartos=2, Semifinal=3, Final=4)
        num_rondas = int(math.log2(bracket_size))
        ronda_inicio = 1  # Siempre empezamos en ronda 1
        
        # 4. Generar todas las rondas desde la primera hasta la final
        partidos_por_ronda = {}
        
        # Generar partidos de la ronda inicial (la más grande)
        cant_partidos_r1 = bracket_size // 2
        partidos_por_ronda[ronda_inicio] = []
        
        for i in range(cant_partidos_r1):
            e1 = slots.pop(0) if slots else None
            e2 = slots.pop(0) if slots else None

            p = Partido.objects.create(
                torneo=torneo,
                ronda=ronda_inicio,
                orden_partido=i + 1,
                equipo1=e1,
                equipo2=e2,
            )
            partidos_por_ronda[ronda_inicio].append(p)

            # MANEJO DE BYES
            if e1 and not e2:
                p.ganador = e1
                p.resultado = "Bye"
                p.save()
            elif not e1 and e2:
                p.ganador = e2
                p.resultado = "Bye"
                p.save()
            elif not e1 and not e2:
                p.resultado = "Bye"
                p.save()

        # 5. Generar las rondas superiores (vacías por ahora)
        for ronda_num in range(2, num_rondas + 1):
            cant_partidos = bracket_size // (2 ** ronda_num)
            partidos_por_ronda[ronda_num] = []
            
            for i in range(cant_partidos):
                p = Partido.objects.create(
                    torneo=torneo,
                    ronda=ronda_num,
                    orden_partido=i + 1,
                )
                partidos_por_ronda[ronda_num].append(p)

        # 6. Enlazar partidos con siguiente_partido
        for ronda_num in range(1, num_rondas):
            partidos_actuales = partidos_por_ronda[ronda_num]
            partidos_siguientes = partidos_por_ronda.get(ronda_num + 1, [])
            
            for i, partido in enumerate(partidos_actuales):
                if partidos_siguientes:
                    partido.siguiente_partido = partidos_siguientes[i // 2]
                    partido.save()

        messages.success(
            request, f"Bracket de {bracket_size} generado con {num_equipos} equipos."
        )
        return redirect('torneos:admin_manage', pk=torneo.pk)


# --- OTRAS VISTAS (Carga de Resultados, etc.) ---


class CargarResultadoGrupoView(AdminRequiredMixin, UpdateView):
    model = PartidoGrupo
    form_class = CargarResultadoGrupoForm
    template_name = 'torneos/cargar_resultado_grupo.html'

    def get_success_url(self):
        return reverse_lazy(
            'torneos:admin_manage', kwargs={'pk': self.object.grupo.torneo.pk}
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse('<script>window.location.reload();</script>')
        return response


class AdminPartidoUpdateView(AdminRequiredMixin, UpdateView):
    model = Partido
    form_class = PartidoResultadoForm
    template_name = 'torneos/admin_partido_form.html'
    context_object_name = 'partido'

    def get_success_url(self):
        return reverse_lazy(
            'torneos:admin_manage', kwargs={'pk': self.object.torneo.pk}
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse('<script>window.location.reload();</script>')
        return response



class SchedulePartidoGrupoView(AdminRequiredMixin, UpdateView):
    model = PartidoGrupo
    form_class = PartidoGrupoScheduleForm
    template_name = 'torneos/schedule_form.html'

    def get_success_url(self):
        return reverse_lazy(
            'torneos:admin_manage', kwargs={'pk': self.object.grupo.torneo.pk}
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse('<script>window.location.reload();</script>')
        return response


class SchedulePartidoView(AdminRequiredMixin, UpdateView):
    model = Partido
    form_class = PartidoScheduleForm
    template_name = 'torneos/schedule_form.html'

    def get_success_url(self):
        return reverse_lazy(
            'torneos:admin_manage', kwargs={'pk': self.object.torneo.pk}
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse('<script>window.location.reload();</script>')
        return response


# --- VISTAS CRUD (List, Create, Update, Detail) ---


class AdminTorneoListView(AdminRequiredMixin, ListView):
    model = Torneo
    template_name = 'torneos/admin_torneo_list.html'
    context_object_name = 'torneos'
    queryset = Torneo.objects.select_related('division').order_by('-fecha_inicio')


class AdminTorneoCreateView(AdminRequiredMixin, CreateView):
    model = Torneo
    form_class = TorneoAdminForm
    template_name = 'torneos/admin_torneo_form.html'
    success_url = reverse_lazy('torneos:admin_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Crear Nuevo Torneo"
        return context



class AdminTorneoUpdateView(AdminRequiredMixin, UpdateView):
    model = Torneo
    form_class = TorneoAdminForm
    template_name = 'torneos/admin_torneo_form.html'

    def get_success_url(self):
        return reverse_lazy('torneos:admin_manage', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f"Editar Torneo: {self.object.nombre}"
        return context


class AdminTorneoDeleteView(AdminRequiredMixin, DeleteView):
    model = Torneo
    success_url = reverse_lazy('torneos:admin_list')
    template_name = 'torneos/admin_torneo_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f"Eliminar Torneo: {self.object.nombre}"
        return context



class TorneoDetailView(DetailView):
    model = Torneo
    template_name = 'torneos/torneo_detail.html'
    context_object_name = 'torneo'
    
    def _es_division_permitida(self, equipo, torneo):
        """
        Verifica si el equipo puede inscribirse al torneo según la división.
        
        Reglas:
        - Torneos libres (division=null): cualquier equipo puede inscribirse
        - Misma división: puede inscribirse
        - División adyacente (±1): puede inscribirse
        - Otras divisiones: no puede inscribirse
        """
        if torneo.division is None:  # Torneo libre
            return True
        
        if equipo.division == torneo.division:  # Misma división
            return True
        
        # División adyacente (±1)
        if equipo.division and torneo.division:
            if hasattr(equipo.division, 'orden') and hasattr(torneo.division, 'orden'):
                diff = abs(equipo.division.orden - torneo.division.orden)
                return diff <= 1
        
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        torneo = self.object
        user = self.request.user
        grupos = torneo.grupos.all().prefetch_related(
            'tabla__equipo',
            'partidos_grupo__equipo1',
            'partidos_grupo__equipo2'
        )
        context['grupos'] = grupos
        context['partidos_eliminacion'] = torneo.partidos.all().order_by(
            'ronda', 'orden_partido'
        )
        if context['partidos_eliminacion'].exists():
            from django.db.models import Max
            max_ronda = context['partidos_eliminacion'].aggregate(Max('ronda'))['ronda__max']
            context['total_rondas'] = max_ronda if max_ronda else 0
        else:
            context['total_rondas'] = 0
        
        context['tiene_equipo'] = (
            user.is_authenticated
            and hasattr(user, 'equipo')
            and user.equipo is not None
        )
        if context['tiene_equipo']:
            equipo = user.equipo
            context['equipo'] = equipo
            context['ya_inscrito'] = Inscripcion.objects.filter(
                torneo=torneo, equipo=equipo
            ).exists()
            context['division_correcta'] = self._es_division_permitida(equipo, torneo)
            
            # Validación de Categoría
            context['categoria_correcta'] = True
            if hasattr(equipo, 'categoria') and hasattr(torneo, 'categoria'):
                if torneo.categoria and equipo.categoria != torneo.categoria:
                     context['categoria_correcta'] = False

            context['torneo_abierto'] = torneo.estado == Torneo.Estado.ABIERTO
            context['inscripcion_cerrada'] = (
                timezone.now() > torneo.fecha_limite_inscripcion
            )
            context['hay_cupos'] = torneo.inscripciones.count() < torneo.cupos_totales
            context['puede_inscribirse'] = (
                context['tiene_equipo']
                and context['torneo_abierto']
                and not context['inscripcion_cerrada']
                and context['hay_cupos']
                and not context['ya_inscrito']
                and not user.is_staff
                and context['division_correcta']  # Validación de división
                and context['categoria_correcta'] # Validación de categoría
            )

            # --- LÓGICA PARA "MIS PARTIDOS" ---
            if context['ya_inscrito']:
                # 1. Partidos de Grupo
                partidos_grupo = PartidoGrupo.objects.filter(
                    grupo__torneo=torneo
                ).filter(
                    Q(equipo1=equipo) | Q(equipo2=equipo)
                ).select_related('equipo1', 'equipo2', 'grupo')

                # 2. Partidos de Eliminación
                partidos_bracket = Partido.objects.filter(
                    torneo=torneo
                ).filter(
                    Q(equipo1=equipo) | Q(equipo2=equipo)
                ).select_related('equipo1', 'equipo2')

                mis_partidos_pendientes = []
                mis_partidos_jugados = []

                # Procesar Grupos
                for p in partidos_grupo:
                    # Un partido de grupo está jugado si tiene ganador O si se cargaron sets (empate técnico o en proceso)
                    # En este modelo, 'ganador' se setea al final. Usaremos 'ganador' como criterio de "Jugado"
                    # O si tiene resultado string. El modelo tiene 'resultado' property pero no campo persistido de estado.
                    # Chequeamos si tiene ganador asignado.
                    if p.ganador:
                        mis_partidos_jugados.append({
                            'tipo': 'Grupo',
                            'contexto': p.grupo.nombre,
                            'rival': p.equipo2 if p.equipo1 == equipo else p.equipo1,
                            'resultado': p.resultado,
                            'obj': p
                        })
                    else:
                        mis_partidos_pendientes.append({
                            'tipo': 'Grupo',
                            'contexto': p.grupo.nombre,
                            'rival': p.equipo2 if p.equipo1 == equipo else p.equipo1,
                            'obj': p
                        })

                # Procesar Bracket
                for p in partidos_bracket:
                    if p.ganador:
                        mis_partidos_jugados.append({
                            'tipo': 'Eliminatoria',
                            'contexto': p.nombre_ronda,
                            'rival': p.equipo2 if p.equipo1 == equipo else p.equipo1,
                            'resultado': p.resultado,
                            'obj': p
                        })
                    else:
                        mis_partidos_pendientes.append({
                            'tipo': 'Eliminatoria',
                            'contexto': p.nombre_ronda,
                            'rival': p.equipo2 if p.equipo1 == equipo else p.equipo1,
                            'obj': p
                        })
                
                context['mis_partidos_pendientes'] = mis_partidos_pendientes
                context['mis_partidos_jugados'] = mis_partidos_jugados

        return context


class TorneoFinalizadoListView(ListView):
    model = Torneo
    template_name = 'torneos/torneo_finalizado_list.html'
    context_object_name = 'torneos_finalizados'
    queryset = Torneo.objects.filter(estado=Torneo.Estado.FINALIZADO) \
        .select_related('division') \
        .order_by('-fecha_inicio')
    paginate_by = 10


class TorneoEnJuegoListView(ListView):
    model = Torneo
    template_name = 'torneos/torneo_en_juego_list.html'
    context_object_name = 'torneos_en_juego'
    queryset = Torneo.objects.filter(estado=Torneo.Estado.EN_JUEGO) \
        .select_related('division') \
        .order_by('-fecha_inicio')
    paginate_by = 10


class TorneoAbiertoListView(ListView):
    model = Torneo
    template_name = 'torneos/torneo_abierto_list.html'
    context_object_name = 'torneos_abiertos'
    queryset = Torneo.objects.filter(estado=Torneo.Estado.ABIERTO) \
        .select_related('division') \
        .order_by('fecha_inicio')
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated and hasattr(user, 'equipo') and user.equipo:
            # Excluir torneos donde ya está inscrito el equipo del usuario
            # Usamos values_list para ser más eficientes
            mis_inscripciones_ids = Inscripcion.objects.filter(equipo=user.equipo).values_list('torneo_id', flat=True)
            qs = qs.exclude(id__in=mis_inscripciones_ids)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['mis_torneos'] = []
        if user.is_authenticated and hasattr(user, 'equipo') and user.equipo:
             # Obtener torneos ABIERTOS donde está inscrito para la sección superior
             inscripciones = Inscripcion.objects.filter(
                 equipo=user.equipo,
                 torneo__estado=Torneo.Estado.ABIERTO
             ).select_related('torneo', 'torneo__division').order_by('torneo__fecha_inicio')
             
             # Extraemos los objetos torneo de las inscripciones
             context['mis_torneos'] = [i.torneo for i in inscripciones]

             # Obtener torneos EN JUEGO donde participa el equipo
             inscripciones_juego = Inscripcion.objects.filter(
                 equipo=user.equipo,
                 torneo__estado=Torneo.Estado.EN_JUEGO
             ).select_related('torneo', 'torneo__division').order_by('torneo__fecha_inicio')
             
             context['mis_torneos_juego'] = [i.torneo for i in inscripciones_juego]
        
        return context


import unicodedata

def normalize_division_name(name):
    """
    Normaliza el nombre de una división para comparación flexible.
    Ej: "Séptima" -> "septima", "7ma" -> "septima", "3ra" -> "tercera"
    """
    if not name:
        return ""
    
    # 1. Lowercase y quitar espacios
    norm = name.lower().strip()
    
    # 2. Quitar tildes
    norm = ''.join(c for c in unicodedata.normalize('NFD', norm) if unicodedata.category(c) != 'Mn')
    
    # 3. Mapeo de alias comunes
    aliases = {
        '1ra': 'primera', '1a': 'primera',
        '2da': 'segunda', '2a': 'segunda',
        '3ra': 'tercera', '3a': 'tercera',
        '4ta': 'cuarta', '4a': 'cuarta',
        '5ta': 'quinta', '5a': 'quinta',
        '6ta': 'sexta', '6a': 'sexta',
        '7ma': 'septima', '7a': 'septima',
        '8va': 'octava', '8a': 'octava',
    }
    
    return aliases.get(norm, norm)


class InscripcionCreateView(LoginRequiredMixin, CreateView):
    model = Inscripcion
    form_class = InscripcionForm
    template_name = 'torneos/inscripcion_form.html'

    def get_success_url(self):
        return reverse_lazy('torneos:detail', kwargs={'pk': self.kwargs['torneo_pk']})

    def dispatch(self, request, *args, **kwargs):
        self.torneo = get_object_or_404(Torneo, pk=self.kwargs['torneo_pk'])
        torneo = self.torneo

        # Verificar si el usuario tiene equipo
        try:
            equipo = request.user.equipo
            if not equipo:
                messages.warning(request, "Necesitas tener un equipo para inscribirte. Crea uno primero.")
                # Redirecting to detail instead of create to keep context, 
                # user can navigate to create from menu if needed, or we could add a link in message (complex).
                # User asked to "not be redirected anywhere" (stay in place).
                return redirect('torneos:detail', pk=torneo.pk)
            
            # Verificar División
            if torneo.division and equipo.division != torneo.division:
                messages.warning(request, f"Tu equipo es de {equipo.division} y este torneo es de {torneo.division}.")
                return redirect('torneos:detail', pk=torneo.pk)
            
            # Verificar Categoría
            if hasattr(equipo, 'categoria') and hasattr(torneo, 'categoria'):
                # Si el torneo tiene categoría (M/F/X) y el equipo no coincide
                if torneo.categoria and equipo.categoria != torneo.categoria:
                    messages.warning(
                        request, 
                        f"Tu equipo es categoría {equipo.get_categoria_display()} y este torneo es {torneo.get_categoria_display()}."
                    )
                    return redirect('torneos:detail', pk=torneo.pk)

        except Exception:
             messages.error(request, "Error al obtener tu equipo.")
             return redirect('torneos:detail', pk=torneo.pk)

        if torneo.estado != Torneo.Estado.ABIERTO:
            messages.error(request, "La inscripción está cerrada.")
            return redirect('torneos:detail', pk=torneo.pk)

        if timezone.now() > torneo.fecha_limite_inscripcion:
            messages.error(request, "La fecha límite de inscripción ha pasado.")
            return redirect('torneos:detail', pk=torneo.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['torneo'] = self.torneo
        context['equipo'] = self.request.user.equipo
        return context

    def form_valid(self, form):
        from django.db import IntegrityError
        
        torneo = self.torneo
        equipo = self.request.user.equipo
        
        # Validación extra de seguridad
        if Inscripcion.objects.filter(torneo=torneo, equipo=equipo).exists():
            messages.warning(self.request, "Tu equipo ya está inscrito en este torneo.")
            return redirect('torneos:detail', pk=torneo.pk)

        form.instance.torneo = torneo
        form.instance.equipo = equipo
        
        try:
            response = super().form_valid(form)
            messages.success(self.request, "¡Inscripción confirmada!")
            return response
        except IntegrityError:
            messages.warning(self.request, "Tu equipo ya está inscrito en este torneo.")
            return redirect('torneos:detail', pk=torneo.pk)
        except Exception as e:
            messages.error(self.request, f"Error al inscribirse: {e}")
            return redirect('torneos:detail', pk=torneo.pk)


class InscripcionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Inscripcion
    
    def get_object(self):
        # Obtener la inscripción basada en el torneo y el equipo del usuario
        torneo_pk = self.kwargs.get('torneo_pk')
        torneo = get_object_or_404(Torneo, pk=torneo_pk)
        
        if not hasattr(self.request.user, 'equipo') or not self.request.user.equipo:
            raise Http404("No tienes equipo.")
            
        return get_object_or_404(Inscripcion, torneo=torneo, equipo=self.request.user.equipo)

    def test_func(self):
        inscripcion = self.get_object()
        # Verificar que el torneo esté abierto
        if inscripcion.torneo.estado != Torneo.Estado.ABIERTO:
            return False
        return True
        
    def handle_no_permission(self):
        messages.error(self.request, "No puedes cancelar la inscripción de este torneo (ya comenzó o no estás inscrito).")
        return redirect('torneos:detail', pk=self.kwargs['torneo_pk'])

    def post(self, request, *args, **kwargs):
        inscripcion = self.get_object()
        torneo_pk = inscripcion.torneo.pk
        inscripcion.delete()
        messages.success(request, "Inscripción cancelada exitosamente.")
        return redirect('torneos:detail', pk=torneo_pk)

# --- UTILIDAD: Crear Torneo de Prueba ---

@login_required
def crear_torneo_prueba(request):
    """
    Vista protegida para admins que crea un torneo de prueba con 24 equipos.
    Accesible desde la interfaz web sin necesidad de shell.
    """
    # Verificar que el usuario sea admin
    if request.user.tipo_usuario != 'ADMIN':
        messages.error(request, "Acceso denegado: solo administradores.")
        return redirect('core:home')
    
    from accounts.models import Division
    from django.contrib.auth import get_user_model
    from datetime import timedelta
    import string
    
    User = get_user_model()
    
    # Limpiar datos de prueba anteriores
    Torneo.objects.filter(nombre__startswith="Torneo 24 Equipos").delete()
    User.objects.filter(email__contains='@ejemplo.com').delete()
    
    # Crear división
    division, _ = Division.objects.get_or_create(nombre="Séptima")
    
    # Crear torneo
    torneo_nombre = f"Torneo 24 Equipos - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    torneo = Torneo.objects.create(
        nombre=torneo_nombre,
        division=division,
        fecha_inicio=timezone.now().date(),
        fecha_limite_inscripcion=timezone.now() + timedelta(days=7),
        cupos_totales=24,
        equipos_por_grupo=3,
        estado=Torneo.Estado.ABIERTO
    )
    
    # Crear 24 equipos
    for i in range(1, 25):
        sufijo = string.ascii_lowercase[i % 26] if i > 26 else ''
        email1 = f"jugador{i}a{sufijo}@ejemplo.com"
        email2 = f"jugador{i}b{sufijo}@ejemplo.com"
        
        jugador1 = User.objects.create_user(
            email=email1,
            nombre=f'Jugador{i}A',
            apellido=f'Sim{i}A',
            division=division,
            tipo_usuario='PLAYER',
            password='sim123456'
        )
        
        jugador2 = User.objects.create_user(
            email=email2,
            nombre=f'Jugador{i}B',
            apellido=f'Sim{i}B',
            division=division,
            tipo_usuario='PLAYER',
            password='sim123456'
        )
        
        equipo = Equipo.objects.create(
            jugador1=jugador1,
            jugador2=jugador2,
            division=division
        )
        
        Inscripcion.objects.create(
            torneo=torneo,
            equipo=equipo
        )
    
    messages.success(
        request, 
        f"✓ Torneo de prueba creado con 24 equipos. "
        f"Ahora puedes iniciar el torneo para crear los grupos."
    )
    return redirect('torneos:admin_manage', pk=torneo.pk)


class ReplacePartidoTeamsView(AdminRequiredMixin, UpdateView):
    model = Partido
    form_class = PartidoReplaceTeamsForm
    template_name = 'torneos/replace_teams_form.html'

    def get_success_url(self):
        return reverse_lazy(
            'torneos:admin_manage', kwargs={'pk': self.object.torneo.pk}
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse('<script>window.location.reload();</script>')
        return response


class ReplacePartidoGrupoTeamsView(AdminRequiredMixin, UpdateView):
    model = PartidoGrupo
    form_class = PartidoGrupoReplaceTeamsForm
    template_name = 'torneos/replace_teams_form.html'

    def get_success_url(self):
        return reverse_lazy(
            'torneos:admin_manage', kwargs={'pk': self.object.grupo.torneo.pk}
        )

    def form_valid(self, form):
        # Obtener los equipos ANTES de guardar el formulario
        old_equipo1 = self.get_object().equipo1
        old_equipo2 = self.get_object().equipo2
        
        response = super().form_valid(form)
        
        # Obtener los equipos NUEVOS del objeto ya guardado
        new_equipo1 = self.object.equipo1
        new_equipo2 = self.object.equipo2
        
        grupo = self.object.grupo
        
        # Lógica para Equipo 1
        if old_equipo1 != new_equipo1:
            self._handle_team_change(grupo, old_equipo1, new_equipo1)

        # Lógica para Equipo 2
        if old_equipo2 != new_equipo2:
            self._handle_team_change(grupo, old_equipo2, new_equipo2)

        if self.request.headers.get('HX-Request'):
            return HttpResponse('<script>window.location.reload();</script>')
        return response

    def _handle_team_change(self, current_group, old_team, new_team):
        """
        Maneja el cambio de equipo, incluyendo el intercambio si el nuevo equipo
        ya pertenece a otro grupo.
        """
        # 1. Verificar si el nuevo equipo ya está en otro grupo del mismo torneo
        other_group_entry = new_team.tabla.filter(grupo__torneo=current_group.torneo).first()
        
        if other_group_entry and other_group_entry.grupo != current_group:
            # --- ESCENARIO DE INTERCAMBIO (SWAP) ---
            other_group = other_group_entry.grupo
            
            # A. Actualizar Grupo Actual: old_team -> new_team (Ya hecho parcialmente por el form, pero falta EquipoGrupo)
            current_entry = current_group.tabla.filter(equipo=old_team).first()
            if current_entry:
                current_entry.equipo = new_team
                current_entry.save()
                
            # B. Actualizar Otro Grupo: new_team -> old_team
            # (other_group_entry es la entrada de new_team en el otro grupo)
            other_group_entry.equipo = old_team
            other_group_entry.save()
            
            # C. Actualizar partidos en Grupo Actual (old_team -> new_team)
            # (Excluyendo el partido actual que ya se actualizó)
            current_matches = current_group.partidos_grupo.exclude(pk=self.object.pk)
            current_matches.filter(equipo1=old_team).update(equipo1=new_team)
            current_matches.filter(equipo2=old_team).update(equipo2=new_team)
            
            # D. Actualizar partidos en Otro Grupo (new_team -> old_team)
            other_matches = other_group.partidos_grupo.all()
            other_matches.filter(equipo1=new_team).update(equipo1=old_team)
            other_matches.filter(equipo2=new_team).update(equipo2=old_team)
            
        else:
            # --- ESCENARIO DE REEMPLAZO SIMPLE ---
            # (El nuevo equipo no estaba en ningún grupo, ej: reserva)
            
            # 1. Actualizar EquipoGrupo: Reemplazar old_team por new_team
            equipo_grupo = current_group.tabla.filter(equipo=old_team).first()
            if equipo_grupo:
                equipo_grupo.equipo = new_team
                equipo_grupo.save()
            
            # 2. Actualizar otros partidos del grupo
            otros_partidos = current_group.partidos_grupo.exclude(pk=self.object.pk)
            otros_partidos.filter(equipo1=old_team).update(equipo1=new_team)
            otros_partidos.filter(equipo2=old_team).update(equipo2=new_team)


from .forms import SwapGroupTeamsForm
from django.views.generic import FormView

class SwapGroupTeamsView(AdminRequiredMixin, FormView):
    template_name = 'torneos/replace_teams_form.html'
    form_class = SwapGroupTeamsForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        grupo = get_object_or_404(Grupo, pk=self.kwargs['pk'])
        kwargs['grupo'] = grupo
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Intercambiar Equipos de Grupo"
        return context

    def form_valid(self, form):
        grupo = get_object_or_404(Grupo, pk=self.kwargs['pk'])
        equipo_origen = form.cleaned_data['equipo_origen']
        equipo_destino = form.cleaned_data['equipo_destino']
        
        # Lógica de Intercambio (Swap)
        # 1. Identificar el grupo del equipo destino
        other_group_entry = equipo_destino.equipogrupo_set.filter(grupo__torneo=grupo.torneo).first()
        
        if other_group_entry:
            other_group = other_group_entry.grupo
            
            # A. Actualizar EquipoGrupo (Tablas de posiciones)
            # Origen -> Destino
            entry_origen = grupo.tabla.filter(equipo=equipo_origen).first()
            if entry_origen:
                entry_origen.equipo = equipo_destino
                entry_origen.save()
            
            # Destino -> Origen
            other_group_entry.equipo = equipo_origen
            other_group_entry.save()
            
            # B. Actualizar Partidos
            # Grupo Actual: equipo_origen -> equipo_destino
            matches_origen = grupo.partidos_grupo.all()
            matches_origen.filter(equipo1=equipo_origen).update(equipo1=equipo_destino)
            matches_origen.filter(equipo2=equipo_origen).update(equipo2=equipo_destino)
            
            # Otro Grupo: equipo_destino -> equipo_origen
            matches_destino = other_group.partidos_grupo.all()
            matches_destino.filter(equipo1=equipo_destino).update(equipo1=equipo_origen)
            matches_destino.filter(equipo2=equipo_destino).update(equipo2=equipo_origen)

        if self.request.headers.get('HX-Request'):
            return HttpResponse('<script>window.location.reload();</script>')
        
        return super().form_valid(form)

    def get_success_url(self):
        grupo = get_object_or_404(Grupo, pk=self.kwargs['pk'])
        return reverse_lazy('torneos:admin_manage', kwargs={'pk': grupo.torneo.pk})
