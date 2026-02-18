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
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        import threading
        import sys

        def send_email_thread(subject, html_message, plain_message, from_email, recipient_list):
            print(f"--- Intento de envío de email a {recipient_list} desde {from_email} ---")
            print(f"--- Config: Host={settings.EMAIL_HOST}, Port={settings.EMAIL_PORT}, User={settings.EMAIL_HOST_USER}, TLS={settings.EMAIL_USE_TLS}, SSL={settings.EMAIL_USE_SSL} ---")
            sys.stdout.flush()
            try:
                send_mail(
                    subject,
                    plain_message,
                    from_email,
                    recipient_list,
                    html_message=html_message,
                    fail_silently=False, 
                )
                print("--- Email enviado correctamente ---")
                sys.stdout.flush()
            except Exception as e:
                print(f"!!! Error enviando email async: {e}")
                import traceback
                traceback.print_exc()
                sys.stdout.flush()

        subject = 'Verifica tu cuenta en TodoPadel'
        html_message = render_to_string('accounts/emails/verification_email.html', {'code': code})
        plain_message = strip_tags(html_message)
        
        email_thread = threading.Thread(
            target=send_email_thread,
            args=(subject, html_message, plain_message, settings.DEFAULT_FROM_EMAIL, [user.email])
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
        from .utils import get_player_stats, get_user_ranking
        
        # Obtener estadísticas completas
        stats = get_player_stats(self.request.user)
        context['stats'] = stats

        # Obtener Ranking
        ranking_info = get_user_ranking(self.request.user)
        context['ranking_info'] = ranking_info

        # --- Invitaciones (Fix: Pasar al contexto) ---
        from equipos.models import Invitation
        context['invitaciones_enviadas'] = self.request.user.sent_invitations.filter(status=Invitation.Status.PENDING)
        context['invitaciones_recibidas'] = self.request.user.received_invitations.filter(status=Invitation.Status.PENDING)

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
        from .utils import get_division_rankings
        from equipos.models import Division
        
        # Obtener división seleccionada del parámetro GET
        division_id = self.request.GET.get('division')
        
        # Si no hay división seleccionada, usar la del usuario o la primera
        if not division_id:
            if self.request.user.is_authenticated and self.request.user.division:
                division_id = self.request.user.division.id
            else:
                first_div = Division.objects.first()
                if first_div:
                    division_id = first_div.id

        # Filtrar divisiones (Solo UNA a la vez)
        if division_id:
            divisiones = Division.objects.filter(id=division_id)
        else:
            # Fallback: si no hay divisiones en absoluto
            divisiones = Division.objects.none()
        
        rankings_por_division = []
        
        for division in divisiones:
            # Ahora la función get_division_rankings debe traer a todos los de esa división
            jugadores_con_puntos = get_division_rankings(division)
            
            # Mostrar tabla incluso si está vacía (para que se vea que no hay nadie)
            # O si preferimos ocultar: if jugadores_con_puntos:
            rankings_por_division.append({
                'division': division,
                'jugadores': jugadores_con_puntos
            })
        
        return rankings_por_division
    
    def get_context_data(self, **kwargs):
        from equipos.models import Division
        context = super().get_context_data(**kwargs)
        
        # Agregar todas las divisiones para el filtro (Dropdown)
        context['divisiones'] = Division.objects.all().order_by('nombre')
        
        # Determinar la división seleccionada para marcar en el select
        division_id = self.request.GET.get('division')
        if not division_id:
             if self.request.user.is_authenticated and self.request.user.division:
                division_id = str(self.request.user.division.id)
             else:
                first = Division.objects.first()
                if first:
                    division_id = str(first.id)
        
        context['division_seleccionada'] = division_id
        
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
        from .utils import get_player_stats, get_user_ranking
        
        # El objeto usuario ya está en self.object o context['perfil_usuario']
        usuario = self.object
        
        # Obtener estadísticas completas
        stats = get_player_stats(usuario)
        context['stats'] = stats

        # Obtener Ranking
        ranking_info = get_user_ranking(usuario)
        context['ranking_info'] = ranking_info

        # --- Lógica de Invitación ---
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


class OrganizadorDetailView(DetailView):
    model = CustomUser
    template_name = 'accounts/organizador_detail.html'
    context_object_name = 'organizador'

    def get_queryset(self):
        # Solo usuarios organizadores
        return CustomUser.objects.filter(tipo_usuario=CustomUser.TipoUsuario.ORGANIZER)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organizador = self.object
        
        # 1. Perfil extendido
        if hasattr(organizador, 'perfil_organizador'):
            context['perfil_detalle'] = organizador.perfil_organizador
            context['sponsors'] = organizador.perfil_organizador.sponsors.all().order_by('orden')
        else:
            context['perfil_detalle'] = None
            context['sponsors'] = []

        # 2. Torneos
        # Asumiendo que añadimos related_name='torneos_organizados' en Torneo
        torneos = organizador.torneos_organizados.all().order_by('-fecha_inicio')
        
        context['torneos_activos'] = torneos.filter(estado__in=['AB', 'EJ'])
        context['torneos_historial'] = torneos.filter(estado='FN')
        
        return context
        
        context['can_invite'] = can_invite
        
        # Separar inscripciones por estado para la vista
        inscripciones = stats['inscripciones']
        context['torneos_activos'] = [i.torneo for i in inscripciones if i.torneo.estado in ['AB', 'EJ']]
        context['torneos_finalizados'] = [i.torneo for i in inscripciones if i.torneo.estado == 'FN']
        
        return context
