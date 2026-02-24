from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, UpdateView, ListView, DetailView, DeleteView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.contrib import messages
from .models import CustomUser, Organizacion, Sponsor
from .forms import CustomUserCreationForm, CustomUserProfileForm, CustomLoginForm, OrganizacionForm, SponsorForm, GoogleProfileCompletionForm


class CompleteGoogleProfileView(LoginRequiredMixin, UpdateView):
    """
    Vista para que los usuarios nuevos de Google completen su perfil.
    Solo permite acceder si le faltan campos obligatorios.
    """
    model = CustomUser
    form_class = GoogleProfileCompletionForm
    template_name = 'accounts/complete_profile.html'
    success_url = reverse_lazy('core:home')

    def get_object(self, queryset=None):
        return self.request.user

    def dispatch(self, request, *args, **kwargs):
        # Si el perfil ya está completo, redirigir al home
        if request.user.is_authenticated:
            if request.user.division_id and request.user.numero_telefono:
                from django.shortcuts import redirect
                return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, '¡Perfil completado! Bienvenido/a a TodoPadel.')
        return super().form_valid(form)




class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomLoginForm
    redirect_authenticated_user = True

    def form_invalid(self, form):
        from django.shortcuts import redirect
        if form.errors.get('__all__'):
            for error in form.errors.as_data().get('__all__', []):
                if getattr(error, 'code', None) == 'unverified':
                    return redirect('accounts:verificar_email')
        return super().form_invalid(form)


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
        user = self.request.user
        
        # --- LÓGICA DE DASHBOARD DE GESTIÓN (ADMIN/ORGANIZADOR) ---
        if user.tipo_usuario in ['ADMIN', 'ORGANIZER']:
            from torneos.models import Torneo, Inscripcion
            from django.core.cache import cache as dj_cache
            from django.db.models import Prefetch, Count, Q

            cache_key = f'perfil_gestion_{user.id}'
            cached_ctx = dj_cache.get(cache_key)

            if cached_ctx:
                context.update(cached_ctx)
            else:
                organizacion = user.organizacion

                # Torneos gestionados con select_related para evitar queries extra
                if user.tipo_usuario == 'ADMIN':
                    torneos_gestionados = Torneo.objects.all().select_related(
                        'division', 'organizacion'
                    ).order_by('-fecha_inicio')
                else:
                    torneos_gestionados = Torneo.objects.filter(
                        organizacion=organizacion
                    ).select_related('division', 'organizacion').order_by('-fecha_inicio')

                # Prefetch de inscripciones optimizado
                inscripciones_qs = Inscripcion.objects.select_related(
                    'equipo', 'equipo__division', 'equipo__jugador1', 'equipo__jugador2'
                ).order_by('-fecha_inscripcion')

                torneos_con_inscripciones = list(
                    torneos_gestionados.prefetch_related(
                        Prefetch('inscripciones', queryset=inscripciones_qs, to_attr='inscripciones_list')
                    )
                )

                # Alertas de división y contadores en un solo paso
                total_torneos_activos = 0
                for torneo in torneos_con_inscripciones:
                    if torneo.estado in ['AB', 'EJ']:
                        total_torneos_activos += 1
                    for ins in torneo.inscripciones_list:
                        ins.alerta_division = None
                        if torneo.division and ins.equipo.division:
                            if ins.equipo.division.orden < torneo.division.orden:
                                ins.alerta_division = 'SUPERIOR'
                            elif ins.equipo.division.orden > torneo.division.orden:
                                ins.alerta_division = 'INFERIOR'

                # Inscripciones de hoy (una sola query)
                hoy = timezone.now().date()
                torneo_ids = [t.id for t in torneos_con_inscripciones]
                total_inscripciones_hoy = Inscripcion.objects.filter(
                    torneo_id__in=torneo_ids,
                    fecha_inscripcion__date=hoy
                ).count() if torneo_ids else 0

                to_cache = {
                    'torneos_gestionados': torneos_con_inscripciones,
                    'torneos_con_inscripciones': torneos_con_inscripciones,
                    'total_torneos_activos': total_torneos_activos,
                    'total_inscripciones_hoy': total_inscripciones_hoy,
                }
                dj_cache.set(cache_key, to_cache, 300)
                context.update(to_cache)


        # --- LÓGICA DE JUGADOR (STATS) ---
        # Solo calculamos stats pesadas si el usuario es jugador
        if user.tipo_usuario == 'PLAYER':
            from .utils import get_player_stats, get_user_ranking
            from django.core.cache import cache as dj_cache
            
            cache_key = f'perfil_stats_ctx_{user.id}'
            cached_ctx = dj_cache.get(cache_key)
            
            if cached_ctx:
                context.update(cached_ctx)
            else:
                # Obtener estadísticas completas
                stats = get_player_stats(user)
                stats_ctx = {}
                stats_ctx['stats'] = stats

                # Obtener Ranking
                ranking_info = get_user_ranking(user)
                stats_ctx['ranking_info'] = ranking_info

                # Separar inscripciones por estado para la vista
                inscripciones_stats = stats['inscripciones']
                stats_ctx['torneos_activos'] = [i.torneo for i in inscripciones_stats if i.torneo.estado in ['AB', 'EJ']]
                stats_ctx['torneos_finalizados'] = [i.torneo for i in inscripciones_stats if i.torneo.estado == 'FN']
                
                # Próximos Partidos (Solo para Jugadores)
                equipo = user.equipo
                proximos = []
                if equipo:
                    from django.db.models import Q
                    from torneos.models import Partido, PartidoGrupo
                    
                    partidos_elim = list(Partido.objects.filter(
                        Q(equipo1=equipo) | Q(equipo2=equipo),
                        ganador__isnull=True,
                        torneo__estado__in=['AB', 'EJ']
                    ).select_related('torneo', 'equipo1', 'equipo2'))

                    partidos_grupo = list(PartidoGrupo.objects.filter(
                        Q(equipo1=equipo) | Q(equipo2=equipo),
                        ganador__isnull=True,
                        grupo__torneo__estado__in=['AB', 'EJ']
                    ).select_related('grupo__torneo', 'equipo1', 'equipo2'))
                    
                    proximos = sorted(
                        partidos_elim + partidos_grupo,
                        key=lambda x: x.fecha_hora.timestamp() if x.fecha_hora else 9999999999
                    )
                stats_ctx['proximos_partidos'] = proximos
                
                dj_cache.set(cache_key, stats_ctx, 300)
                context.update(stats_ctx)

        # --- Invitaciones (Común para todos si son jugadores activos, pero prioritario para PLAYER) ---
        from equipos.models import Invitation
        context['invitaciones_enviadas'] = user.sent_invitations.filter(status=Invitation.Status.PENDING)
        context['invitaciones_recibidas'] = user.received_invitations.filter(status=Invitation.Status.PENDING)
        
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
        context['divisiones'] = Division.objects.all().order_by('orden')
        
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

    def get_object(self, queryset=None):
        return CustomUser.objects.select_related('division').get(pk=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_player_stats, get_user_ranking
        from django.core.cache import cache as dj_cache
        
        # El objeto usuario ya está en self.object o context['perfil_usuario']
        usuario = self.object
        
        cache_key = f'public_profile_ctx_{usuario.id}'
        cached_ctx = dj_cache.get(cache_key)
        
        if cached_ctx:
            context.update(cached_ctx)
        else:
            # Obtener estadísticas completas
            stats = get_player_stats(usuario)
            public_ctx = {}
            public_ctx['stats'] = stats

            # Obtener Ranking
            ranking_info = get_user_ranking(usuario)
            public_ctx['ranking_info'] = ranking_info
            
            # Separar inscripciones por estado para la vista
            inscripciones = stats['inscripciones']
            public_ctx['torneos_activos'] = [i.torneo for i in inscripciones if i.torneo.estado in ['AB', 'EJ']]
            public_ctx['torneos_finalizados'] = [i.torneo for i in inscripciones if i.torneo.estado == 'FN']
            
            dj_cache.set(cache_key, public_ctx, 300)
            context.update(public_ctx)

        # --- LÓGICA DE INVITACIÓN (No se cachea porque depende del visitante) ---
        can_invite = False
        if self.request.user.is_authenticated and self.request.user != usuario:
            visitante = self.request.user
            if not visitante.equipo and not usuario.equipo:
                if visitante.division_id == usuario.division_id:
                    can_invite = True

        context['can_invite'] = can_invite
        return context



class OrganizacionListView(ListView):
    model = Organizacion
    template_name = 'accounts/organizacion_list.html'
    context_object_name = 'organizaciones'
    ordering = ['nombre']


class OrganizacionDetailView(DetailView):
    # model = Organizacion (Dynamic import in dispatch/queryset to avoid circular imports if needed)
    template_name = 'accounts/organizador_detail.html' # Mantengo el nombre del template por ahora
    context_object_name = 'organizacion'

    def get_queryset(self):
        from .models import Organizacion
        return Organizacion.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organizacion = self.object
        
        # 1. Sponsors
        context['sponsors'] = organizacion.sponsors.all().order_by('orden')

        # 2. Torneos
        # Torneo ahora tiene FK 'organizacion'
        torneos = organizacion.torneos.all().order_by('-fecha_inicio')
        
        context['torneos_activos'] = torneos.filter(estado__in=['AB', 'EJ'])
        context['torneos_historial'] = torneos.filter(estado='FN')
        
        return context


from .forms import OrganizacionForm, SponsorForm

class OrganizacionSettingsView(LoginRequiredMixin, UpdateView):
    # model = Organizacion # Dynamic to avoid circular imports
    form_class = OrganizacionForm
    template_name = 'accounts/organizacion_settings.html'
    success_url = reverse_lazy('accounts:organizacion_settings')

    def get_object(self, queryset=None):
        # Obtener la organización del usuario actual
        user = self.request.user
        if not user.organizacion:
             from django.http import Http404
             raise Http404("No tienes una organización asignada.")
        return user.organizacion
    
    def get_queryset(self):
         from .models import Organizacion
         return Organizacion.objects.all()



class OrganizacionSponsorsView(LoginRequiredMixin, CreateView):
    model = Sponsor
    form_class = SponsorForm
    template_name = 'accounts/organizacion_sponsors.html'

    def get_success_url(self):
        return reverse('accounts:organizacion_sponsors')

    def form_valid(self, form):
        user = self.request.user
        if not user.organizacion:
             from django.http import Http404
             raise Http404("No tienes una organización asignada.")
        
        form.instance.organizacion = user.organizacion
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.organizacion:
            context['sponsors'] = user.organizacion.sponsors.all().order_by('orden')
        return context

class SponsorDeleteView(LoginRequiredMixin, DeleteView):
    model = Sponsor
    
    def get_success_url(self):
        return reverse('accounts:organizacion_sponsors')
        
    def get_queryset(self):
        # Asegurar que solo pueda borrar sponsors de su organización
        from .models import Sponsor
        return Sponsor.objects.filter(organizacion=self.request.user.organizacion)

class SponsorUpdateView(LoginRequiredMixin, UpdateView):
    model = Sponsor
    form_class = SponsorForm
    template_name = 'accounts/sponsor_edit.html'

    def get_success_url(self):
        return reverse('accounts:organizacion_sponsors')

    def get_queryset(self):
        # Asegurar que solo pueda editar sponsors de su organización
        from .models import Sponsor
        return Sponsor.objects.filter(organizacion=self.request.user.organizacion)


class DummyUserCreationView(LoginRequiredMixin, CreateView):
    """Vista para que un organizador cree un usuario dummy"""
    model = CustomUser
    from .forms import DummyUserCreationForm
    form_class = DummyUserCreationForm
    template_name = 'accounts/dummy_user_form.html'
    success_url = reverse_lazy('accounts:organizacion_settings')

    def dispatch(self, request, *args, **kwargs):
        if request.user.tipo_usuario not in ['ADMIN', 'ORGANIZER'] or not request.user.organizacion:
            messages.error(request, "Acceso denegado. Solo para organizadores.")
            return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Añadir Jugador Sin Registro"
        return context

    def form_valid(self, form):
        # Pasar la organización al método save del form
        form.save(organizacion=self.request.user.organizacion)
        messages.success(self.request, f"¡Jugador '{form.instance.full_name}' creado con éxito!")
        return redirect(self.success_url)

