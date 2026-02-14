from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, ListView, DetailView
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
    success_url = reverse_lazy('accounts:verificar_email')

    def form_valid(self, form):
        # 1. Guardar usuario pero inactivo
        user = form.save(commit=False)
        user.is_active = False # Deberá verificar email
        
        # 2. Generar código
        import random
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        user.verification_code = code
        user.save()

        # 3. Enviar email en segundo plano (Threading)
        from django.core.mail import send_mail
        from django.conf import settings
        import threading

        def send_email_thread(subject, message, from_email, recipient_list):
            try:
                send_mail(
                    subject,
                    message,
                    from_email,
                    recipient_list,
                    fail_silently=True, # No bloquear si falla
                )
            except Exception as e:
                print(f"Error enviando email async: {e}")

        subject = 'Verifica tu cuenta en PadelApp'
        message = f'Tu código de verificación es: {code}'
        
        email_thread = threading.Thread(
            target=send_email_thread,
            args=(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
        )
        email_thread.start()

        # 4. Guardar ID en sesión para la siguiente vista
        self.request.session['verification_user_id'] = user.id
        
        return super().form_valid(form)


from django.views.generic import FormView
from django.shortcuts import redirect, render
from django.contrib.auth import login
from django import forms
from django.contrib import messages

class VerificationForm(forms.Form):
    code = forms.CharField(max_length=6, label="Código de Verificación")

class VerifyEmailView(FormView):
    template_name = 'accounts/verification_form.html'
    form_class = VerificationForm
    success_url = reverse_lazy('core:home')

    def dispatch(self, request, *args, **kwargs):
        if 'verification_user_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user_id = self.request.session.get('verification_user_id')
        user = CustomUser.objects.get(id=user_id)
        code = form.cleaned_data['code']

        if user.verification_code == code:
            user.is_active = True
            user.verification_code = None # Limpiar código
            user.is_verified = True
            user.save()
            
            # Autologuear
            login(self.request, user)
            del self.request.session['verification_user_id']
            return super().form_valid(form)
        else:
            form.add_error('code', 'Código incorrecto')
            return self.form_invalid(form)


class PerfilView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserProfileForm
    template_name = 'accounts/perfil.html'
    success_url = reverse_lazy('accounts:perfil')

    def get_object(self, queryset=None):
        # Devuelve el usuario actualmente logueado con división precargada
        return CustomUser.objects.select_related('division').get(pk=self.request.user.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_player_stats
        
        # Obtener estadísticas completas
        stats = get_player_stats(self.request.user)
        context['stats'] = stats

        # --- Próximos Partidos ---
        equipo = self.request.user.equipo
        if equipo:
            from django.db.models import Q
            from torneos.models import Partido, PartidoGrupo
            
            # 1. Partidos de Eliminatoria Pendientes
            partidos_elim = Partido.objects.filter(
                Q(equipo1=equipo) | Q(equipo2=equipo),
                ganador__isnull=True,
                torneo__estado__in=['AB', 'EJ'] # Solo torneos activos
            ).select_related('torneo', 'equipo1', 'equipo2')

            # 2. Partidos de Fase de Grupos Pendientes
            partidos_grupo = PartidoGrupo.objects.filter(
                Q(equipo1=equipo) | Q(equipo2=equipo),
                ganador__isnull=True,
                grupo__torneo__estado__in=['AB', 'EJ']
            ).select_related('grupo__torneo', 'equipo1', 'equipo2')

            # Combinar y ordenar por fecha (los que no tienen fecha van al final)
            proximos = sorted(
                list(partidos_elim) + list(partidos_grupo),
                key=lambda x: x.fecha_hora.timestamp() if x.fecha_hora else 9999999999
            )
            context['proximos_partidos'] = proximos
        else:
            context['proximos_partidos'] = []
        
        # Separar inscripciones por estado para la vista
        inscripciones = stats['inscripciones']
        context['torneos_activos'] = [i.torneo for i in inscripciones if i.torneo.estado in ['AB', 'EJ']]
        context['torneos_finalizados'] = [i.torneo for i in inscripciones if i.torneo.estado == 'FN']
        
        return context


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
                Q(equipos_como_jugador1__division=division) | Q(equipos_como_jugador2__division=division)
            ).distinct().annotate(
                # Victorias como jugador1 en partidos de eliminación
                victorias_j1_elim=Count(
                    'equipos_como_jugador1__partidos_bracket_ganados',
                    filter=Q(equipos_como_jugador1__partidos_bracket_ganados__isnull=False),
                    distinct=True
                ),
                # Victorias como jugador1 en partidos de grupo
                victorias_j1_grupo=Count(
                    'equipos_como_jugador1__partidos_grupo_ganados',
                    filter=Q(equipos_como_jugador1__partidos_grupo_ganados__isnull=False),
                    distinct=True
                ),
                # Victorias como jugador2 en partidos de eliminación
                victorias_j2_elim=Count(
                    'equipos_como_jugador2__partidos_bracket_ganados',
                    filter=Q(equipos_como_jugador2__partidos_bracket_ganados__isnull=False),
                    distinct=True
                ),
                # Victorias como jugador2 en partidos de grupo
                victorias_j2_grupo=Count(
                    'equipos_como_jugador2__partidos_grupo_ganados',
                    filter=Q(equipos_como_jugador2__partidos_grupo_ganados__isnull=False),
                    distinct=True
                ),
                # Partidos jugados como jugador1 en eliminación
                partidos_j1_elim_1=Count(
                    'equipos_como_jugador1__partidos_bracket_e1',
                    filter=Q(equipos_como_jugador1__partidos_bracket_e1__ganador__isnull=False),
                    distinct=True
                ),
                partidos_j1_elim_2=Count(
                    'equipos_como_jugador1__partidos_bracket_e2',
                    filter=Q(equipos_como_jugador1__partidos_bracket_e2__ganador__isnull=False),
                    distinct=True
                ),
                # Partidos jugados como jugador1 en grupo
                partidos_j1_grupo_1=Count(
                    'equipos_como_jugador1__partidos_grupo_e1',
                    filter=Q(equipos_como_jugador1__partidos_grupo_e1__ganador__isnull=False),
                    distinct=True
                ),
                partidos_j1_grupo_2=Count(
                    'equipos_como_jugador1__partidos_grupo_e2',
                    filter=Q(equipos_como_jugador1__partidos_grupo_e2__ganador__isnull=False),
                    distinct=True
                ),
                # Partidos jugados como jugador2 en eliminación
                partidos_j2_elim_1=Count(
                    'equipos_como_jugador2__partidos_bracket_e1',
                    filter=Q(equipos_como_jugador2__partidos_bracket_e1__ganador__isnull=False),
                    distinct=True
                ),
                partidos_j2_elim_2=Count(
                    'equipos_como_jugador2__partidos_bracket_e2',
                    filter=Q(equipos_como_jugador2__partidos_bracket_e2__ganador__isnull=False),
                    distinct=True
                ),
                # Partidos jugados como jugador2 en grupo
                partidos_j2_grupo_1=Count(
                    'equipos_como_jugador2__partidos_grupo_e1',
                    filter=Q(equipos_como_jugador2__partidos_grupo_e1__ganador__isnull=False),
                    distinct=True
                ),
                partidos_j2_grupo_2=Count(
                    'equipos_como_jugador2__partidos_grupo_e2',
                    filter=Q(equipos_como_jugador2__partidos_grupo_e2__ganador__isnull=False),
                    distinct=True
                ),
                # Torneos ganados
                torneos_j1=Count('equipos_como_jugador1__torneos_ganados', distinct=True),
                torneos_j2=Count('equipos_como_jugador2__torneos_ganados', distinct=True),
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


class PublicProfileView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'accounts/public_profile.html'
    context_object_name = 'perfil_usuario'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_player_stats
        
        # El objeto usuario ya está en self.object o context['perfil_usuario']
        usuario = self.object
        
        # Obtener estadísticas completas
        stats = get_player_stats(usuario)
        context['stats'] = stats

        # --- Lógica de Invitación ---
        # Solo si:
        # 1. El visitante está logueado y no es el dueño del perfil
        # 2. El visitante NO tiene equipo
        # 3. El dueño del perfil NO tiene equipo
        # 4. Ambos son de la misma división (Regla de negocio)
        can_invite = False
        if self.request.user.is_authenticated and self.request.user != usuario:
            visitante = self.request.user
            if not visitante.equipo and not usuario.equipo:
                if visitante.division == usuario.division:
                    can_invite = True
        
        context['can_invite'] = can_invite
        
        # Separar inscripciones por estado para la vista
        inscripciones = stats['inscripciones']
        context['torneos_activos'] = [i.torneo for i in inscripciones if i.torneo.estado in ['AB', 'EJ']]
        context['torneos_finalizados'] = [i.torneo for i in inscripciones if i.torneo.estado == 'FN']
        
        return context
