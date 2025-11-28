from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, ListView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserProfileForm, CustomLoginForm


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomLoginForm
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('core:home')


class RegistroView(CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'accounts/registro.html'
    success_url = reverse_lazy('accounts:login')


class PerfilView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserProfileForm
    template_name = 'accounts/perfil.html'
    success_url = reverse_lazy('accounts:perfil')

    def get_object(self, queryset=None):
        # Devuelve el usuario actualmente logueado con división precargada
        return CustomUser.objects.select_related('division').get(pk=self.request.user.pk)


class RankingJugadoresListView(ListView):
    """Vista optimizada de rankings de jugadores individuales"""
    model = CustomUser
    template_name = 'accounts/ranking_jugadores_list.html'
    context_object_name = 'rankings_por_division'
    
    def get_queryset(self):
        from django.db.models import Count, Q
        from django.core.cache import cache
        from equipos.models import Division
        
        # Obtener división seleccionada del parámetro GET
        division_id = self.request.GET.get('division')
        
        # Crear clave de cache única
        cache_key = f'rankings_jugadores_{"all" if not division_id else f"div_{division_id}"}'
        
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
            # Obtener jugadores que tienen equipo en esta división
            jugadores_con_stats = CustomUser.objects.filter(
                Q(equipo_jugador1__division=division) | Q(equipo_jugador2__division=division)
            ).distinct().annotate(
                # Victorias como jugador1 en partidos de eliminación
                victorias_j1_elim=Count(
                    'equipo_jugador1__partidos_bracket_ganados',
                    filter=Q(equipo_jugador1__partidos_bracket_ganados__isnull=False),
                    distinct=True
                ),
                # Victorias como jugador1 en partidos de grupo
                victorias_j1_grupo=Count(
                    'equipo_jugador1__partidos_grupo_ganados',
                    filter=Q(equipo_jugador1__partidos_grupo_ganados__isnull=False),
                    distinct=True
                ),
                # Victorias como jugador2 en partidos de eliminación
                victorias_j2_elim=Count(
                    'equipo_jugador2__partidos_bracket_ganados',
                    filter=Q(equipo_jugador2__partidos_bracket_ganados__isnull=False),
                    distinct=True
                ),
                # Victorias como jugador2 en partidos de grupo
                victorias_j2_grupo=Count(
                    'equipo_jugador2__partidos_grupo_ganados',
                    filter=Q(equipo_jugador2__partidos_grupo_ganados__isnull=False),
                    distinct=True
                ),
                # Partidos jugados como jugador1 en eliminación
                partidos_j1_elim_1=Count(
                    'equipo_jugador1__partidos_bracket_e1',
                    filter=Q(equipo_jugador1__partidos_bracket_e1__ganador__isnull=False),
                    distinct=True
                ),
                partidos_j1_elim_2=Count(
                    'equipo_jugador1__partidos_bracket_e2',
                    filter=Q(equipo_jugador1__partidos_bracket_e2__ganador__isnull=False),
                    distinct=True
                ),
                # Partidos jugados como jugador1 en grupo
                partidos_j1_grupo_1=Count(
                    'equipo_jugador1__partidos_grupo_e1',
                    filter=Q(equipo_jugador1__partidos_grupo_e1__ganador__isnull=False),
                    distinct=True
                ),
                partidos_j1_grupo_2=Count(
                    'equipo_jugador1__partidos_grupo_e2',
                    filter=Q(equipo_jugador1__partidos_grupo_e2__ganador__isnull=False),
                    distinct=True
                ),
                # Partidos jugados como jugador2 en eliminación
                partidos_j2_elim_1=Count(
                    'equipo_jugador2__partidos_bracket_e1',
                    filter=Q(equipo_jugador2__partidos_bracket_e1__ganador__isnull=False),
                    distinct=True
                ),
                partidos_j2_elim_2=Count(
                    'equipo_jugador2__partidos_bracket_e2',
                    filter=Q(equipo_jugador2__partidos_bracket_e2__ganador__isnull=False),
                    distinct=True
                ),
                # Partidos jugados como jugador2 en grupo
                partidos_j2_grupo_1=Count(
                    'equipo_jugador2__partidos_grupo_e1',
                    filter=Q(equipo_jugador2__partidos_grupo_e1__ganador__isnull=False),
                    distinct=True
                ),
                partidos_j2_grupo_2=Count(
                    'equipo_jugador2__partidos_grupo_e2',
                    filter=Q(equipo_jugador2__partidos_grupo_e2__ganador__isnull=False),
                    distinct=True
                ),
                # Torneos ganados
                torneos_j1=Count('equipo_jugador1__torneos_ganados', distinct=True),
                torneos_j2=Count('equipo_jugador2__torneos_ganados', distinct=True),
            )
            
            # Procesar jugadores y calcular métricas
            jugadores_con_puntos = []
            for jugador in jugadores_con_stats:
                # Calcular totales
                victorias_total = (jugador.victorias_j1_elim + jugador.victorias_j1_grupo +
                                  jugador.victorias_j2_elim + jugador.victorias_j2_grupo)
                
                partidos_total = (jugador.partidos_j1_elim_1 + jugador.partidos_j1_elim_2 +
                                 jugador.partidos_j1_grupo_1 + jugador.partidos_j1_grupo_2 +
                                 jugador.partidos_j2_elim_1 + jugador.partidos_j2_elim_2 +
                                 jugador.partidos_j2_grupo_1 + jugador.partidos_j2_grupo_2)
                
                torneos_ganados = jugador.torneos_j1 + jugador.torneos_j2
                
                # Calcular win rate
                if partidos_total > 0:
                    win_rate = round((victorias_total / partidos_total) * 100, 1)
                else:
                    win_rate = 0
                
                # Calcular puntos de ranking
                puntos = victorias_total * 3  # 3 puntos por victoria
                puntos += torneos_ganados * 50  # 50 puntos por torneo ganado
                
                # Bonus por win rate alto (más estricto para jugadores)
                if win_rate >= 75 and partidos_total >= 10:
                    puntos += 20
                
                # Solo incluir jugadores con actividad
                if puntos > 0:
                    # Obtener equipo(s) actual(es) del jugador en esta división
                    equipos_actuales = []
                    if hasattr(jugador, 'equipo') and jugador.equipo and jugador.equipo.division == division:
                        equipos_actuales.append(jugador.equipo)
                    
                    jugadores_con_puntos.append({
                        'jugador': jugador,
                        'puntos': puntos,
                        'victorias': victorias_total,
                        'win_rate': win_rate,
                        'torneos_ganados': torneos_ganados,
                        'equipos': equipos_actuales,
                        'partidos_totales': partidos_total
                    })
            
            # Ordenar por puntos
            jugadores_con_puntos.sort(key=lambda x: x['puntos'], reverse=True)
            
            # Agregar posición
            for i, item in enumerate(jugadores_con_puntos, 1):
                item['posicion'] = i
            
            # Solo agregar división si tiene jugadores con actividad
            if jugadores_con_puntos:
                rankings_por_division.append({
                    'division': division,
                    'jugadores': jugadores_con_puntos
                })
        
        # Guardar en cache por 5 minutos
        cache.set(cache_key, rankings_por_division, 300)
        
        return rankings_por_division
    
    def get_context_data(self, **kwargs):
        from equipos.models import Division
        context = super().get_context_data(**kwargs)
        
        # Agregar todas las divisiones para el filtro
        context['divisiones'] = Division.objects.all().order_by('nombre')
        context['division_seleccionada'] = self.request.GET.get('division')
        
        # Agregar información del usuario autenticado
        if self.request.user.is_authenticated:
            context['usuario_actual'] = self.request.user
        
        return context
