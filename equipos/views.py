from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, DeleteView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from .models import Equipo
from accounts.models import Division, CustomUser
from .forms import EquipoCreateForm
from django.db.models import Q  # Importamos Q de forma limpia
from django.db import models  # <--- ¡CORRECCIÓN! Importamos models desde django.db

# IMPORTANTE: Importar las vistas de autocompletado
from dal import autocomplete


# --- Mixins de Permisos ---
class PlayerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Verifica que el usuario sea un 'PLAYER'"""

    def test_func(self):
        return self.request.user.tipo_usuario == 'PLAYER'

    def handle_no_permission(self):
        messages.error(
            self.request, "Debes ser un jugador para acceder a esta sección."
        )
        return redirect(reverse_lazy('core:home'))


class PlayerHasNoTeamMixin(PlayerRequiredMixin):
    """Verifica que el jugador NO tenga equipo. Para CreateView."""

    def test_func(self):
        if not super().test_func():
            return False
        # FIX: Usamos el método equipo del modelo CustomUser
        return self.request.user.equipo is None

    def handle_no_permission(self):
        messages.warning(self.request, "Ya tienes un equipo.")
        return redirect('equipos:mi_equipo')


class PlayerOwnsTeamMixin(PlayerRequiredMixin):
    """Verifica que el jugador sea dueño del equipo que intenta ver/borrar."""

    def get_object(self, queryset=None):
        # Devuelve el equipo del usuario logueado para usar en test_func
        return self.request.user.equipo

    def test_func(self):
        if not super().test_func():
            return False

        equipo = self.request.user.equipo
        # El mixin base de DetailView/DeleteView necesita un objeto para test_func
        return equipo is not None

    def handle_no_permission(self):
        messages.error(self.request, "Acceso denegado o no tienes equipo.")
        return redirect(reverse_lazy('equipos:mi_equipo'))


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Verifica que el usuario sea un 'ADMIN'"""

    def test_func(self):
        return self.request.user.tipo_usuario == 'ADMIN'

    def handle_no_permission(self):
        messages.error(self.request, "Acceso denegado: solo administradores.")
        return redirect(reverse_lazy('core:home'))


# --- Vistas de Autocompletado (NUEVAS) ---


class JugadorAutocomplete(autocomplete.Select2QuerySetView):
    """
    Vista AJAX que devuelve jugadores de la misma división para el autocompletado.
    """

    def get_queryset(self):
        # Aseguramos que solo los usuarios logueados puedan buscar
        if (
            not self.request.user.is_authenticated
            or self.request.user.tipo_usuario != 'PLAYER'
        ):
            return CustomUser.objects.none()

        user = self.request.user

        # 1. Base Query: Mismos filtros que en EquipoCreateForm (División y tipo)
        qs = CustomUser.objects.filter(
            division=user.division, tipo_usuario='PLAYER'
        ).exclude(
            id=user.id  # Excluirse a sí mismo
        )

        # 2. FILTRO CLAVE: Excluir a los jugadores que ya aparecen como jugador1 O jugador2 en CUALQUIER equipo
        # Usamos las relaciones inversas explícitas (related_name)
        qs = qs.exclude(
            Q(equipos_como_jugador1__isnull=False)
            | Q(equipos_como_jugador2__isnull=False)
        )

        # 3. Aplicamos el filtro de búsqueda del usuario (q)
        if self.q:
            # Búsqueda por nombre O apellido (Case insensitive: icontains)
            qs = qs.filter(Q(nombre__icontains=self.q) | Q(apellido__icontains=self.q))

        return qs


# --- Vistas de Jugador ---


class MiEquipoDetailView(LoginRequiredMixin, DetailView):
    model = Equipo
    template_name = 'equipos/mi_equipo_detail.html'
    context_object_name = 'equipo'

    def get_object(self, queryset=None):
        """Devuelve el equipo del usuario logueado con relaciones precargadas."""
        equipo = self.request.user.equipo
        if equipo:
            # Precarga jugador1, jugador2 y division para evitar queries extras
            return Equipo.objects.select_related(
                'jugador1', 'jugador2', 'division'
            ).get(pk=equipo.pk)
        return None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            messages.info(request, "Aún no tienes un equipo. ¡Crea uno!")
            return redirect('equipos:crear')

        # Redirigir a crear si no tiene equipo
        if not self.object:
            return redirect('equipos:crear')

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
    
    def get_context_data(self, **kwargs):
        """Añade estadísticas del equipo al contexto"""
        context = super().get_context_data(**kwargs)
        equipo = self.get_object()
        
        if equipo:
            context['stats'] = {
                'partidos_jugados': equipo.get_partidos_jugados()['total'],
                'victorias': equipo.get_victorias(),
                'derrotas': equipo.get_derrotas(),
                'win_rate': equipo.get_win_rate(),
                'torneos_ganados': equipo.get_torneos_ganados(),
                'racha': equipo.get_racha_actual(),
                'ultimos_resultados': equipo.get_ultimos_resultados(),
            }
        
        return context


class EquipoCreateView(PlayerHasNoTeamMixin, CreateView):
    model = Equipo
    form_class = EquipoCreateForm
    template_name = 'equipos/equipo_form.html'
    success_url = reverse_lazy('equipos:mi_equipo')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Crear Nuevo Equipo"
        # ¡IMPORTANTE! Necesitamos el objeto usuario en el contexto
        context['user'] = self.request.user
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pasamos el usuario logueado al formulario para filtrar la división
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Asignamos al usuario logueado como jugador1
        form.instance.jugador1 = self.request.user
        messages.success(
            self.request,
            f"¡El equipo '{form.instance.nombre}' fue creado exitosamente!",
        )
        return super().form_valid(form)


class EquipoDeleteView(PlayerOwnsTeamMixin, DeleteView):
    model = Equipo
    template_name = 'equipos/equipo_confirm_delete.html'
    success_url = reverse_lazy('core:home')
    context_object_name = 'equipo'

    def get_object(self, queryset=None):
        # Obtenemos el equipo del usuario (validado por PlayerOwnsTeamMixin)
        return self.request.user.equipo

    def form_valid(self, form):
        messages.success(
            self.request, f"El equipo '{self.object.nombre}' ha sido disuelto."
        )
        return super().form_valid(form)


# --- Vistas de Admin ---


class AdminEquipoListView(AdminRequiredMixin, ListView):
    model = Equipo
    template_name = 'equipos/admin_equipo_list.html'
    context_object_name = 'equipos'
    paginate_by = 20

    def get_queryset(self):
        queryset = Equipo.objects.all().select_related(
            'jugador1', 'jugador2', 'division'
        )

        # Filtro por división
        division_id = self.request.GET.get('division')
        if division_id:
            queryset = queryset.filter(division_id=division_id)

        # Búsqueda por nombre de equipo
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(nombre__icontains=search_query)

        return queryset.order_by('nombre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['divisiones'] = Division.objects.all()
        context['current_division'] = self.request.GET.get('division')
        context['search_query'] = self.request.GET.get('search', '')
        return context


# --- Vista de Rankings ---


class RankingListView(ListView):
    model = Equipo
    template_name = 'equipos/ranking_list.html'
    context_object_name = 'rankings_por_division'
    
    def get_queryset(self):
        from django.db.models import Count, Q, F, Case, When, IntegerField, FloatField, Value
        from django.core.cache import cache
        
        # Obtener división seleccionada del parámetro GET
        division_id = self.request.GET.get('division')
        
        # Crear clave de cache única
        cache_key = f'rankings_v2_{"all" if not division_id else f"div_{division_id}"}'
        
        # Intentar obtener del cache
        cached_rankings = cache.get(cache_key)
        if cached_rankings is not None:
            return cached_rankings
        
        # Filtrar divisiones
        if division_id:
            divisiones = Division.objects.filter(id=division_id)
        else:
            divisiones = Division.objects.all().order_by('nombre')
        
        rankings_por_division = []
        
        for division in divisiones:
            # --- LÓGICA DE RANKING POR DIVISIÓN ---
            # Ahora iteramos sobre TODOS los equipos, pero calculamos sus puntos
            # basándonos ÚNICAMENTE en su desempeño en torneos de ESTA división.
            
            equipos_con_stats = Equipo.objects.all().select_related(
                'jugador1', 'jugador2', 'division'
            ).annotate(
                # 1. Victorias en Eliminación (Solo torneos de esta división)
                victorias_eliminacion=Count(
                    'partidos_bracket_ganados',
                    filter=Q(
                        partidos_bracket_ganados__isnull=False,
                        partidos_bracket_ganados__torneo__division=division
                    ),
                    distinct=True
                ),
                # 2. Victorias en Grupos (Solo torneos de esta división)
                victorias_grupo=Count(
                    'partidos_grupo_ganados',
                    filter=Q(
                        partidos_grupo_ganados__isnull=False,
                        partidos_grupo_ganados__grupo__torneo__division=division
                    ),
                    distinct=True
                ),
                # 3. Partidos jugados en Eliminación (Solo torneos de esta división)
                partidos_elim_1=Count(
                    'partidos_bracket_e1',
                    filter=Q(
                        partidos_bracket_e1__ganador__isnull=False,
                        partidos_bracket_e1__torneo__division=division
                    ),
                    distinct=True
                ),
                partidos_elim_2=Count(
                    'partidos_bracket_e2',
                    filter=Q(
                        partidos_bracket_e2__ganador__isnull=False,
                        partidos_bracket_e2__torneo__division=division
                    ),
                    distinct=True
                ),
                # 4. Partidos jugados en Grupos (Solo torneos de esta división)
                partidos_grupo_1=Count(
                    'partidos_grupo_e1',
                    filter=Q(
                        partidos_grupo_e1__ganador__isnull=False,
                        partidos_grupo_e1__grupo__torneo__division=division
                    ),
                    distinct=True
                ),
                partidos_grupo_2=Count(
                    'partidos_grupo_e2',
                    filter=Q(
                        partidos_grupo_e2__ganador__isnull=False,
                        partidos_grupo_e2__grupo__torneo__division=division
                    ),
                    distinct=True
                ),
                # 5. Torneos Ganados (Solo de esta división)
                torneos_ganados_count=Count(
                    'torneos_ganados',
                    filter=Q(torneos_ganados__division=division),
                    distinct=True
                )
            )
            
            # Procesar equipos y calcular métricas
            equipos_con_puntos = []
            for equipo in equipos_con_stats:
                # Calcular totales
                victorias_total = equipo.victorias_eliminacion + equipo.victorias_grupo
                partidos_total = (equipo.partidos_elim_1 + equipo.partidos_elim_2 + 
                                 equipo.partidos_grupo_1 + equipo.partidos_grupo_2)
                
                # Calcular win rate
                if partidos_total > 0:
                    win_rate = round((victorias_total / partidos_total) * 100, 1)
                else:
                    win_rate = 0
                
                # Calcular puntos de ranking
                puntos = victorias_total * 3  # 3 puntos por victoria
                puntos += equipo.torneos_ganados_count * 50  # 50 puntos por torneo ganado
                
                # Bonus por win rate alto (Solo si jugó suficientes partidos en esta división)
                if win_rate >= 75 and partidos_total >= 5:
                    puntos += 20
                
                # Solo incluir equipos con PUNTOS en esta división
                if puntos > 0:
                    equipos_con_puntos.append({
                        'equipo': equipo,
                        'puntos': puntos,
                        'victorias': victorias_total,
                        'win_rate': win_rate,
                        'torneos_ganados': equipo.torneos_ganados_count,
                        'partidos_jugados': partidos_total # Útil para debug
                    })
            
            # Ordenar por puntos
            equipos_con_puntos.sort(key=lambda x: x['puntos'], reverse=True)
            
            # Agregar posición
            for i, item in enumerate(equipos_con_puntos, 1):
                item['posicion'] = i
            
            # Solo agregar división si tiene equipos con actividad
            if equipos_con_puntos:
                rankings_por_division.append({
                    'division': division,
                    'equipos': equipos_con_puntos
                })
        
        # Guardar en cache por 5 minutos
        cache.set(cache_key, rankings_por_division, 300)
        
        return rankings_por_division
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar todas las divisiones para el filtro
        context['divisiones'] = Division.objects.all().order_by('nombre')
        context['division_seleccionada'] = self.request.GET.get('division')
        
        # Agregar información del equipo del usuario si está autenticado
        if self.request.user.is_authenticated and hasattr(self.request.user, 'equipo') and self.request.user.equipo:
            context['mi_equipo'] = self.request.user.equipo
        
        return context
