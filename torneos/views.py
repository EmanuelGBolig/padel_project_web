from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView
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
        if torneo.partidos.exists():
            messages.warning(request, "La fase de eliminación ya fue generada.")
            return redirect('torneos:admin_manage', pk=torneo.pk)

        # 1. Obtener clasificados (1ro y 2do de cada grupo)
        clasificados = []
        grupos = torneo.grupos.all().order_by('nombre')

        for grupo in grupos:
            tabla = grupo.tabla.all()  # Ya viene ordenada por mérito (PG, DS, DG)
            # Clasifican los primeros 2 de cada grupo (estándar para grupos de 3 o 4 equipos)
            num_clasificados_por_grupo = 2
            for i in range(min(len(tabla), num_clasificados_por_grupo)):
                clasificados.append(tabla[i].equipo)

        num_equipos = len(clasificados)

        if num_equipos < 4:
            messages.error(
                request,
                f"Solo hay {num_equipos} clasificados. Se necesitan al menos 4.",
            )
            return redirect('torneos:admin_manage', pk=torneo.pk)

        # 2. Calcular tamaño del bracket (Potencia de 2)
        num_byes = bracket_size - num_equipos
        slots = clasificados + [None] * num_byes

        cant_partidos_r1 = bracket_size // 2

        for i in range(cant_partidos_r1):
            e1 = slots.pop(0)
            e2 = slots.pop(0)

            p = Partido.objects.create(
                torneo=torneo,
                ronda=ronda_inicio,
                orden_partido=i + 1,
                equipo1=e1,
                equipo2=e2,
                # Enlazar con la siguiente ronda (que creamos en el bucle)
                siguiente_partido=(
                    partidos_ronda_superior[i // 2] if partidos_ronda_superior else None
                ),
            )

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


# --- VISTAS CRUD (List, Create, Update, Detail) ---


class AdminTorneoListView(AdminRequiredMixin, ListView):
    model = Torneo
    template_name = 'torneos/admin_torneo_list.html'
    context_object_name = 'torneos'
    queryset = Torneo.objects.all().order_by('-fecha_inicio')


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


class TorneoDetailView(DetailView):
    model = Torneo
    template_name = 'torneos/torneo_detail.html'
    context_object_name = 'torneo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        torneo = self.object
        user = self.request.user
        grupos = torneo.grupos.all().prefetch_related('tabla__equipo', 'partidos_grupo')
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
            )
        return context


class TorneoFinalizadoListView(ListView):
    model = Torneo
    template_name = 'torneos/torneo_finalizado_list.html'
    context_object_name = 'torneos_finalizados'
    queryset = Torneo.objects.filter(estado=Torneo.Estado.FINALIZADO).order_by(
        '-fecha_inicio'
    )
    paginate_by = 10


class InscripcionCreateView(PlayerRequiredMixin, CreateView):
    model = Inscripcion
    form_class = InscripcionForm
    template_name = 'torneos/inscripcion_form.html'

    def get_success_url(self):
        return reverse_lazy('torneos:detail', kwargs={'pk': self.kwargs['torneo_pk']})

    def get_torneo(self):
        return get_object_or_404(Torneo, pk=self.kwargs['torneo_pk'])

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'equipo') or not request.user.equipo:
            messages.error(request, "Debes tener un equipo creado para inscribirte.")
            return redirect(reverse_lazy('equipos:crear'))
        torneo = self.get_torneo()
        equipo = request.user.equipo
        if torneo.estado != Torneo.Estado.ABIERTO:
            messages.error(request, "La inscripción está cerrada.")
            return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))
        if Inscripcion.objects.filter(torneo=torneo, equipo=equipo).exists():
            messages.warning(request, "Tu equipo ya está inscrito.")
            return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))
        if equipo.division != torneo.division:
            messages.error(request, "División incorrecta.")
            return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))
        if torneo.inscripciones.count() >= torneo.cupos_totales:
            messages.error(request, "Torneo lleno.")
            return redirect(reverse_lazy('torneos:detail', kwargs={'pk': torneo.pk}))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['torneo'] = self.get_torneo()
        context['equipo'] = self.request.user.equipo
        return context

    def form_valid(self, form):
        form.instance.torneo = self.get_torneo()
        form.instance.equipo = self.request.user.equipo
        messages.success(self.request, "¡Inscripción confirmada!")
        return super().form_valid(form)
