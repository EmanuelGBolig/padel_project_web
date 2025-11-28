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
)
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
        return self.request.user.tipo_usuario == 'ADMIN'

    def handle_no_permission(self):
        messages.error(self.request, "Acceso denegado: solo administradores.")
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

        return context

    def post(self, request, *args, **kwargs):
        torneo = self.get_object()
        action = request.POST.get('action')

        if action == 'iniciar_torneo':
            return self.iniciar_torneo_logica(request, torneo)

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

        # Usar el tamaño de grupo configurado en el torneo
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

        torneo.estado = Torneo.Estado.EN_JUEGO
        torneo.save()
        messages.success(
            request, f"Fase de Grupos generada: {num_grupos} grupos creados."
        )
        return redirect('torneos:admin_manage', pk=torneo.pk)

    def generar_octavos_logica(self, request, torneo):
        # Permitir regeneración si se eliminaron los partidos
        # if torneo.partidos.exists():
        #     messages.warning(request, "La fase de eliminación ya fue generada.")
        #     return redirect('torneos:admin_manage', pk=torneo.pk)

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
            context['total_rondas'] = context['partidos_eliminacion'].aggregate(Max('ronda'))['ronda__max']
        
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
            context['division_correcta'] = equipo.division == torneo.division
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
                and context['division_correcta']
                and not context['ya_inscrito']
                and not user.is_staff
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
                messages.error(request, "Necesitas tener un equipo para inscribirte.")
                return redirect('equipos:create')
        except Exception:
             messages.error(request, "Error al obtener tu equipo.")
             return redirect('home')

        if Inscripcion.objects.filter(torneo=torneo, equipo=equipo).exists():
            messages.warning(request, "Tu equipo ya está inscrito.")
            return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))
        
        # --- VERIFICACIÓN DE DIVISIÓN FLEXIBLE ---
        equipo_div_norm = normalize_division_name(equipo.division.nombre)
        torneo_div_norm = normalize_division_name(torneo.division.nombre)
        
        if equipo_div_norm != torneo_div_norm:
             # Fallback: si la normalización falla, chequear IDs por si acaso son el mismo objeto exacto
             if equipo.division_id != torneo.division_id:
                messages.error(request, f"División incorrecta. Tu equipo es {equipo.division} y el torneo es {torneo.division}.")
                return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))

        if torneo.inscripciones.count() >= torneo.cupos_totales:
            messages.error(request, "Torneo lleno.")
            return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))
            
        if torneo.estado != Torneo.Estado.ABIERTO:
            messages.error(request, "La inscripción está cerrada.")
            return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))

        if timezone.now() > torneo.fecha_limite_inscripcion:
            messages.error(request, "La fecha límite de inscripción ha pasado.")
            return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['torneo'] = self.torneo
        context['equipo'] = self.request.user.equipo
        return context

    def form_valid(self, form):
        form.instance.torneo = self.torneo
        form.instance.equipo = self.request.user.equipo
        messages.success(self.request, "¡Inscripción confirmada!")
        return super().form_valid(form)


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
